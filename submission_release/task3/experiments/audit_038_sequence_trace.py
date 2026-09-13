"""Forensic trace of candidate-038 short-horizon sequencing decisions (read-only).

Reconstructs, from an already-recorded task_queue sweep log, what the
short-horizon sequencer saw at every replan, what it chose, what the committed
ResolveSource actually executed, and how far the single-action ``TaskPreview``
endpoint sat from the real completion position.

The script only reads logs: it never imports the simulator, the controller, or
any production module, and it never writes outside its three CSV outputs.

Only quantities that are actually present in the log are reported.  Where the
log cannot support a number the row/field is left empty and the summary says so
instead of guessing.
"""

from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
import re
import statistics
from pathlib import Path
from typing import Any


DEFAULT_POLICY = "candidate_038_task_queue_sweep"

# ``TaskDrivenController._sequence_waiting`` hard-codes this prefilter width.
TOP_N = 3

# Only used when a log predates the physical configuration block; every current
# sweep log records these, and ``_physical`` prefers the logged values.
FALLBACK_PHYSICAL = {
    "speed_mps": 5.0,
    "switch_s": 1.0,
    "measure_s": 5.0,
    "optical_s": 3.0,
    "laser_s": 2.0,
    "clear_radius_m": 20.0,
}

RESOLVE_CHANNEL = re.compile(r"Resolve ch(\d+)")
# Stranding reasons label tasks either by Task.label ("Resolve ch7") or, when a
# required task was never previewed, by raw identity ("(<TaskKind.RESOLVE_SOURCE:
# 'ResolveSource'>, 17)").  Both forms are parsed.
STRANDED_CHANNEL = re.compile(r"Resolve ch(\d+)|RESOLVE_SOURCE[^)]*?,\s*(\d+)\s*\)")
DISTANCE_TOL_M = 1e-7


def _load(path: Path, policy: str) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    metadata = next(
        (row for row in rows if row.get("record_type") == "metadata"), {}
    )
    cases = sorted(
        (row for row in rows if row.get("policy") == policy),
        key=lambda row: int(row["scenario_seed"]),
    )
    if not cases:
        raise ValueError(f"no case records for policy {policy!r}")
    return metadata, cases


def _physical(metadata: dict[str, Any]) -> dict[str, float]:
    logged = metadata.get("configuration", {}).get("PhysicalConfig", {})
    return {
        key: float(logged.get(key, value))
        for key, value in FALLBACK_PHYSICAL.items()
    }


def _distance(first: Any, second: Any) -> float:
    return math.hypot(float(first[0]) - float(second[0]), float(first[1]) - float(second[1]))


def _sequence_steps(label: str) -> list[str]:
    return [step.strip() for step in label.split(" -> ") if step.strip()]


def _step_channel(step: str) -> int | None:
    match = RESOLVE_CHANNEL.fullmatch(step)
    return int(match.group(1)) if match else None


def _is_resolve_only(label: str) -> bool:
    """True for the resolve-only prefixes the sequencer adds as a fallback."""
    steps = _sequence_steps(label)
    return len(steps) == 1 and _step_channel(steps[0]) is not None


def _stranded_channels(reason: str | None) -> list[int]:
    if not reason:
        return []
    channels = []
    for first, second in STRANDED_CHANNEL.findall(reason):
        channels.append(int(first or second))
    return channels


def _action_cost(
    action: dict[str, Any], current_channel: int, physical: dict[str, float]
) -> tuple[float, int]:
    """Reproduce the controller's own time accounting for one logged action.

    Movement and operating times are read from ``PhysicalConfig``; the channel
    switch is charged only for MEASURE, matching ``SearchController._measure``
    and the ``clear`` protocol invariant that a clear never moves the channel.
    """
    cost = float(action["movement_m"]) / physical["speed_mps"]
    if action["action_kind"] == "MEASURE":
        if int(action["channel"]) != current_channel:
            cost += physical["switch_s"]
        return cost + physical["measure_s"], int(action["channel"])
    return cost + physical["optical_s"] + physical["laser_s"], current_channel


def _check_cost_model(
    diagnostics: list[dict[str, Any]],
    breakdown: dict[str, float],
    physical: dict[str, float],
) -> None:
    """Fail loudly if the reconstructed time model drifts from the log."""
    actions = [item for item in diagnostics if item.get("type") == "task_action"]
    movement = measurement = optical = laser = switching = 0.0
    current = 1
    for action in actions:
        movement += float(action["movement_m"]) / physical["speed_mps"]
        if action["action_kind"] == "MEASURE":
            measurement += physical["measure_s"]
            if int(action["channel"]) != current:
                switching += physical["switch_s"]
            current = int(action["channel"])
        else:
            optical += physical["optical_s"]
            laser += physical["laser_s"]
    reconstructed = {
        "movement_s": movement,
        "measurement_s": measurement,
        "optical_s": optical,
        "laser_s": laser,
        "switching_s": switching,
    }
    for key, value in reconstructed.items():
        if abs(value - float(breakdown[key])) > 1e-6:
            raise ValueError(
                f"reconstructed {key}={value} does not match logged "
                f"{breakdown[key]}; the log and the time model disagree"
            )


def _walk(diagnostics: list[dict[str, Any]], physical: dict[str, float]) -> dict[str, Any]:
    """Single chronological pass over the diagnostics.

    Produces the decision rows (each carrying the robot pose the sequencer saw),
    the committed ResolveSource traces with their real action chains, and the
    global action/pose stream used for validation.
    """
    decisions: list[dict[str, Any]] = []
    traces: list[dict[str, Any]] = []
    actions: list[dict[str, Any]] = []
    position = (0.0, 0.0)
    current_channel = 1
    active: dict[str, Any] | None = None

    for index, item in enumerate(diagnostics):
        kind = item.get("type")
        if kind == "task_action":
            cost, current_channel = _action_cost(item, current_channel, physical)
            record = {
                "index": index,
                "action_kind": item["action_kind"],
                "channel": int(item["channel"]),
                "start": item["start"],
                "end": item["end"],
                "movement_m": float(item["movement_m"]),
                "reason": item["reason"],
                "opportunistic": bool(item["opportunistic"]),
                "active_task_type": item.get("active_task_type"),
                "active_channel": item.get("active_channel"),
                "cost_s": cost,
                "sweep_sector": item.get("sweep_sector"),
                "frontier_rank": item.get("frontier_rank"),
                "local_leg_retrace": bool(item.get("local_leg_retrace")),
                "macro_backward_movement": bool(item.get("macro_backward_movement")),
            }
            actions.append(record)
            position = (float(item["end"][0]), float(item["end"][1]))
            if (
                active is not None
                and record["active_task_type"] == "ResolveSource"
                and record["active_channel"] == active["channel"]
            ):
                bucket = "opportunistic" if record["opportunistic"] else "main"
                active[bucket].append(record)
        elif kind == "task_started":
            if item.get("active_task_type") == "ResolveSource":
                active = {
                    "channel": int(item["active_channel"]),
                    "start_index": index,
                    "start_position": tuple(map(float, item["task_start_position"])),
                    "pose_at_start": position,
                    "channel_at_start": current_channel,
                    "main": [],
                    "opportunistic": [],
                    "frontier_rank": item.get("frontier_rank"),
                    "phase": item.get("phase"),
                }
        elif kind in ("task_completed", "task_paused") and active is not None:
            if (
                item.get("active_task_type") == "ResolveSource"
                and item.get("active_channel") == active["channel"]
            ):
                end = item.get("task_end_position")
                active["end_index"] = index
                active["end_position"] = (
                    tuple(map(float, end)) if end else position
                )
                active["outcome"] = item.get("task_completion_reason") or item.get("pause_reason")
                active["later_opportunistic"] = [
                    action for action in actions
                    if action["index"] > index
                    and action["opportunistic"]
                    and action["active_channel"] == active["channel"]
                ]
                traces.append(active)
                active = None
        elif kind == "route_sequence_decision":
            candidates = item["candidate_sequences"]
            considered = sorted({
                channel
                for candidate in candidates
                for channel in (
                    [_step_channel(step) for step in _sequence_steps(candidate["sequence"])]
                )
                if channel is not None
            })
            preview_ends = {
                _step_channel(_sequence_steps(candidate["sequence"])[0]): tuple(
                    map(float, candidate["estimated_end_position"])
                )
                for candidate in candidates
                if _is_resolve_only(candidate["sequence"])
            }
            stranded = sorted({
                channel
                for candidate in candidates
                for channel in _stranded_channels(candidate.get("reason"))
            })
            # "Advance is gated by an unsatisfiable required set" is observable:
            # every sequence that reaches the milestone is infeasible, so
            # ``choose_short_horizon_sequence`` appends resolve-only prefixes and
            # the cheapest prefix — always a single task, since every extra task
            # only adds cost — wins the argmin.
            advance_candidates = [
                candidate for candidate in candidates
                if any(step.startswith("Advance") for step in _sequence_steps(candidate["sequence"]))
            ]
            if not advance_candidates:
                mode = "coverage_complete"
            elif any(candidate["feasible"] for candidate in advance_candidates):
                mode = "advance_feasible"
            else:
                mode = "advance_blocked"
            decisions.append({
                "index": index,
                "event": item.get("event"),
                "pose": position,
                "current_channel": current_channel,
                "active_channel": active["channel"] if active else None,
                "chosen_sequence": item.get("chosen_sequence"),
                "chosen_next_task": item.get("chosen_next_task"),
                "chosen_cost_s": _chosen_cost(candidates, item.get("chosen_sequence")),
                "candidates": candidates,
                "considered": considered,
                "preview_ends": preview_ends,
                # A sequence that ends with Advance reports the Advance vertex as
                # its estimated_end_position, so the only candidates that expose a
                # *resolve* preview endpoint are the resolve-only prefixes the
                # fallback branch adds.  For a two-task prefix that endpoint is the
                # second task's preview, computed before the first task moved.
                "second_step_previews": [
                    {
                        "sequence": candidate["sequence"],
                        "cost_s": candidate["estimated_cost_s"],
                        "second_end": candidate["estimated_end_position"],
                        "second_preview_is_plan_pose": (
                            _distance(candidate["estimated_end_position"], position)
                            <= DISTANCE_TOL_M
                        ),
                    }
                    for candidate in candidates
                    if sum(
                        _step_channel(step) is not None
                        for step in _sequence_steps(candidate["sequence"])
                    ) == 2
                    and not any(
                        step.startswith("Advance")
                        for step in _sequence_steps(candidate["sequence"])
                    )
                ],
                "stranded": stranded,
                "mode": mode,
                "effective_resolve_steps": sum(
                    _step_channel(step) is not None
                    for step in _sequence_steps(item.get("chosen_sequence") or "")
                ),
                "has_resolve_only_candidate": any(
                    _is_resolve_only(candidate["sequence"]) for candidate in candidates
                ),
                "snapshot": _following_snapshot(diagnostics, index, item.get("event")),
            })
    return {"decisions": decisions, "traces": traces, "actions": actions}


def _chosen_cost(candidates: list[dict[str, Any]], chosen: str | None) -> float | None:
    for candidate in candidates:
        if candidate["sequence"] == chosen and candidate["feasible"]:
            return candidate["estimated_cost_s"]
    return None


def _following_snapshot(
    diagnostics: list[dict[str, Any]], index: int, event: str | None
) -> dict[str, Any] | None:
    """The ``waiting_rebuilt`` snapshot emitted by the same ``_refresh_waiting``."""
    for later in diagnostics[index + 1:]:
        if later.get("type") == "waiting_rebuilt" and later.get("event") == event:
            return later
        if later.get("type") in ("task_action", "task_started", "sweep_selected"):
            return None
    return None


def _validate_reconstruction(
    diagnostics: list[dict[str, Any]], traces: list[dict[str, Any]]
) -> dict[str, int]:
    """Prove that the reconstructed preview endpoint is the logged one.

    Whenever the sequencer emitted a resolve-only candidate for the task that was
    actually committed next, its logged ``estimated_end_position`` must be
    bit-identical to the point of that Resolve's first executed action.  This is
    what licenses reading anything about a ``TaskPreview`` out of the log.
    """
    checked = matched = 0
    for trace in traces:
        decisions = [
            item for item in diagnostics[:trace["start_index"]]
            if item.get("type") == "route_sequence_decision"
        ]
        if not decisions or not trace["main"]:
            continue
        logged = [
            candidate for candidate in decisions[-1]["candidate_sequences"]
            if candidate["sequence"] == f"Resolve ch{trace['channel']}"
            and candidate["feasible"]
            and candidate["estimated_cost_s"] is not None
        ]
        if not logged:
            continue
        checked += 1
        first = trace["main"][0]
        if _distance(logged[0]["estimated_end_position"], first["end"]) <= 1e-9:
            matched += 1
        else:
            raise ValueError(
                f"reconstructed preview endpoint for ch{trace['channel']} does not "
                f"match the logged candidate endpoint"
            )
    return {"checked": checked, "matched": matched}


def _decode_trace(trace: dict[str, Any]) -> dict[str, Any]:
    """Attach the preview/completion comparison to one committed ResolveSource."""
    main = trace["main"]
    # Travelling inside a task spends the same wall clock whether the controller
    # books it against the ACTIVE Resolve or against an opportunistic detour on
    # the way to the ACTIVE target, so both are reported.
    chain = main + trace["opportunistic"]
    row = {
        "channel": trace["channel"],
        "start_index": trace["start_index"],
        "end_index": trace.get("end_index"),
        "outcome": trace.get("outcome"),
        "phase": trace.get("phase"),
        "frontier_rank": trace.get("frontier_rank"),
        "task_start_x_m": trace["start_position"][0],
        "task_start_y_m": trace["start_position"][1],
        "main_action_count": len(main),
        "opportunistic_action_count": len(trace["opportunistic"]),
        "preview_kind": None,
        "preview_reason": None,
        "preview_end_x_m": None,
        "preview_end_y_m": None,
        "actual_end_x_m": None,
        "actual_end_y_m": None,
        "preview_travel_m": None,
        "actual_travel_m": None,
        "endpoint_error_m": None,
        "preview_cost_s": None,
        "actual_main_cost_s": None,
        "actual_total_cost_s": None,
        "cost_error_s": None,
        "cost_error_total_s": None,
        "preview_end_is_start_pose": None,
        "path_length_m": None,
        "net_displacement_m": None,
        "within_task_detour_ratio": None,
        "current_pose_measure_actions": None,
        "forward_route_measure_actions": None,
    }
    if not main:
        return row
    first = main[0]
    end = trace.get("end_position")
    row.update({
        "main_action_chain": "|".join(
            f"{action['action_kind']}:{action['channel']}:{action['reason']}" for action in main
        ),
        "preview_kind": first["action_kind"],
        "preview_reason": first["reason"],
        "preview_end_x_m": float(first["end"][0]),
        "preview_end_y_m": float(first["end"][1]),
        "preview_travel_m": _distance(first["end"], trace["start_position"]),
        "preview_cost_s": first["cost_s"],
        "actual_travel_m": sum(action["movement_m"] for action in main),
        "actual_main_cost_s": sum(action["cost_s"] for action in main),
        "actual_total_cost_s": sum(action["cost_s"] for action in chain),
        "current_pose_measure_actions": sum(
            action["reason"] == "current_position_information" for action in main
        ),
        "forward_route_measure_actions": sum(
            action["reason"] == "forward_route_measurement" for action in main
        ),
    })
    if end is not None:
        # Logged actions are consecutive leg segments, so the path length is just
        # the sum of the travel booked to the ACTIVE Resolve plus its detours.
        path_length = sum(action["movement_m"] for action in chain)
        net = _distance(trace["start_position"], end)
        row.update({
            "actual_end_x_m": float(end[0]),
            "actual_end_y_m": float(end[1]),
            "endpoint_error_m": _distance(first["end"], end),
            "preview_end_is_start_pose": (
                _distance(first["end"], trace["pose_at_start"]) <= DISTANCE_TOL_M
            ),
            "path_length_m": path_length,
            "net_displacement_m": net,
            "within_task_detour_ratio": (
                path_length / net if net > DISTANCE_TOL_M else None
            ),
        })
        row["cost_error_s"] = row["actual_main_cost_s"] - row["preview_cost_s"]
        row["cost_error_total_s"] = row["actual_total_cost_s"] - row["preview_cost_s"]
    return row


def _quantiles(values: list[float]) -> dict[str, float | int | None]:
    if not values:
        return {"count": 0, "mean": None, "median": None, "p90": None, "max": None}
    ordered = sorted(values)
    index = min(len(ordered) - 1, max(0, math.ceil(0.9 * len(ordered)) - 1))
    return {
        "count": len(ordered),
        "mean": statistics.fmean(ordered),
        "median": statistics.median(ordered),
        "p90": ordered[index],
        "max": ordered[-1],
    }


def _second_step_preview(decisions: list[dict[str, Any]]) -> dict[str, Any]:
    """How often a frozen second-step preview collapses onto the planning pose.

    Readable only where the sequencer logged a resolve-only two-task prefix, but
    those are exactly the pairs whose ordering the rollout is comparing.
    """
    pairs = [
        row for decision in decisions for row in decision["second_step_previews"]
    ]
    collapsed = [row for row in pairs if row["second_preview_is_plan_pose"]]
    return {
        "readable_two_task_prefixes": len(pairs),
        "second_preview_at_plan_pose": len(collapsed),
        "share": len(collapsed) / len(pairs) if pairs else None,
    }


def _travel_share(decoded: list[dict[str, Any]]) -> dict[str, Any]:
    """How much of the driven distance sits behind a collapsed preview?"""
    total = sum(row["path_length_m"] or 0.0 for row in decoded)
    collapsed = sum(
        row["path_length_m"] or 0.0 for row in decoded
        if row["preview_end_is_start_pose"]
    )
    return {
        "total_resolve_path_m": total,
        "collapsed_preview_path_m": collapsed,
        "collapsed_preview_share": collapsed / total if total else None,
        "collapsed_preview_tasks": sum(
            1 for row in decoded if row["preview_end_is_start_pose"]
        ),
        "resolve_tasks": len(decoded),
    }


def _grouped_quantiles(rows: list[dict[str, Any]], key: str) -> dict[str, Any]:
    groups: dict[str, list[float]] = {}
    for row in rows:
        value = row.get(key)
        error = row.get("endpoint_error_m")
        if value is None or error is None:
            continue
        groups.setdefault(str(value), []).append(error)
    return {name: _quantiles(values) for name, values in sorted(groups.items())}


def _plan_stability(
    decisions: list[dict[str, Any]], traces: list[dict[str, Any]]
) -> dict[str, Any]:
    """Did a multi-step plan survive the execution of its own first task?

    One row per committed ResolveSource, attributed to the last decision taken
    before it started.  Re-emissions of the same plan at ``belief_updated`` /
    ``active_completed`` / ``select_active`` are therefore counted once, and the
    follow-up is the first replan after the first task actually finished.
    """
    rows: list[dict[str, Any]] = []
    for trace in traces:
        prior = [item for item in decisions if item["index"] < trace["start_index"]]
        if not prior:
            continue
        decision = prior[-1]
        steps = _sequence_steps(decision["chosen_sequence"] or "")
        if len(steps) < 2 or _step_channel(steps[0]) != trace["channel"]:
            continue
        follow_up = next(
            (
                later for later in decisions
                if later["index"] > trace.get("end_index", trace["start_index"])
            ),
            None,
        )
        if follow_up is None:
            continue
        second_channel = _step_channel(steps[1])
        # The candidate the plan itself was built from carries the rollout's own
        # estimate of where the pair ends.  For an Advance-terminated plan that is
        # the Advance vertex rather than the second task's preview endpoint, so the
        # column is named for what it actually holds.
        planned_end = next(
            (
                candidate["estimated_end_position"]
                for candidate in decision["candidates"]
                if candidate["sequence"] == decision["chosen_sequence"]
            ),
            None,
        )
        second_trace = next(
            (
                trace for trace in traces
                if trace["channel"] == second_channel and trace["main"]
                and trace["start_index"] > decision["index"]
            ),
            None,
        )
        rows.append({
            "decision_index": decision["index"],
            "event": decision["event"],
            "plan": decision["chosen_sequence"],
            "plan_cost_s": decision["chosen_cost_s"],
            "step_count": len(steps),
            "first_task": steps[0],
            "planned_second_task": steps[1],
            "planned_second_is_resolve": second_channel is not None,
            "plan_estimated_end_x_m": float(planned_end[0]) if planned_end else None,
            "plan_estimated_end_y_m": float(planned_end[1]) if planned_end else None,
            "plan_pose_x_m": decision["pose"][0],
            "plan_pose_y_m": decision["pose"][1],
            "second_operative_preview_kind": (
                second_trace["main"][0]["action_kind"] if second_trace else None
            ),
            "second_operative_preview_reason": (
                second_trace["main"][0]["reason"] if second_trace else None
            ),
            "second_operative_preview_x_m": (
                float(second_trace["main"][0]["end"][0]) if second_trace else None
            ),
            "second_operative_preview_y_m": (
                float(second_trace["main"][0]["end"][1]) if second_trace else None
            ),
            "follow_up_decision_index": follow_up["index"],
            "follow_up_choice": follow_up["chosen_next_task"],
            "follow_up_sequence": follow_up["chosen_sequence"],
            "second_task_retained": follow_up["chosen_next_task"] == steps[1],
        })
    multi = [row for row in rows if row["planned_second_is_resolve"]]
    retained_multi = sum(row["second_task_retained"] for row in multi)
    return {
        "rows": rows,
        "multi_step_decisions": len(multi),
        "changed_after_first_task": len(multi) - retained_multi,
        "instability_rate": (
            (len(multi) - retained_multi) / len(multi) if multi else None
        ),
    }


def _case_summary(
    record: dict[str, Any], physical: dict[str, float], policy: str
) -> dict[str, Any]:
    diagnostics = record["result"]["diagnostics"]
    _check_cost_model(diagnostics, record["result"]["time_breakdown"], physical)
    walked = _walk(diagnostics, physical)
    decisions, traces = walked["decisions"], walked["traces"]
    decoded = [_decode_trace(trace) for trace in traces]
    stability = _plan_stability(decisions, traces)
    reconstruction = _validate_reconstruction(diagnostics, traces)
    seed = int(record["scenario_seed"])

    errors = [row["endpoint_error_m"] for row in decoded if row["endpoint_error_m"] is not None]
    cost_errors = [row["cost_error_s"] for row in decoded if row["cost_error_s"] is not None]
    counts = [row["main_action_count"] for row in decoded if row["main_action_count"]]

    previews: list[dict[str, Any]] = []
    exclusions: list[dict[str, Any]] = []
    for order, decision in enumerate(decisions):
        snapshot = decision["snapshot"] or {}
        considered = decision["considered"]
        ready_total = snapshot.get("resolve_ready_count")
        for channel, point in decision["preview_ends"].items():
            previews.append({
                "seed": seed,
                "decision_index": decision["index"],
                "event": decision["event"],
                "channel": channel,
                "endpoint_is_current_pose": _distance(point, decision["pose"]) <= DISTANCE_TOL_M,
                "preview_travel_m": _distance(point, decision["pose"]),
                "considered": channel in considered,
                "was_chosen": decision["chosen_next_task"] == f"Resolve ch{channel}",
            })
        # A READY resolve that never entered the candidate set, then chosen soon after.
        later_choices = {
            later["chosen_next_task"]
            for later in decisions[order + 1: order + 3]
        }
        never_considered = [
            channel for channel in (snapshot.get("waiting_order") or [])
            if (parsed := _step_channel(channel)) is not None
            and parsed not in considered
        ]
        exclusions.append({
            "seed": seed,
            "decision_index": decision["index"],
            "event": decision["event"],
            "ready_total": ready_total,
            "considered_count": len(considered),
            "ready_not_evaluated": (
                None if ready_total is None else max(0, ready_total - len(considered))
            ),
            "active_occupied_slot": (
                decision["active_channel"] in considered
                if decision["active_channel"] is not None else False
            ),
            "stranded": decision["stranded"],
            "stranded_not_considered": [
                channel for channel in decision["stranded"] if channel not in considered
            ],
            "waiting_resolves_never_considered": never_considered,
            "excluded_then_chosen_within_two": sorted(
                f"Resolve ch{channel}" for channel in never_considered
                if f"Resolve ch{channel}" in later_choices
            ),
            "has_resolve_only_candidate": decision["has_resolve_only_candidate"],
            "pose_x_m": decision["pose"][0],
            "pose_y_m": decision["pose"][1],
            "current_channel": decision["current_channel"],
            "active_channel": decision["active_channel"],
            "mode": decision["mode"],
            "chosen_cost_s": decision["chosen_cost_s"],
            # "label=cost" for feasible candidates, "label=infeasible" otherwise, so
            # the episode write-ups can be re-derived from the table alone.
            "candidate_costs": "; ".join(
                "%s=%s" % (
                    candidate["sequence"],
                    "infeasible" if not candidate["feasible"] else candidate["estimated_cost_s"],
                )
                for candidate in decision["candidates"]
            ),
            "required_lower_size": len(decision["stranded"]),
            "effective_resolve_steps": decision["effective_resolve_steps"],
            "chosen_sequence": decision["chosen_sequence"],
        })

    summary = {
        "policy": policy,
        "seed": seed,
        "scenario_id": record["scenario_id"],
        "termination_reason": record["result"]["termination_reason"],
        "action_count": record["result"]["action_count"],
        "virtual_time_s": record["result"]["virtual_time_s"],
        "decisions": len(decisions),
        "resolve_tasks": len(traces),
        "endpoint_error_m": _quantiles(errors),
        "endpoint_error_by_preview_mode": _grouped_quantiles(decoded, "preview_reason"),
        "cost_error_s": _quantiles(cost_errors),
        "main_actions_per_resolve": _quantiles([float(count) for count in counts]),
        "preview_reconstruction_check": reconstruction,
        "previews_logged": len(previews),
        "previews_at_current_pose": sum(row["endpoint_is_current_pose"] for row in previews),
        "sequence": {
            "multi_step_decisions": stability["multi_step_decisions"],
            "changed_after_first_task": stability["changed_after_first_task"],
            "instability_rate": stability["instability_rate"],
        },
        "exclusion": {
            "decisions": len(exclusions),
            "with_ready_gt_3": sum(
                1 for row in exclusions if (row["ready_total"] or 0) > 3
            ),
            "with_ready_not_evaluated": sum(
                1 for row in exclusions if (row["ready_not_evaluated"] or 0) > 0
            ),
            "ready_not_evaluated_total": sum(
                row["ready_not_evaluated"] or 0 for row in exclusions
            ),
            "top3_saturated": sum(
                1 for row in exclusions if row["considered_count"] == TOP_N
            ),
            "active_occupied_slot": sum(row["active_occupied_slot"] for row in exclusions),
            "with_stranded_not_considered": sum(
                1 for row in exclusions if row["stranded_not_considered"]
            ),
            "excluded_then_chosen_within_two": sum(
                len(row["excluded_then_chosen_within_two"]) for row in exclusions
            ),
            "no_resolve_only_candidate": sum(
                1 for row in exclusions if not row["has_resolve_only_candidate"]
            ),
        },
        "horizon": {
            "mode_counts": {
                mode: sum(row["mode"] == mode for row in exclusions)
                for mode in ("advance_feasible", "advance_blocked", "coverage_complete")
            },
            # A multi-step choice is only reachable in "advance_feasible"; the other
            # two modes compare resolve-only prefixes, where every extra task only
            # adds positive cost, so the argmin is always a one-task plan.
            "effective_steps_by_mode": {
                mode: {
                    str(steps): sum(
                        row["mode"] == mode and row["effective_resolve_steps"] == steps
                        for row in exclusions
                    )
                    for steps in sorted({row["effective_resolve_steps"] for row in exclusions})
                }
                for mode in ("advance_feasible", "advance_blocked", "coverage_complete")
            },
            "blocked_without_required_lower_ge_3": sum(
                row["mode"] == "advance_blocked" and row["required_lower_size"] < 3
                for row in exclusions
            ),
        },
        "travel": _travel_share(decoded),
        "second_step_preview": _second_step_preview(decisions),
        "retrace_actions": sum(
            1 for action in walked["actions"] if action["local_leg_retrace"]
        ),
        "macro_backward_actions": sum(
            1 for action in walked["actions"] if action["macro_backward_movement"]
        ),
    }
    tables = {
        "decisions": exclusions,
        "resolves": decoded,
        "stability": stability["rows"],
        "previews": previews,
    }
    return {"summary": summary, "tables": tables}


def _write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    fieldnames: list[str] = []
    for row in rows:
        for key in row:
            if key not in fieldnames:
                fieldnames.append(key)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path, help="candidate-038 sweep log (.jsonl or .jsonl.gz)")
    parser.add_argument("--policy", default=DEFAULT_POLICY)
    parser.add_argument("--seeds", default="", help="comma-separated scenario seeds; default all")
    parser.add_argument("--out-dir", type=Path, default=Path("task3/results/tables"))
    args = parser.parse_args()

    metadata, cases = _load(args.input, args.policy)
    physical = _physical(metadata)
    wanted = {int(value) for value in args.seeds.split(",") if value.strip()}
    if wanted:
        cases = [case for case in cases if int(case["scenario_seed"]) in wanted]

    decision_rows: list[dict[str, Any]] = []
    resolve_rows: list[dict[str, Any]] = []
    stability_rows: list[dict[str, Any]] = []
    summaries: list[dict[str, Any]] = []
    for case in cases:
        result = _case_summary(case, physical, args.policy)
        summaries.append(result["summary"])
        for key, bucket in (
            ("decisions", decision_rows),
            ("resolves", resolve_rows),
            ("stability", stability_rows),
        ):
            for row in result["tables"][key]:
                bucket.append({"seed": result["summary"]["seed"], **row})

    _write_csv(args.out_dir / "038_sequence_decision_trace.csv", decision_rows)
    _write_csv(args.out_dir / "038_resolve_preview_error.csv", resolve_rows)
    _write_csv(args.out_dir / "038_sequence_plan_stability.csv", stability_rows)
    print(json.dumps(summaries, ensure_ascii=False, indent=2, default=str))


if __name__ == "__main__":
    main()
