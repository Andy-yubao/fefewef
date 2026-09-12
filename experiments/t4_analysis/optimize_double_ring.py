"""Paired local evaluation; simulator truth is read only after each strategy exits.

Run from the repository root, for example::

    python3 -B -m experiments.t4_analysis.optimize_double_ring \
        --strategy double_ring_optical_clear_probe --seed-start 10000 \
        --cases 20 --workers 4 --output-dir /tmp/t4-paired-check

Candidate configuration inherits the explicit baseline settings below. Override
individual settings with --strategy-config '{"route_length_slack_m": 80}'.
Every output directory must be new, including when a previous run was interrupted.
All failed runs retain their action logs. --regression-log-limit bounds the number
of paired regression logs; complete per-case metrics are retained regardless.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from datetime import datetime, timezone
import heapq
import json
import math
from pathlib import Path
import shlex
import statistics
import sys
from typing import Any

from experiments.t4_local.benchmark import run_local_case
from experiments.t4_local.engine import SimulatorConfig
from task4.strategies import STRATEGIES


BASELINE = "double_ring_optical_clear_probe"
BASELINE_CONFIG = {
    "grid_spacing": 600.0,
    "grid_half_extent": 1800.0,
    "lattice_spacing": 731.0,
    "replacement_distance_m": 550.0,
    "max_replaced_waypoints": 0,
    "early_clear_radius_m": 35.0,
    "route_length_slack_m": 100.0,
}
TIME_COMPONENTS = (
    "movement_time_s", "measure_time_s", "switch_time_s",
    "optical_time_s", "successful_clear_time_s",
)
METRICS = (
    "virtual_time_s", *TIME_COMPONENTS, "movement_distance_m", "measure_count",
    "no_signal_count", "optical_count", "directional_loss_count",
    "post_last_clear_time_s", "post_seen16_time_s", "unseen_measures_after_seen16",
    "wall_time_s",
)


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    low = math.floor(index)
    high = math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def _metric(values: list[float]) -> dict[str, float] | None:
    if not values:
        return None
    return {
        "minimum": min(values), "mean": statistics.fmean(values),
        "median": _quantile(values, 0.5), "p90": _quantile(values, 0.9),
        "p95": _quantile(values, 0.95), "p99": _quantile(values, 0.99),
        "maximum": max(values), "population_stddev": statistics.pstdev(values),
    }


def _rate(successes: int, total: int) -> dict[str, Any]:
    if not total:
        return {"count": successes, "total": total, "rate": None, "wilson_95": None}
    z = 1.959963984540054
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total**2)) / denominator
    return {
        "count": successes, "total": total, "rate": rate,
        "wilson_95": [max(0.0, center - radius), min(1.0, center + radius)],
    }


def _augment(row: dict[str, Any], detail: dict[str, Any], config: dict[str, Any]) -> None:
    simulator = SimulatorConfig(**config)
    row["switch_time_s"] = row["channel_switch_count"] * simulator.switch_time_s
    row["optical_time_s"] = row["optical_count"] * simulator.optical_time_s
    row["successful_clear_time_s"] = row["clear_success_count"] * simulator.clear_time_s
    row["cost_accounting_residual_s"] = row["virtual_time_s"] - sum(row[key] for key in TIME_COMPONENTS)
    if abs(row["cost_accounting_residual_s"]) > 1e-6:
        raise ValueError(f"time accounting mismatch for seed {row['seed']}: {row['cost_accounting_residual_s']}")
    row["all_cleared_within_6000"] = bool(row["all_cleared"] and row["virtual_time_s"] <= 6000.0)
    row["post_last_clear_time_s"] = (
        row["virtual_time_s"] - row["last_clear_time_s"] if row["all_cleared"] else None
    )
    seen = sorted(detail["truth"]["first_seen_time_s"].values())
    row["seen16_time_s"] = seen[15] if len(seen) == 16 else None
    row["post_seen16_time_s"] = (
        row["virtual_time_s"] - seen[15] if len(seen) == 16 else None
    )
    seen_channels: set[int] = set()
    after_limit = 0
    for action in detail["actions"]:
        if action["path"] != "/measure":
            continue
        channel = action["request"]["channel"]
        if len(seen_channels) == 16 and channel not in seen_channels:
            after_limit += 1
        if action["response"].get("measure_result") in {"near", "direction"}:
            seen_channels.add(channel)
    row["unseen_measures_after_seen16"] = after_limit if len(seen) == 16 else None


def _run_pair(arguments: tuple[Any, ...]) -> tuple[Any, ...]:
    seed, candidate, candidate_config, simulator_config = arguments
    baseline_row, baseline_detail = run_local_case(
        BASELINE, seed, BASELINE_CONFIG, simulator_config, keep_log=True,
    )
    candidate_row, candidate_detail = run_local_case(
        candidate, seed, candidate_config, simulator_config, keep_log=True,
    )
    # Check the actual generated instance, excluding the strategy-dependent outcome.
    def instance(detail: dict[str, Any]) -> list[dict[str, Any]]:
        return [{k: v for k, v in emitter.items() if k != "cleared"}
                for emitter in detail["truth"]["emitters"]]
    if instance(baseline_detail) != instance(candidate_detail):
        raise ValueError(f"paired simulator instances differ for seed {seed}")
    _augment(baseline_row, baseline_detail, simulator_config)
    _augment(candidate_row, candidate_detail, simulator_config)
    return baseline_row, baseline_detail, candidate_row, candidate_detail


def _groups(rows: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    return {
        "all": rows,
        "16_emitters": [row for row in rows if row["emitter_count"] == 16],
        "fewer_than_16": [row for row in rows if row["emitter_count"] < 16],
        **{f"count_{count}": [row for row in rows if row["emitter_count"] == count]
           for count in range(10, 17)},
    }


def _summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    cleared = [row for row in rows if row["all_cleared"]]
    return {
        "cases": len(rows),
        "all_clear": _rate(len(cleared), len(rows)),
        "all_clear_within_6000": _rate(sum(row["all_cleared_within_6000"] for row in rows), len(rows)),
        "aggregate_clear_rate": (
            sum(row["cleared_count"] for row in rows) / sum(row["emitter_count"] for row in rows)
            if rows else None
        ),
        "failure_seeds": [row["seed"] for row in rows if not row["all_cleared"]],
        "target_miss_seeds": [row["seed"] for row in rows if not row["all_cleared_within_6000"]],
        "successful_virtual_time_s": _metric([row["virtual_time_s"] for row in cleared]),
        "metrics": {key: _metric([float(row[key]) for row in rows if row[key] is not None])
                    for key in METRICS},
    }


def _compare(baseline: list[dict[str, Any]], candidate: list[dict[str, Any]]) -> dict[str, Any]:
    pairs = list(zip(baseline, candidate))
    if any(b["seed"] != c["seed"] for b, c in pairs) or len(baseline) != len(candidate):
        raise ValueError("comparison rows must be paired in seed order")
    both_clear = [(b, c) for b, c in pairs if b["all_cleared"] and c["all_cleared"]]
    return {
        "cases": len(pairs),
        "time_delta_convention": "candidate minus baseline; negative means faster",
        "deltas": {
            key: _metric([float(c[key]) - float(b[key]) for b, c in pairs
                          if b[key] is not None and c[key] is not None])
            for key in METRICS
        },
        "both_clear_cases": len(both_clear),
        "both_clear_virtual_time_delta_s": _metric([c["virtual_time_s"] - b["virtual_time_s"] for b, c in both_clear]),
        "both_clear_faster": sum(c["virtual_time_s"] < b["virtual_time_s"] - 1e-6 for b, c in both_clear),
        "both_clear_slower": sum(c["virtual_time_s"] > b["virtual_time_s"] + 1e-6 for b, c in both_clear),
        "new_failure_seeds": [c["seed"] for b, c in pairs if b["all_cleared"] and not c["all_cleared"]],
        "rescued_failure_seeds": [c["seed"] for b, c in pairs if not b["all_cleared"] and c["all_cleared"]],
        "gained_target_seeds": [c["seed"] for b, c in pairs if not b["all_cleared_within_6000"] and c["all_cleared_within_6000"]],
        "lost_target_seeds": [c["seed"] for b, c in pairs if b["all_cleared_within_6000"] and not c["all_cleared_within_6000"]],
    }


def _json(path: Path, value: Any) -> None:
    with path.open("x", encoding="utf-8") as handle:
        json.dump(value, handle, ensure_ascii=False, indent=2, allow_nan=False)
        handle.write("\n")


def _csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def _summary_markdown(summary: dict[str, Any]) -> str:
    lines = [f"# {summary['strategy']} 配对实验", "",
             "所有分层只用于运行后评价，不向策略提供真实源数。Wilson 95% 区间描述本地采样率，不是最坏情况保证。", "",
             "| 分层 | 案例 | 全清 | 全清且≤6000 | 均值(s) | P95(s) | P99(s) | 最大(s) |",
             "|---|---:|---:|---:|---:|---:|---:|---:|"]
    for name, group in summary["groups"].items():
        if not group["cases"]:
            continue
        metric = group["metrics"]["virtual_time_s"]
        lines.append(f"| {name} | {group['cases']} | {group['all_clear']['count']} | "
                     f"{group['all_clear_within_6000']['count']} | {metric['mean']:.2f} | "
                     f"{metric['p95']:.2f} | {metric['p99']:.2f} | {metric['maximum']:.2f} |")
    overall = summary["groups"]["all"]
    lines += ["", "平均时间分解（s）：", ""]
    lines += [f"- {key}: {overall['metrics'][key]['mean']:.2f}" for key in TIME_COMPONENTS]
    lines += ["", f"未全清种子：`{overall['failure_seeds']}`。", "",
              "总时包含未全清局；全清局单独统计、达标率区间及配置见 summary.json。"]
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--strategy", required=True, choices=sorted(STRATEGIES))
    parser.add_argument("--seed-start", type=int, default=0)
    parser.add_argument("--cases", type=int, default=100)
    parser.add_argument("--directional-probability", type=float, default=0.5)
    parser.add_argument("--emitter-count", type=int, choices=range(10, 17))
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--workers", type=int, default=1)
    parser.add_argument(
        "--regression-log-limit", type=int, default=5,
        help="retain full paired logs for the largest N time regressions (default: 5; 0 disables); all failure logs and per-case metrics are always kept",
    )
    configs = parser.add_mutually_exclusive_group()
    configs.add_argument("--strategy-config", help="JSON object of candidate overrides")
    configs.add_argument("--strategy-config-file", type=Path, help="JSON file containing candidate overrides")
    args = parser.parse_args()
    if args.cases < 1 or args.workers < 1 or args.seed_start < 0:
        parser.error("--cases and --workers must be positive; --seed-start must be nonnegative")
    if args.regression_log_limit < 0:
        parser.error("--regression-log-limit must be nonnegative")
    if not 0 <= args.directional_probability <= 1:
        parser.error("--directional-probability must be in [0, 1]")
    if args.output_dir.exists():
        parser.error(f"output directory already exists; choose a new path: {args.output_dir}")
    try:
        overrides = json.loads(args.strategy_config_file.read_text(encoding="utf-8")
                               if args.strategy_config_file else args.strategy_config or "{}")
        if not isinstance(overrides, dict):
            parser.error("candidate strategy configuration must be a JSON object")
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    candidate_config = BASELINE_CONFIG | overrides
    simulator_config = {"directional_probability": args.directional_probability}
    if args.emitter_count is not None:
        simulator_config |= {"min_emitters": args.emitter_count, "max_emitters": args.emitter_count}
    seeds = list(range(args.seed_start, args.seed_start + args.cases))
    args.output_dir.mkdir(parents=True, exist_ok=False)
    for name in ("baseline", "candidate", "regressions"):
        (args.output_dir / name).mkdir()
    manifest = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": shlex.join([sys.executable, "-B", "-m", "experiments.t4_analysis.optimize_double_ring", *sys.argv[1:]]),
        "seed_selection": "consecutive fixed seeds; this tool does not designate development or holdout status",
        "seeds": seeds, "workers": args.workers,
        "baseline": {"strategy": BASELINE, "strategy_config": BASELINE_CONFIG},
        "candidate": {"strategy": args.strategy, "strategy_config": candidate_config},
        "simulator_config": simulator_config,
        "regression_log_limit": args.regression_log_limit,
        "regression_log_rule": (
            "all failed runs keep full action logs; paired regression logs are retained only for the largest "
            "N candidate-minus-baseline time deltas among slower or lost-clearance cases; all per-case metrics remain"
        ),
    }
    _json(args.output_dir / "manifest.json", manifest)
    baseline_rows: list[dict[str, Any]] = []
    candidate_rows: list[dict[str, Any]] = []
    regression_rows: list[dict[str, Any]] = []
    regression_logs: list[tuple[float, int, dict[str, Any]]] = []
    arguments = [(seed, args.strategy, candidate_config, simulator_config) for seed in seeds]
    executor = ProcessPoolExecutor(max_workers=args.workers) if args.workers > 1 else None
    try:
        results = executor.map(_run_pair, arguments) if executor else map(_run_pair, arguments)
        for b, bd, c, cd in results:
            baseline_rows.append(b)
            candidate_rows.append(c)
            seed = b["seed"]
            for label, row, detail in (("baseline", b, bd), ("candidate", c, cd)):
                if not row["all_cleared"]:
                    _json(args.output_dir / label / f"failure_seed_{seed}.json", detail)
            delta = c["virtual_time_s"] - b["virtual_time_s"]
            lost_clearance = bool(b["all_cleared"] and not c["all_cleared"])
            regression = delta > 1e-6 or lost_clearance
            comparison_row = {
                "seed": seed, "emitter_count": b["emitter_count"],
                "directional_count": b["directional_count"],
                "baseline_all_cleared": b["all_cleared"], "candidate_all_cleared": c["all_cleared"],
                "baseline_virtual_time_s": b["virtual_time_s"], "candidate_virtual_time_s": c["virtual_time_s"],
                "virtual_time_delta_s": delta, "lost_clearance": lost_clearance,
                "lost_target": b["all_cleared_within_6000"] and not c["all_cleared_within_6000"],
                "is_regression": regression, "regression_log": None,
            }
            regression_rows.append(comparison_row)
            if regression and args.regression_log_limit:
                entry = (delta, seed, {"comparison": comparison_row, "baseline": bd, "candidate": cd})
                if len(regression_logs) < args.regression_log_limit:
                    heapq.heappush(regression_logs, entry)
                elif (delta, seed) > regression_logs[0][:2]:
                    heapq.heapreplace(regression_logs, entry)
            if len(baseline_rows) % 20 == 0 or len(baseline_rows) == len(seeds):
                print(f"completed {len(baseline_rows)}/{len(seeds)} paired cases", flush=True)
    finally:
        if executor:
            executor.shutdown(wait=True, cancel_futures=True)
    for _, seed, detail in sorted(regression_logs, reverse=True):
        detail["comparison"]["regression_log"] = f"regressions/seed_{seed}.json"
        _json(args.output_dir / "regressions" / f"seed_{seed}.json", detail)
    for label, rows in (("baseline", baseline_rows), ("candidate", candidate_rows)):
        summary = manifest[label] | {"simulator_config": simulator_config,
                                     "groups": {key: _summarize(group) for key, group in _groups(rows).items()}}
        folder = args.output_dir / label
        _csv(folder / "cases.csv", rows)
        _json(folder / "summary.json", summary)
        (folder / "summary.md").write_text(_summary_markdown(summary), encoding="utf-8")
    bg, cg = _groups(baseline_rows), _groups(candidate_rows)
    comparisons = {key: _compare(bg[key], cg[key]) for key in bg}
    comparison = {"baseline": manifest["baseline"], "candidate": manifest["candidate"],
                  "simulator_config": simulator_config, "groups": comparisons,
                  "regression_log_limit": args.regression_log_limit,
                  "regression_logs_saved": len(regression_logs),
                  "regressions": sorted([row for row in regression_rows if row["is_regression"]],
                                        key=lambda row: row["virtual_time_delta_s"], reverse=True)}
    _csv(args.output_dir / "paired_cases.csv", regression_rows)
    _json(args.output_dir / "comparison.json", comparison)
    lines = ["# 双环策略配对比较", "", "Δ=候选−基线；负数表示候选更快。源数分层只用于离线评价。", "",
             "| 分层 | 案例 | 均值Δ(s) | 双方全清均值Δ(s) | 更快/更慢 | 新增未全清 | 新增/损失6000达标 |",
             "|---|---:|---:|---:|---:|---:|---:|"]
    for key, group in comparisons.items():
        if not group["cases"]:
            continue
        both = group["both_clear_virtual_time_delta_s"]
        both_mean = f"{both['mean']:.2f}" if both else "n/a"
        lines.append(f"| {key} | {group['cases']} | {group['deltas']['virtual_time_s']['mean']:.2f} | "
                     f"{both_mean} | {group['both_clear_faster']}/{group['both_clear_slower']} | "
                     f"{len(group['new_failure_seeds'])} | {len(group['gained_target_seeds'])}/{len(group['lost_target_seeds'])} |")
    lines += ["", "均值可能包含未全清案例，须同时查看全清率与达标率。双方全清的时间差另行列出。", "",
              "完整配置与复现命令见 manifest.json；成本分解见各 summary.json；逐种子结果见 paired_cases.csv。", "",
              f"所有未全清局保留完整动作日志；候选更慢或损失全清的配对日志仅保留时间差最大的 {args.regression_log_limit} 例（本次 {len(regression_logs)} 例），见 regressions/。所有回归指标仍按时间差降序写入 comparison.json，未留完整日志者的 regression_log 为 null。"]
    (args.output_dir / "comparison.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    overall = comparisons["all"]
    print(json.dumps({
        "output_dir": str(args.output_dir), "cases": overall["cases"],
        "mean_time_delta_s": overall["deltas"]["virtual_time_s"]["mean"],
        "new_failure_seeds": overall["new_failure_seeds"],
        "gained_target_cases": len(overall["gained_target_seeds"]),
        "lost_target_cases": len(overall["lost_target_seeds"]),
        "baseline": {
            "mean_virtual_time_s": statistics.fmean(row["virtual_time_s"] for row in baseline_rows),
            "all_clear_cases": sum(row["all_cleared"] for row in baseline_rows),
            "target_cases": sum(row["all_cleared_within_6000"] for row in baseline_rows),
        },
        "candidate": {
            "mean_virtual_time_s": statistics.fmean(row["virtual_time_s"] for row in candidate_rows),
            "all_clear_cases": sum(row["all_cleared"] for row in candidate_rows),
            "target_cases": sum(row["all_cleared_within_6000"] for row in candidate_rows),
        },
    }, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
