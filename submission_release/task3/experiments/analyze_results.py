"""Summarize paired offline/practice results with case bootstrap intervals."""

from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


def read_rows(path: Path) -> list[dict]:
    opener = gzip.open if path.suffix == ".gz" else open
    with opener(path, "rt", encoding="utf-8") as handle:
        return [row for line in handle if (row := json.loads(line)).get("record_type") != "metadata"]


def interval(values: np.ndarray, rng: np.random.Generator, n_boot: int) -> tuple[float, float]:
    if not len(values):
        return np.nan, np.nan
    means = np.empty(n_boot)
    for i in range(n_boot):
        means[i] = np.mean(values[rng.integers(0, len(values), len(values))])
    return tuple(np.quantile(means, [0.025, 0.975]))


def summarize(rows: list[dict], n_boot: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed)
    output = []
    for policy in sorted({r["policy"] for r in rows}):
        selected = [r for r in rows if r["policy"] == policy]
        times = np.array([r["result"]["virtual_time_s"] for r in selected], float)
        averages = np.array([r["result"]["average_localize_clear_s"] for r in selected], float)
        ratios = np.array([r["result"]["clear_ratio"] for r in selected], float)
        walls = np.array([r["result"]["wall_runtime_s"] for r in selected], float)
        actions = np.array([r["result"]["action_count"] for r in selected], float)
        delays = np.array([r["result"]["mean_found_to_clear_s"] for r in selected], float)
        breakdown = {
            key: np.array([r["result"]["time_breakdown"][key] for r in selected], float)
            for key in ("movement_s", "switching_s", "measurement_s", "optical_s", "laser_s")
        }
        failed_clears = np.array([
            sum(d.get("type") in ("fallback_miss", "unexpected_clear_failure")
                for d in r["result"]["diagnostics"])
            for r in selected
        ], float)
        lo, hi = interval(times, rng, n_boot)
        alo, ahi = interval(averages, rng, n_boot)
        output.append({
            "policy": policy, "n": len(selected), "full_clear_rate": float(np.mean(ratios == 1.0)),
            "clear_ratio_mean": float(np.mean(ratios)), "virtual_mean_s": float(np.mean(times)),
            "virtual_median_s": float(np.median(times)), "virtual_p90_s": float(np.quantile(times, .90)),
            "virtual_p95_s": float(np.quantile(times, .95)), "virtual_max_s": float(np.max(times)),
            "virtual_mean_ci_low_s": lo, "virtual_mean_ci_high_s": hi,
            "average_per_clear_mean_s": float(np.mean(averages)),
            "average_per_clear_median_s": float(np.median(averages)),
            "average_per_clear_p90_s": float(np.quantile(averages, .90)),
            "average_per_clear_p95_s": float(np.quantile(averages, .95)),
            "average_per_clear_max_s": float(np.max(averages)),
            "average_per_clear_mean_ci_low_s": alo, "average_per_clear_mean_ci_high_s": ahi,
            "wall_mean_s": float(np.mean(walls)), "wall_p95_s": float(np.quantile(walls, .95)),
            "wall_max_s": float(np.max(walls)),
            "action_count_mean": float(np.mean(actions)),
            "found_to_clear_mean_s": float(np.mean(delays)),
            "failed_clear_count_mean": float(np.mean(failed_clears)),
            "coverage_complete_rate": float(np.mean([
                len(r["result"]["coverage_completed"]) == 7 for r in selected
            ])),
            **{f"{key}_mean": float(np.mean(value)) for key, value in breakdown.items()},
        })
    return output


def write_csv(path: Path, rows: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def paired(rows: list[dict], baseline: str, n_boot: int, seed: int) -> list[dict]:
    rng = np.random.default_rng(seed + 1)
    lookup = {(r["scenario_id"], r["policy"]): r for r in rows}
    scenarios = sorted({r["scenario_id"] for r in rows})
    result = []
    for policy in sorted({r["policy"] for r in rows} - {baseline}):
        diff = np.array([lookup[(s, baseline)]["result"]["virtual_time_s"]
                         - lookup[(s, policy)]["result"]["virtual_time_s"] for s in scenarios])
        lo, hi = interval(diff, rng, n_boot)
        result.append({"baseline": baseline, "policy": policy, "n": len(diff),
                       "mean_time_saved_s": float(np.mean(diff)),
                       "median_time_saved_s": float(np.median(diff)),
                       "win_rate": float(np.mean(diff > 0)), "mean_ci_low_s": lo, "mean_ci_high_s": hi})
    return result


def make_figures(rows: list[dict], output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    policies = sorted({r["policy"] for r in rows})
    values = {p: np.array([r["result"]["virtual_time_s"] for r in rows if r["policy"] == p]) for p in policies}
    fig, ax = plt.subplots(figsize=(10, 5))
    ax.boxplot([values[p] for p in policies], tick_labels=policies, showfliers=False)
    ax.set_ylabel("Total virtual time (s)")
    ax.tick_params(axis="x", rotation=35)
    fig.tight_layout()
    fig.savefig(output_dir / "offline_virtual_time_boxplot.png", dpi=180)
    plt.close(fig)
    fig, ax = plt.subplots(figsize=(8, 5))
    for p in policies:
        x = np.sort(values[p]); y = np.arange(1, len(x) + 1) / len(x)
        ax.plot(x, y, label=p)
    ax.set_xlabel("Total virtual time (s)"); ax.set_ylabel("Empirical CDF")
    ax.legend(fontsize=7)
    fig.tight_layout(); fig.savefig(output_dir / "offline_virtual_time_ecdf.png", dpi=180)
    plt.close(fig)


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input", type=Path, default=Path("task3/results/raw/offline_runs.jsonl.gz"))
    p.add_argument("--tables", type=Path, default=Path("task3/results/tables"))
    p.add_argument("--figures", type=Path, default=Path("task3/results/figures"))
    p.add_argument("--bootstrap", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20260911)
    p.add_argument("--baseline", default="B0_two_stage")
    return p


def main() -> None:
    args = parser().parse_args()
    rows = read_rows(args.input)
    if not rows:
        raise SystemExit("no experiment rows")
    summary = summarize(rows, args.bootstrap, args.seed)
    available = {row["policy"] for row in rows}
    if args.baseline not in available:
        raise SystemExit(f"baseline policy not present: {args.baseline}")
    comparisons = paired(rows, args.baseline, args.bootstrap, args.seed)
    write_csv(args.tables / "offline_strategy_summary.csv", summary)
    write_csv(args.tables / "offline_paired_vs_two_stage.csv", comparisons)
    make_figures(rows, args.figures)
    failures = [r for r in rows if not r["result"]["success"] or r["result"]["clear_ratio"] != 1.0]
    print(json.dumps({"rows": len(rows), "cases": len({r['scenario_id'] for r in rows}),
                      "failures": len(failures)}, ensure_ascii=False))
    if failures:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
