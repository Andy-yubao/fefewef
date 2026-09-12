from __future__ import annotations

import csv
from dataclasses import asdict
import json
from pathlib import Path
import statistics
import time
from typing import Any

from .engine import LocalSimulator, SimulatorConfig
from task4.client import InProcessClient
from task4.strategies import make_strategy


def run_local_case(
    strategy_name: str,
    seed: int,
    strategy_config: dict[str, Any] | None = None,
    simulator_config: dict[str, Any] | None = None,
    keep_log: bool = False,
):
    simulator = LocalSimulator(SimulatorConfig(seed=seed, **(simulator_config or {})))
    client = InProcessClient(simulator, simulator.config.robot_id)
    strategy = make_strategy(strategy_name, **(strategy_config or {}))
    started = time.perf_counter()
    result = strategy.run(client)
    wall = time.perf_counter() - started
    truth = simulator.truth_summary()
    stats = truth["stats"]
    row = {
        "strategy": strategy_name,
        "seed": seed,
        "emitter_count": truth["emitter_count"],
        "directional_count": truth["directional_count"],
        "cleared_count": truth["cleared_count"],
        "clear_rate": truth["clear_rate"],
        "all_cleared": truth["all_cleared"],
        "average_localize_clear_time_s": truth["virtual_time_s"] / truth["cleared_count"] if truth["cleared_count"] else None,
        "virtual_time_s": truth["virtual_time_s"],
        "movement_time_s": stats["movement_time_s"],
        "movement_distance_m": stats["movement_distance_m"],
        "measure_time_s": stats["measure_time_s"],
        "measure_count": stats["measure_count"],
        "no_signal_count": stats["no_signal_count"],
        "no_signal_rate": stats["no_signal_count"] / stats["measure_count"] if stats["measure_count"] else None,
        "direction_count": stats["direction_count"],
        "near_count": stats["near_count"],
        "channel_switch_count": stats["channel_switch_count"],
        "optical_count": stats["optical_count"],
        "clear_attempt_count": stats["clear_attempt_count"],
        "clear_success_count": stats["clear_success_count"],
        "directional_loss_count": truth["directional_loss_count"],
        "directional_reacquisition_count": truth["directional_reacquisition_count"],
        "mean_first_seen_time_s": statistics.fmean(truth["first_seen_time_s"].values()) if truth["first_seen_time_s"] else None,
        "max_first_seen_time_s": max(truth["first_seen_time_s"].values()) if truth["first_seen_time_s"] else None,
        "first_clear_time_s": truth["first_clear_time_s"],
        "last_clear_time_s": truth["last_clear_time_s"],
        "measurements_before_first_clear": truth["measurements_before_first_clear"],
        "wall_time_s": wall,
        "local_check_count": result.diagnostics.get("local_check_count"),
        "local_detour_distance_m": result.diagnostics.get("local_detour_distance_m"),
        "main_skeleton_distance_m": result.diagnostics.get("main_skeleton_distance_m"),
        "main_leg_distance_m": result.diagnostics.get("main_leg_distance_m"),
        "settlement_check_distance_m": result.diagnostics.get("settlement_check_distance_m"),
        "settlement_clear_distance_m": result.diagnostics.get("settlement_clear_distance_m"),
        "residual_check_distance_m": result.diagnostics.get("residual_check_distance_m"),
        "residual_clear_distance_m": result.diagnostics.get("residual_clear_distance_m"),
        "unseen_source_count": sum(
            int(emitter["channel"]) not in result.seen_channels
            for emitter in truth["emitters"]
        ),
        "unresolved_seen_source_count": sum(
            int(emitter["channel"]) in result.seen_channels and not emitter["cleared"]
            for emitter in truth["emitters"]
        ),
    }
    detail = {"metrics": row, "strategy_result": asdict(result), "truth": truth}
    if keep_log:
        detail["actions"] = client.actions
    return row, detail


def _quantile(values: list[float], q: float) -> float:
    ordered = sorted(values)
    if not ordered:
        return float("nan")
    index = (len(ordered) - 1) * q
    lo, hi = int(index), min(int(index) + 1, len(ordered) - 1)
    if lo == hi:
        return ordered[lo]
    return ordered[lo] * (hi - index) + ordered[hi] * (index - lo)


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    virtual = [float(r["virtual_time_s"]) for r in rows]
    avg_clear = [float(r["average_localize_clear_time_s"]) for r in rows if r["average_localize_clear_time_s"] is not None]
    failures = [int(r["seed"]) for r in rows if not r["all_cleared"]]
    return {
        "strategy": rows[0]["strategy"] if rows else None,
        "cases": len(rows),
        "aggregate_clear_rate": sum(r["cleared_count"] for r in rows) / sum(r["emitter_count"] for r in rows),
        "all_clear_case_rate": sum(bool(r["all_cleared"]) for r in rows) / len(rows),
        "mean_average_localize_clear_time_s": statistics.fmean(avg_clear),
        "p95_average_localize_clear_time_s": _quantile(avg_clear, 0.95),
        "mean_virtual_time_s": statistics.fmean(virtual),
        "p50_virtual_time_s": _quantile(virtual, 0.5),
        "p90_virtual_time_s": _quantile(virtual, 0.9),
        "p95_virtual_time_s": _quantile(virtual, 0.95),
        "max_virtual_time_s": max(virtual),
        "mean_movement_distance_m": statistics.fmean(float(r["movement_distance_m"]) for r in rows),
        "mean_movement_time_s": statistics.fmean(float(r["movement_time_s"]) for r in rows),
        "mean_measure_time_s": statistics.fmean(float(r["measure_time_s"]) for r in rows),
        "mean_measure_count": statistics.fmean(float(r["measure_count"]) for r in rows),
        "mean_no_signal_count": statistics.fmean(float(r["no_signal_count"]) for r in rows),
        "mean_no_signal_rate": statistics.fmean(float(r["no_signal_rate"]) for r in rows if r["no_signal_rate"] is not None),
        "mean_direction_count": statistics.fmean(float(r["direction_count"]) for r in rows),
        "mean_channel_switch_count": statistics.fmean(float(r["channel_switch_count"]) for r in rows),
        "mean_optical_count": statistics.fmean(float(r["optical_count"]) for r in rows),
        "mean_clear_attempt_count": statistics.fmean(float(r["clear_attempt_count"]) for r in rows),
        "mean_local_check_count": statistics.fmean(float(r["local_check_count"]) for r in rows if r["local_check_count"] is not None) if any(r["local_check_count"] is not None for r in rows) else None,
        "mean_local_detour_distance_m": statistics.fmean(float(r["local_detour_distance_m"]) for r in rows if r["local_detour_distance_m"] is not None) if any(r["local_detour_distance_m"] is not None for r in rows) else None,
        "mean_main_skeleton_distance_m": statistics.fmean(float(r["main_skeleton_distance_m"]) for r in rows if r["main_skeleton_distance_m"] is not None) if any(r["main_skeleton_distance_m"] is not None for r in rows) else None,
        "mean_main_leg_distance_m": statistics.fmean(float(r["main_leg_distance_m"]) for r in rows if r["main_leg_distance_m"] is not None) if any(r["main_leg_distance_m"] is not None for r in rows) else None,
        "mean_settlement_check_distance_m": statistics.fmean(float(r["settlement_check_distance_m"]) for r in rows if r["settlement_check_distance_m"] is not None) if any(r["settlement_check_distance_m"] is not None for r in rows) else None,
        "mean_settlement_clear_distance_m": statistics.fmean(float(r["settlement_clear_distance_m"]) for r in rows if r["settlement_clear_distance_m"] is not None) if any(r["settlement_clear_distance_m"] is not None for r in rows) else None,
        "mean_residual_check_distance_m": statistics.fmean(float(r["residual_check_distance_m"]) for r in rows if r["residual_check_distance_m"] is not None) if any(r["residual_check_distance_m"] is not None for r in rows) else None,
        "mean_residual_clear_distance_m": statistics.fmean(float(r["residual_clear_distance_m"]) for r in rows if r["residual_clear_distance_m"] is not None) if any(r["residual_clear_distance_m"] is not None for r in rows) else None,
        "mean_unseen_source_count": statistics.fmean(float(r["unseen_source_count"]) for r in rows),
        "mean_unresolved_seen_source_count": statistics.fmean(float(r["unresolved_seen_source_count"]) for r in rows),
        "mean_directional_loss_count": statistics.fmean(float(r["directional_loss_count"]) for r in rows),
        "mean_directional_reacquisition_count": statistics.fmean(float(r["directional_reacquisition_count"]) for r in rows),
        "mean_first_seen_time_s": statistics.fmean(float(r["mean_first_seen_time_s"]) for r in rows if r["mean_first_seen_time_s"] is not None),
        "mean_first_clear_time_s": statistics.fmean(float(r["first_clear_time_s"]) for r in rows if r["first_clear_time_s"] is not None),
        "mean_measurements_before_first_clear": statistics.fmean(float(r["measurements_before_first_clear"]) for r in rows if r["measurements_before_first_clear"] is not None),
        "mean_wall_time_s": statistics.fmean(float(r["wall_time_s"]) for r in rows),
        "total_wall_time_s": sum(float(r["wall_time_s"]) for r in rows),
        "failure_seeds": failures,
    }


def run_batch(
    strategy_name: str,
    seeds: list[int],
    output_dir: Path,
    strategy_config: dict[str, Any] | None = None,
    simulator_config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    output_dir.mkdir(parents=True, exist_ok=True)
    rows = []
    first_seen_rows = []
    for seed in seeds:
        row, detail = run_local_case(strategy_name, seed, strategy_config, simulator_config, keep_log=False)
        rows.append(row)
        emitter_by_channel = {e["channel"]: e for e in detail["truth"]["emitters"]}
        for channel, first_seen in detail["truth"]["first_seen_time_s"].items():
            emitter = emitter_by_channel[int(channel)]
            first_seen_rows.append({
                "strategy": strategy_name,
                "seed": seed,
                "channel": channel,
                "first_seen_time_s": first_seen,
                "directional": emitter["directional"],
            })
        if not row["all_cleared"]:
            (output_dir / f"failure_seed_{seed}.json").write_text(json.dumps(detail, ensure_ascii=False, indent=2), encoding="utf-8")
    with (output_dir / "cases.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    with (output_dir / "first_seen.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=["strategy", "seed", "channel", "first_seen_time_s", "directional"])
        writer.writeheader()
        writer.writerows(first_seen_rows)
    summary = summarize(rows)
    summary["seed_start"] = min(seeds)
    summary["seed_end"] = max(seeds)
    summary["strategy_config"] = strategy_config or {}
    summary["simulator_config"] = simulator_config or {}
    (output_dir / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding="utf-8")
    markdown = "# T4 本地批量实验汇总\n\n" + "\n".join(f"- {key}: `{value}`" for key, value in summary.items()) + "\n"
    (output_dir / "summary.md").write_text(markdown, encoding="utf-8")
    return summary
