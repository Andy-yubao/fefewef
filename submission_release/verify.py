"""Independent verification using only the formal task implementations."""
from __future__ import annotations

import argparse
import csv
import gzip
import json
import math
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parent


def check_q1() -> None:
    sys.path.insert(0, str(ROOT / "task1"))
    from src.q1 import (  # type: ignore[import-not-found]
        BearingObservation, Point, clip_polygon_with_disk,
        clipped_region_diameter, locate_polygon,
        minimum_enclosing_circle_polygon,
    )
    observations = [
        BearingObservation(Point(713.63, 1193.59), 235.05529),
        BearingObservation(Point(-939.50, 362.10), 356.78364),
        BearingObservation(Point(590.63, -611.06), 117.85767),
    ]
    polygon = locate_polygon(observations)
    region = clip_polygon_with_disk(polygon)
    diameter = clipped_region_diameter(region).distance
    circle = minimum_enclosing_circle_polygon(polygon)
    assert len(polygon) == 6
    assert abs(diameter - 43.3485304667) < 1e-6
    assert abs(2 * circle.radius - 46.196233962) < 1e-6


def read_csv(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def check_q2() -> tuple[float, float]:
    rows = read_csv(ROOT / "task2/results/raw/evaluations.csv")
    sample = [float(row["diameter_m"]) for row in rows if row["strategy"] == "gdop_mean"]
    assert len(sample) == 10_000
    current = sum(sample) / len(sample)
    published = float(next(
        row["diameter_mean"] for row in read_csv(ROOT / "task2/results/tables/strategy_summary.csv")
        if row["strategy"] == "gdop_mean"
    ))
    return current, published


def check_q3() -> None:
    path = ROOT / "results/candidate057_concurrency100_seed20261310.jsonl.gz"
    records = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            row = json.loads(line)
            if row.get("record_type") != "metadata":
                records.append(row)
    assert len(records) == 100
    assert sum(bool(row["result"]["success"]) for row in records) == 100
    assert sum(int(row["result"]["known_total"]) for row in records) == 1291
    total_time = sum(float(row["result"]["virtual_time_s"]) for row in records)
    total_sources = sum(int(row["source_count"]) for row in records)
    assert abs(total_time / total_sources - 256.0050674046) < 1e-9


def check_q4() -> None:
    from task4.search_patterns import double_ring_cover
    assert len(double_ring_cover()) == 25
    worst = math.sqrt(50**2 + 36**2 - 2 * 50 * 36 * math.cos(math.radians(18)))
    assert abs(worst - 19.2924) < 1e-4
    base = ROOT / "experiments/t4_analysis/outputs/toward6000_v2"
    folders = ("holdout_omni100", "holdout_n10_mixed100", "holdout_mixed300",
               "holdout_directional300", "holdout_n16_mixed200")
    candidate_cases = candidate_all_clear = 0
    for folder in folders:
        rows = read_csv(base / folder / "candidate/cases.csv")
        candidate_cases += len(rows)
        candidate_all_clear += sum(row["all_cleared"].lower() == "true" for row in rows)
    assert candidate_cases == 1000 and candidate_all_clear == 1000
    rows = read_csv(ROOT / "results/task4_sensitivity_analysis/controlled_experiment/raw_cases.csv")
    assert len(rows) == 3000
    assert sum(row["all_cleared"].lower() == "true" for row in rows) == 3000


def run_tests() -> int:
    task1 = subprocess.run([sys.executable, "-m", "pytest", "task1/tests", "-q"], cwd=ROOT)
    if task1.returncode:
        return task1.returncode
    task4 = subprocess.run(
        [sys.executable, "-m", "unittest", "discover", "-s", "task4/tests", "-v"], cwd=ROOT
    )
    return task4.returncode


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--tests", action="store_true")
    args = parser.parse_args()
    check_q1()
    current, published = check_q2()
    check_q3()
    check_q4()
    print("PASS: Q1/Q2/Q3/Q4 formal-code and frozen-result checks")
    print(f"Q2 GDOP Mean: code={current:.6f} m, paper snapshot={published:.6f} m")
    if abs(current - published) > 1e-9:
        print("WARNING: Q2 code data and paper snapshot are inconsistent; code is the current basis.")
    return run_tests() if args.tests else 0


if __name__ == "__main__":
    raise SystemExit(main())
