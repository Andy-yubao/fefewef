"""Aggregate GUI-annotated practice summaries without inventing missing totals."""

from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

import numpy as np


def main() -> None:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--input-dir", type=Path, default=Path("task3/results/raw/practice"))
    p.add_argument("--output", type=Path, default=Path("task3/results/tables/practice_summary.csv"))
    p.add_argument("--bootstrap", type=int, default=2000)
    p.add_argument("--seed", type=int, default=20260911)
    args = p.parse_args()
    rows = [json.loads(path.read_text(encoding="utf-8")) for path in sorted(args.input_dir.glob("*.summary.json"))]
    valid = [r for r in rows if r.get("success") is True and r.get("known_total") is not None]
    if not valid:
        raise SystemExit("no successful practice summary with a GUI-annotated target total")
    times = np.array([r["virtual_time_s"] for r in valid], float)
    avgs = np.array([r["average_localize_clear_s"] for r in valid], float)
    ratios = np.array([r["clear_ratio"] for r in valid], float)
    rng = np.random.default_rng(args.seed)
    boot = np.array([np.mean(times[rng.integers(0, len(times), len(times))]) for _ in range(args.bootstrap)])
    row = {
        "n": len(valid), "full_clear_rate": float(np.mean(ratios == 1.0)),
        "clear_ratio_mean": float(np.mean(ratios)), "virtual_mean_s": float(np.mean(times)),
        "virtual_median_s": float(np.median(times)), "virtual_p90_s": float(np.quantile(times, .90)),
        "virtual_p95_s": float(np.quantile(times, .95)), "virtual_max_s": float(np.max(times)),
        "virtual_mean_ci_low_s": float(np.quantile(boot, .025)),
        "virtual_mean_ci_high_s": float(np.quantile(boot, .975)),
        "average_per_clear_mean_s": float(np.mean(avgs)),
        "wall_runtime_mean_s": float(np.mean([r["wall_runtime_s"] for r in valid])),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(row)); writer.writeheader(); writer.writerow(row)
    print(json.dumps({"valid": len(valid), "ignored_or_unannotated": len(rows) - len(valid), **row},
                     ensure_ascii=False))


if __name__ == "__main__":
    main()
