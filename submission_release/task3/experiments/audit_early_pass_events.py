"""Classify candidate-020 early-pass events from action-preserving audit runs."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
from typing import Any

import numpy as np


EARLY_PASS_RADIUS_M = 300.0


def _load(path: Path, policy: str) -> list[dict[str, Any]]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        rows = [json.loads(line) for line in handle]
    return sorted(
        (row for row in rows if row.get("policy") == policy),
        key=lambda row: row["scenario_seed"],
    )


def _route_and_clear_indices(
    actions: list[dict[str, Any]],
) -> tuple[list[np.ndarray], dict[int, int]]:
    route = [np.zeros(2, float)]
    clear_indices: dict[int, int] = {}
    for action in actions:
        if action.get("movement_s", 0.0) > 0.0:
            route.append(np.asarray(action["position"], float))
        response = action.get("response", {})
        if action.get("path") == "/clear" and response.get("clear_result") == "success":
            clear_indices[int(action["channel"])] = len(route) - 1
    return route, clear_indices


def _route_audits(
    diagnostics: list[dict[str, Any]], route: list[np.ndarray]
) -> list[dict[str, Any] | None]:
    audits = [dict(item) for item in diagnostics if item.get("type") == "scheduler_audit"]
    decisions = [item for item in diagnostics if item.get("type") == "decision"]
    if len(audits) != len(decisions):
        raise ValueError("scheduler audit and decision counts differ")
    if not audits or not np.allclose(audits[0]["current_position"], route[0]):
        raise ValueError("first scheduler audit is not at the route origin")

    for audit, decision in zip(audits, decisions):
        audit["chosen_position"] = decision["position"]

    mapped: list[dict[str, Any] | None] = [audits[0]]
    reconstructed = [np.asarray(audits[0]["current_position"], float)]
    for index, (audit, decision) in enumerate(zip(audits, decisions)):
        current = np.asarray(audit["current_position"], float)
        destination = np.asarray(decision["position"], float)
        if float(np.linalg.norm(destination - current)) <= 1e-9:
            continue
        reconstructed.append(destination)
        next_audit = audits[index + 1] if index + 1 < len(audits) else None
        if next_audit is not None and not np.allclose(
            next_audit["current_position"], destination
        ):
            raise ValueError("scheduler audit does not follow its chosen destination")
        mapped.append(next_audit)
    if len(reconstructed) != len(route) or not np.allclose(reconstructed, route):
        raise ValueError("diagnostic decisions do not reproduce the action route")
    return mapped


def _first_early_pass(
    route: list[np.ndarray], source: np.ndarray, clear_index: int
) -> tuple[int, float, int, float] | None:
    distances = [float(np.linalg.norm(point - source)) for point in route[:clear_index]]
    for entry_index, entry_distance in enumerate(distances):
        if entry_distance >= EARLY_PASS_RADIUS_M:
            continue
        exit_index = next(
            (
                index for index in range(entry_index + 1, len(distances))
                if distances[index] >= EARLY_PASS_RADIUS_M
            ),
            None,
        )
        if exit_index is not None:
            departure_index = exit_index - 1
            return (
                entry_index,
                entry_distance,
                departure_index,
                distances[departure_index],
            )
    return None


def audit_row(
    seed: int,
    channel: int,
    source: np.ndarray,
    route: list[np.ndarray],
    clear_index: int,
    entry_index: int,
    entry_distance: float,
    pass_index: int,
    pass_distance: float,
    audit: dict[str, Any],
    low_detour_limit_m: float,
    clear_threshold_m: float,
) -> dict[str, Any]:
    snapshot = next(
        item for item in audit["channel_snapshots"] if item["channel"] == channel
    )
    candidates = [
        item for item in audit["local_candidates"] if item["channel"] == channel
    ]
    candidate = min(candidates, key=lambda item: item["score_s"], default=None)
    current = np.asarray(audit["current_position"], float)
    chosen = np.asarray(audit["chosen_position"], float)
    chosen_moves_away = float(np.linalg.norm(chosen - source)) > pass_distance + 1e-9
    delta_route_m = None
    route_reference = ""
    if candidate is not None:
        delta_route_m = candidate["route_insertion_delta_m"]
        route_reference = "next_coverage"
        if delta_route_m is None:
            candidate_point = np.asarray(candidate["position"], float)
            delta_route_m = float(
                np.linalg.norm(candidate_point - current)
                + np.linalg.norm(chosen - candidate_point)
                - np.linalg.norm(chosen - current)
            )
            route_reference = "chosen_action_no_coverage"

    classification: str
    b_reason = ""
    c_reason = ""
    if snapshot["status"] == "unknown":
        classification = "A"
    elif not candidates:
        classification = "B"
        if audit["chosen_source"] == "coverage_forced":
            b_reason = "other"
        elif not snapshot["in_local_shortlist"]:
            b_reason = "outside_local_shortlist"
        else:
            b_reason = "no_local_candidate"
    else:
        assert delta_route_m is not None
        target_action_deferred = (
            audit["chosen_kind"] == "SEARCH" or audit["chosen_channel"] != channel
        )
        if (
            delta_route_m <= low_detour_limit_m
            and target_action_deferred
            and chosen_moves_away
        ):
            classification = "D"
        else:
            classification = "C"
            c_reason = (
                "high_route_detour"
                if delta_route_m > low_detour_limit_m
                else "target_candidate_selected"
            )

    expected_radius = (
        candidate["candidate_expected_radius_m"]
        if candidate is not None and candidate["kind"] == "LOCALIZE" else None
    )
    next_coverage = audit["coverage_next_position"]
    candidate_position = candidate["position"] if candidate is not None else None
    chosen_position = audit["chosen_position"]
    return {
        "seed": seed,
        "channel": channel,
        "first_entry_route_point": entry_index + 1,
        "first_entry_distance_m": entry_distance,
        "route_point": pass_index + 1,
        "clear_route_point": clear_index + 1,
        "distance_to_true_source_m": pass_distance,
        "current_x_m": current[0],
        "current_y_m": current[1],
        "next_coverage_x_m": next_coverage[0] if next_coverage is not None else None,
        "next_coverage_y_m": next_coverage[1] if next_coverage is not None else None,
        "channel_status": snapshot["status"].upper(),
        "certificate_radius_m": snapshot["certificate_radius_m"],
        "bearing_count": snapshot["bearing_count"],
        "possible_count": snapshot["possible_count"],
        "in_local_shortlist": snapshot["in_local_shortlist"],
        "candidate_kind": candidate["kind"] if candidate is not None else None,
        "candidate_x_m": candidate_position[0] if candidate_position is not None else None,
        "candidate_y_m": candidate_position[1] if candidate_position is not None else None,
        "delta_route_m": delta_route_m,
        "route_reference": route_reference,
        "current_certificate_radius_m": snapshot["certificate_radius_m"],
        "candidate_expected_radius_m": expected_radius,
        "clear_threshold_m": clear_threshold_m if expected_radius is not None else None,
        "expected_clearable_after_measurement": (
            expected_radius <= clear_threshold_m if expected_radius is not None else None
        ),
        "chosen_kind": audit["chosen_kind"],
        "chosen_channel": audit["chosen_channel"],
        "chosen_x_m": chosen_position[0],
        "chosen_y_m": chosen_position[1],
        "chosen_source": audit["chosen_source"],
        "chosen_moves_away": chosen_moves_away,
        "classification": classification,
        "b_reason": b_reason,
        "c_reason": c_reason,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("input", type=Path)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--policy", default="candidate_020_grid5_center_approach"
    )
    parser.add_argument("--expected-events", type=int, default=33)
    args = parser.parse_args()

    output: list[dict[str, Any]] = []
    for record in _load(args.input, args.policy):
        route, clear_indices = _route_and_clear_indices(record["actions"])
        route_audits = _route_audits(record["result"]["diagnostics"], route)
        sources = {
            int(item["channel"]): np.asarray(item["position"], float)
            for item in record["sources"]
        }
        low_detour_limit_m = float(record["planner"]["route_insert_limit_m"])
        clear_threshold_m = 20.0 - float(record["planner"]["clear_margin_m"])
        for channel, source in sources.items():
            early_pass = _first_early_pass(
                route, source, clear_indices[channel]
            )
            if early_pass is None:
                continue
            entry_index, entry_distance, pass_index, pass_distance = early_pass
            audit = route_audits[pass_index]
            if audit is None:
                raise ValueError("early-pass route point has no following scheduler decision")
            output.append(audit_row(
                int(record["scenario_seed"]), channel, source, route,
                clear_indices[channel], entry_index, entry_distance,
                pass_index, pass_distance, audit,
                low_detour_limit_m, clear_threshold_m,
            ))

    if len(output) != args.expected_events:
        raise ValueError(f"expected {args.expected_events} events, found {len(output)}")
    output.sort(key=lambda row: (row["seed"], row["route_point"], row["channel"]))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(output[0]))
        writer.writeheader()
        writer.writerows(output)

    counts = {
        label: sum(row["classification"] == label for row in output)
        for label in "ABCD"
    }
    b_reasons = {
        reason: sum(row["b_reason"] == reason for row in output)
        for reason in ("outside_local_shortlist", "no_local_candidate", "other")
    }
    c_reasons = {
        reason: sum(row["c_reason"] == reason for row in output)
        for reason in ("high_route_detour", "target_candidate_selected")
    }
    deltas = np.asarray([
        row["delta_route_m"] for row in output
        if row["classification"] in {"C", "D"}
    ], float)
    localize = [row for row in output if row["candidate_kind"] == "LOCALIZE"]
    summary = {
        "events": len(output),
        "classification": counts,
        "b_reasons": b_reasons,
        "c_reasons": c_reasons,
        "delta_route_m": {
            "count": len(deltas),
            "median": float(np.median(deltas)),
            "p75": float(np.quantile(deltas, 0.75)),
            "max": float(np.max(deltas)),
        },
        "localize_candidate_count": len(localize),
        "expected_clearable_count": sum(
            row["expected_clearable_after_measurement"] is True for row in localize
        ),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
