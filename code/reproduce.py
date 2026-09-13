"""一条命令复算论文中的几何常数和主要实验表。

用法（仓库根目录）：python code/reproduce.py [--strict]
--strict 会在数据缺失或论文关键数值漂移时失败。
"""
from __future__ import annotations

import argparse
import csv
import gzip
import json
from pathlib import Path
from statistics import mean

import numpy as np

from geometry import (Observation, clip_polygon_with_disk, intersect_bearings,
                      minimum_enclosing_circle, region_diameter)
from search import (optical_cover_bound, optical_cover_time_bound,
                    q3_worst_coverage_distance, q4_double_ring)

ROOT = Path(__file__).resolve().parents[1]


def rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8", newline="") as stream:
        return list(csv.DictReader(stream))


def geometric_results() -> dict:
    observations = [
        Observation((713.63, 1193.59), 235.05529),
        Observation((-939.50, 362.10), 356.78364),
        Observation((590.63, -611.06), 117.85767),
    ]
    polygon = intersect_bearings(observations)
    diameter = region_diameter(clip_polygon_with_disk(polygon))[0]
    circle = minimum_enclosing_circle(polygon)
    return {
        "q1_counterexample": {
            "vertices": len(polygon),
            "diameter_m": diameter,
            "minimum_cover_diameter_m": 2 * circle.radius,
        },
        "q3_coverage": {
            "points": 7,
            "worst_distance_m": q3_worst_coverage_distance(),
            "safety_margin_m": 1000.0 - q3_worst_coverage_distance(),
        },
        "q4_guarantees": {
            "discovery_points": len(q4_double_ring()),
            "optical_worst_distance_m": optical_cover_bound(),
            "optical_local_time_bound_s": optical_cover_time_bound(),
        },
    }


def q2_results() -> dict:
    path = ROOT / "task2/results/raw/evaluations.csv"
    wanted = {"gdop_mean", "geometry", "fim_e", "random"}
    grouped: dict[str, list[dict[str, str]]] = {name: [] for name in wanted}
    for row in rows(path):
        if row["strategy"] in wanted:
            grouped[row["strategy"]].append(row)
    output = {}
    for strategy, sample in grouped.items():
        diameters = np.asarray([float(row["diameter_m"]) for row in sample])
        output[strategy] = {
            "n": len(sample),
            "mean_m": float(np.mean(diameters)),
            "median_m": float(np.median(diameters)),
            "p90_m": float(np.percentile(diameters, 90)),
            "p95_m": float(np.percentile(diameters, 95)),
            "max_m": float(np.max(diameters)),
            "move_mean_m": mean(float(row["move_distance_m"]) for row in sample),
            "selection_median_s": float(np.median(
                [float(row["selection_runtime_s"]) for row in sample])),
        }
    published = {}
    for row in rows(ROOT / "task2/results/tables/strategy_summary.csv"):
        if row["strategy"] in wanted:
            published[row["strategy"]] = {
                "n": int(row["n"]), "mean_m": float(row["diameter_mean"]),
                "median_m": float(row["diameter_median"]),
                "p90_m": float(row["diameter_p90"]),
                "p95_m": float(row["diameter_p95"]), "max_m": float(row["diameter_max"]),
            }
    return {
        "raw_current": output,
        "paper_table_snapshot": published,
        "consistent": all(abs(output[s]["mean_m"] - published[s]["mean_m"]) < 1e-9
                          for s in wanted),
    }


def q3_results() -> dict:
    table = ROOT / "task3/results/tables/optimization_validation/summary.csv"
    comparison = {}
    for row in rows(table):
        label = row["policy"].split("_")[1]
        comparison[label] = {
            "cases": int(row["cases"]),
            "mean_case_s": float(row["mean_case_s"]),
            "seconds_per_source": float(row["total_time_per_source_s"]),
            "p95_case_s": float(row["p95_case_s"]),
        }

    path = ROOT / "results/candidate057_concurrency100_seed20261310.jsonl.gz"
    records = []
    with gzip.open(path, "rt", encoding="utf-8") as stream:
        for line in stream:
            item = json.loads(line)
            if item.get("record_type") != "metadata":
                records.append(item)
    times = [float(item["result"]["virtual_time_s"]) for item in records]
    sources = [int(item["source_count"]) for item in records]
    return {
        "paired_30": comparison,
        "scale_100": {
            "successful_cases": sum(bool(item["result"]["success"]) for item in records),
            "cases": len(records),
            "cleared_sources": sum(int(item["result"]["known_total"]) for item in records),
            "true_sources": sum(sources),
            "seconds_per_source": sum(times) / sum(sources),
            "p95_case_s": float(np.percentile(times, 95)),
        },
    }


def _case_summary(path: Path) -> dict:
    data = rows(path)
    times = [float(row["virtual_time_s"]) for row in data]
    return {"cases": len(data),
            "all_cleared": sum(row["all_cleared"].lower() == "true" for row in data),
            "mean_s": mean(times)}


def q4_results() -> dict:
    base = ROOT / "experiments/t4_analysis/outputs/toward6000_v2"
    validation = {}
    for folder in ("holdout_omni100", "holdout_n10_mixed100", "holdout_mixed300",
                   "holdout_directional300", "holdout_n16_mixed200"):
        validation[folder] = {
            kind: _case_summary(base / folder / kind / "cases.csv")
            for kind in ("baseline", "candidate")
        }

    data = rows(ROOT / "results/task4_sensitivity_analysis/controlled_experiment/raw_cases.csv")
    cells: dict[tuple[str, int, float], list[dict[str, str]]] = {}
    for row in data:
        key = (row["strategy"], int(row["emitter_count"]),
               float(row["directional_probability"]))
        cells.setdefault(key, []).append(row)

    directional_effect = {}
    for strategy in ("double_ring_optical_clear_probe", "adaptive_double_ring_clear_probe"):
        directional_effect[strategy] = {}
        for count in (10, 13, 16):
            low = mean(float(x["virtual_time_s"]) for x in cells[(strategy, count, 0.0)])
            high = mean(float(x["virtual_time_s"]) for x in cells[(strategy, count, 1.0)])
            directional_effect[strategy][str(count)] = high - low
    interaction = {
        strategy: directional_effect[strategy]["16"] - directional_effect[strategy]["10"]
        for strategy in directional_effect
    }
    within_6000_n16 = {}
    strategy = "adaptive_double_ring_clear_probe"
    for probability in (0.0, 0.25, 0.5, 0.75, 1.0):
        sample = cells[(strategy, 16, probability)]
        within_6000_n16[str(probability)] = mean(
            row["within_6000"].lower() == "true" for row in sample)
    return {"validation_1000": validation,
            "controlled_3000": {
                "runs": len(data),
                "all_cleared": sum(row["all_cleared"].lower() == "true" for row in data),
                "directional_effect_s": directional_effect,
                "interaction_s": interaction,
                "adaptive_within_6000_n16": within_6000_n16,
            }}


def verify(result: dict) -> None:
    assert abs(result["geometry"]["q1_counterexample"]["diameter_m"] - 43.348530) < 1e-5
    assert abs(result["geometry"]["q1_counterexample"]["minimum_cover_diameter_m"] - 46.196234) < 1e-5
    assert abs(result["geometry"]["q3_coverage"]["worst_distance_m"] - 968.902) < 1e-3
    assert abs(result["geometry"]["q4_guarantees"]["optical_worst_distance_m"] - 19.2924) < 1e-4
    assert abs(result["geometry"]["q4_guarantees"]["optical_local_time_bound_s"] - 82.2486) < 1e-4
    assert result["q2"]["raw_current"]["gdop_mean"]["n"] == 10_000
    assert abs(result["q2"]["paper_table_snapshot"]["gdop_mean"]["mean_m"] - 52.38) < 0.01
    assert result["q3"]["scale_100"]["successful_cases"] == 100
    assert result["q3"]["scale_100"]["cleared_sources"] == 1291
    assert abs(result["q3"]["scale_100"]["seconds_per_source"] - 256.01) < 0.01
    assert sum(x["candidate"]["cases"] for x in result["q4"]["validation_1000"].values()) == 1000
    assert sum(x["candidate"]["all_cleared"] for x in result["q4"]["validation_1000"].values()) == 1000
    assert result["q4"]["controlled_3000"]["runs"] == 3000
    assert result["q4"]["controlled_3000"]["all_cleared"] == 3000


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--strict", action="store_true", help="检查论文关键数值")
    args = parser.parse_args()
    result = {"geometry": geometric_results(), "q2": q2_results(),
              "q3": q3_results(), "q4": q4_results()}
    if args.strict:
        verify(result)
    print(json.dumps(result, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
