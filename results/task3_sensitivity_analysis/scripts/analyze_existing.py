#!/usr/bin/env python3
"""Analyze Task 3 sensitivity using archived runs only; run no simulations."""

from __future__ import annotations

import csv
import gzip
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
REPOSITORY = ROOT.parent.parent
PRIMARY = REPOSITORY / "results/candidate057_concurrency100_seed20261310.jsonl.gz"
TABLES = ROOT / "data_only/tables"
FIGURES = ROOT / "data_only/figures"
BOOTSTRAP_SEED = 20260913
BOOTSTRAP_REPS = 10_000


def quantile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def read_log(path: Path) -> tuple[dict[str, Any], list[dict[str, Any]]]:
    with gzip.open(path, "rt", encoding="utf-8") as handle:
        metadata = json.loads(next(handle))
        rows = [json.loads(line) for line in handle]
    return metadata, rows


def validate_log(path: Path, metadata: dict[str, Any], rows: list[dict[str, Any]]) -> None:
    expected = metadata["case_count"] * len(metadata["policies"])
    if len(rows) != expected:
        raise ValueError(f"incomplete {path}: expected {expected}, got {len(rows)}")
    keys = [(row["policy"], row["scenario_seed"]) for row in rows]
    if len(keys) != len(set(keys)):
        raise ValueError(f"duplicate policy/seed key in {path}")
    expected_keys = {
        (policy, metadata["paired_scenario_seed_start"] + offset)
        for policy in metadata["policies"]
        for offset in range(metadata["case_count"])
    }
    if set(keys) != expected_keys:
        raise ValueError(f"unexpected policy/seed coverage in {path}")
    for row in rows:
        result = row["result"]
        residual = abs(sum(result["time_breakdown"].values()) - result["virtual_time_s"])
        if residual > 1e-6:
            raise ValueError(f"time-accounting mismatch in {path}, seed={row['scenario_seed']}")


def assert_paired(first: list[dict[str, Any]], second: list[dict[str, Any]]) -> list[tuple[dict[str, Any], dict[str, Any]]]:
    left = {row["scenario_seed"]: row for row in first}
    right = {row["scenario_seed"]: row for row in second}
    if set(left) != set(right):
        raise ValueError("paired logs do not have identical seed sets")
    pairs = []
    for seed in sorted(left):
        a, b = left[seed], right[seed]
        if a["source_count"] != b["source_count"] or a["sources"] != b["sources"]:
            raise ValueError(f"scenario truth differs at seed {seed}")
        pairs.append((a, b))
    return pairs


def ranks(values: list[float]) -> list[float]:
    order = sorted(range(len(values)), key=values.__getitem__)
    output = [0.0] * len(values)
    start = 0
    while start < len(order):
        end = start + 1
        while end < len(order) and values[order[end]] == values[order[start]]:
            end += 1
        rank = (start + 1 + end) / 2
        for index in order[start:end]:
            output[index] = rank
        start = end
    return output


def pearson(first: list[float], second: list[float]) -> float:
    mean_a, mean_b = statistics.fmean(first), statistics.fmean(second)
    numerator = sum((a - mean_a) * (b - mean_b) for a, b in zip(first, second))
    denominator = math.sqrt(sum((a - mean_a) ** 2 for a in first) * sum((b - mean_b) ** 2 for b in second))
    return numerator / denominator if denominator else 0.0


def spearman(first: list[float], second: list[float]) -> float:
    return pearson(ranks(first), ranks(second))


def inverse(matrix: list[list[float]]) -> list[list[float]]:
    size = len(matrix)
    work = [row[:] + [float(i == j) for j in range(size)] for i, row in enumerate(matrix)]
    for column in range(size):
        pivot = max(range(column, size), key=lambda row: abs(work[row][column]))
        if abs(work[pivot][column]) < 1e-12:
            raise ValueError("singular regression matrix")
        work[column], work[pivot] = work[pivot], work[column]
        scale = work[column][column]
        work[column] = [value / scale for value in work[column]]
        for row in range(size):
            if row == column:
                continue
            factor = work[row][column]
            work[row] = [a - factor * b for a, b in zip(work[row], work[column])]
    return [row[size:] for row in work]


def matmul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    columns = list(zip(*right))
    return [[sum(a * b for a, b in zip(row, column)) for column in columns] for row in left]


def hc3(rows: list[dict[str, Any]], response: str) -> list[dict[str, Any]]:
    specifications = [
        ("source_count (+1)", "source_count", 1.0),
        ("mean radial distance (+100 m)", "mean_radial_m", 100.0),
        ("mean reception radius (+100 m)", "mean_reception_radius_m", 100.0),
        ("maximum angular gap (+10 deg)", "maximum_angular_gap_deg", 10.0),
        ("mean nearest-neighbor distance (+100 m)", "mean_nearest_neighbor_m", 100.0),
    ]
    centers = {key: statistics.fmean(float(row[key]) for row in rows) for _, key, _ in specifications}
    x = [[1.0] + [(float(row[key]) - centers[key]) / scale for _, key, scale in specifications] for row in rows]
    y = [float(row[response]) for row in rows]
    p = len(x[0])
    xtx = [[sum(row[i] * row[j] for row in x) for j in range(p)] for i in range(p)]
    xty = [sum(row[i] * value for row, value in zip(x, y)) for i in range(p)]
    inv = inverse(xtx)
    beta = [sum(a * b for a, b in zip(row, xty)) for row in inv]
    residuals = [value - sum(a * b for a, b in zip(row, beta)) for row, value in zip(x, y)]
    leverage = [sum(row[i] * inv[i][j] * row[j] for i in range(p) for j in range(p)) for row in x]
    meat = [[0.0] * p for _ in range(p)]
    for row, error, hat in zip(x, residuals, leverage):
        scaled = (error / max(1 - hat, 1e-12)) ** 2
        for i in range(p):
            for j in range(p):
                meat[i][j] += row[i] * row[j] * scaled
    covariance = matmul(matmul(inv, meat), inv)
    errors = [math.sqrt(max(covariance[i][i], 0.0)) for i in range(p)]
    mean_y = statistics.fmean(y)
    r_squared = 1 - sum(value * value for value in residuals) / sum((value - mean_y) ** 2 for value in y)
    names = ["intercept at sample means"] + [item[0] for item in specifications]
    return [{"response": response, "term": name, "estimate": estimate, "hc3_se": error,
             "ci95_low": estimate - 1.96 * error, "ci95_high": estimate + 1.96 * error,
             "n": len(rows), "r_squared": r_squared}
            for name, estimate, error in zip(names, beta, errors)]


def circular_gap_degrees(points: list[list[float]]) -> float:
    angles = sorted(math.degrees(math.atan2(y, x)) % 360 for x, y in points)
    gaps = [b - a for a, b in zip(angles, angles[1:])] + [angles[0] + 360 - angles[-1]]
    return max(gaps)


def scenario_features(row: dict[str, Any], physical: dict[str, Any]) -> dict[str, Any]:
    sources = row["sources"]
    points = [source["position"] for source in sources]
    radial = [math.hypot(*point) for point in points]
    reception = [source["reception_radius_m"] for source in sources]
    nearest = [min(math.dist(point, other) for j, other in enumerate(points) if i != j) for i, point in enumerate(points)]
    center = [statistics.fmean(point[axis] for point in points) for axis in (0, 1)]
    result = row["result"]
    diagnostics = result["diagnostics"]
    operations = [item for item in diagnostics if item["type"] == "actual_operation"]
    stats = next(item for item in diagnostics if item["type"] == "dynamic_open_route_statistics")
    probe_events = [item for item in diagnostics if item["type"] == "bounded_enroute_probe"]
    output = {
        "scenario_seed": row["scenario_seed"], "source_count": row["source_count"],
        "virtual_time_s": result["virtual_time_s"], "time_per_source_s": result["virtual_time_s"] / row["source_count"],
        "success": result["success"], "clear_ratio": result["clear_ratio"], "action_count": result["action_count"],
        "wall_runtime_s": result["wall_runtime_s"], "mean_radial_m": statistics.fmean(radial),
        "radial_std_m": statistics.pstdev(radial), "maximum_radial_m": max(radial),
        "outer_source_fraction": sum(value >= 1200 for value in radial) / len(radial),
        "mean_reception_radius_m": statistics.fmean(reception), "minimum_reception_radius_m": min(reception),
        "reception_radius_std_m": statistics.pstdev(reception), "maximum_angular_gap_deg": circular_gap_degrees(points),
        "centroid_offset_m": math.hypot(*center), "mean_nearest_neighbor_m": statistics.fmean(nearest),
        "minimum_nearest_neighbor_m": min(nearest), "coverage_vertices_completed": len(result["coverage_completed"]),
        "movement_s": result["time_breakdown"]["movement_s"], "measurement_s": result["time_breakdown"]["measurement_s"],
        "switching_s": result["time_breakdown"]["switching_s"], "optical_s": result["time_breakdown"]["optical_s"],
        "laser_s": result["time_breakdown"]["laser_s"], "movement_distance_m": result["time_breakdown"]["movement_s"] * physical["speed_mps"],
        "measure_count": sum(item["action"] == "MEASURE" for item in operations),
        "no_signal_count": sum(item["action"] == "MEASURE" and item["result"] == "no_signal" for item in operations),
        "clear_attempt_count": sum(item["action"] == "CLEAR" for item in operations),
        "fallback_miss_count": sum(item["type"] == "fallback_miss" for item in diagnostics),
        "probe_attempt_count": len(probe_events), "probe_success_count": sum(item["success"] for item in probe_events),
        "refinement_count": sum(item["type"] == "local_cell_refinement" for item in diagnostics),
        "replan_count": stats["replan_count"], "opportunistic_measure_count": stats["opportunistic_measure_count"],
    }
    return output


def bootstrap_ratio(rows: list[dict[str, Any]], rng: random.Random, numerator: str, denominator: str) -> tuple[float, float]:
    draws = []
    for _ in range(BOOTSTRAP_REPS):
        sample = [rows[rng.randrange(len(rows))] for _ in rows]
        draws.append(sum(row[numerator] for row in sample) / sum(row[denominator] for row in sample))
    return quantile(draws, 0.025), quantile(draws, 0.975)


def summarize_primary(rows: list[dict[str, Any]], rng: random.Random) -> dict[str, Any]:
    ratio = sum(row["virtual_time_s"] for row in rows) / sum(row["source_count"] for row in rows)
    low, high = bootstrap_ratio(rows, rng, "virtual_time_s", "source_count")
    loo = [(sum(r["virtual_time_s"] for r in rows) - row["virtual_time_s"]) /
           (sum(r["source_count"] for r in rows) - row["source_count"]) for row in rows]
    times = [row["virtual_time_s"] for row in rows]
    return {"policy": "candidate_057_posterior_free", "cases": len(rows),
            "sources": sum(row["source_count"] for row in rows),
            "all_clear_cases": sum(row["success"] and row["clear_ratio"] == 1 for row in rows),
            "aggregate_time_per_source_s": ratio, "bootstrap_ci95_low_s": low, "bootstrap_ci95_high_s": high,
            "leave_one_out_min_s": min(loo), "leave_one_out_max_s": max(loo),
            "mean_case_time_s": statistics.fmean(times), "median_case_time_s": statistics.median(times),
            "p95_case_time_s": quantile(times, 0.95), "maximum_case_time_s": max(times),
            "zero_failure_rule_of_three_upper95": 3 / len(rows)}


def source_count_summary(rows: list[dict[str, Any]]) -> list[dict[str, Any]]:
    output = []
    for count in sorted({row["source_count"] for row in rows}):
        part = [row for row in rows if row["source_count"] == count]
        times = [row["virtual_time_s"] for row in part]
        output.append({"source_count": count, "cases": len(part), "all_clear_cases": sum(row["success"] for row in part),
                       "mean_case_time_s": statistics.fmean(times), "median_case_time_s": statistics.median(times),
                       "p95_case_time_s": quantile(times, 0.95), "mean_time_per_source_s": statistics.fmean(times) / count,
                       "mean_movement_s": statistics.fmean(row["movement_s"] for row in part),
                       "mean_measurement_s": statistics.fmean(row["measurement_s"] for row in part),
                       "mean_fallback_misses": statistics.fmean(row["fallback_miss_count"] for row in part),
                       "mean_probe_success_rate": sum(row["probe_success_count"] for row in part) /
                                                  max(sum(row["probe_attempt_count"] for row in part), 1)})
    return output


def paired_summary(label: str, baseline: list[dict[str, Any]], candidate: list[dict[str, Any]], rng: random.Random) -> dict[str, Any]:
    pairs = assert_paired(baseline, candidate)
    items = [{"delta": right["result"]["virtual_time_s"] - left["result"]["virtual_time_s"],
              "sources": left["source_count"]} for left, right in pairs]
    estimate = sum(item["delta"] for item in items) / sum(item["sources"] for item in items)
    draws = []
    for _ in range(BOOTSTRAP_REPS):
        sample = [items[rng.randrange(len(items))] for _ in items]
        draws.append(sum(item["delta"] for item in sample) / sum(item["sources"] for item in sample))
    return {"comparison": label, "cases": len(items), "sources": sum(item["sources"] for item in items),
            "candidate_minus_baseline_s_per_source": estimate,
            "bootstrap_ci95_low_s_per_source": quantile(draws, 0.025),
            "bootstrap_ci95_high_s_per_source": quantile(draws, 0.975),
            "mean_case_delta_s": statistics.fmean(item["delta"] for item in items),
            "candidate_faster_cases": sum(item["delta"] < 0 for item in items),
            "maximum_candidate_regression_s": max(0.0, max(item["delta"] for item in items))}


def svg_plot(path: Path, series: list[dict[str, Any]], x_label: str, y_label: str,
             y_domain: tuple[float, float] | None = None, horizontal: float | None = None) -> None:
    width, height, left, right, top, bottom = 900, 560, 90, 30, 35, 75
    all_x = [point[0] for item in series for point in item["points"]]
    all_y = [point[1] for item in series for point in item["points"]]
    xmin, xmax = min(all_x), max(all_x)
    ymin, ymax = y_domain or (min(all_y), max(all_y))
    if xmin == xmax: xmax += 1
    if ymin == ymax: ymax += 1
    sx = lambda value: left + (value - xmin) / (xmax - xmin) * (width - left - right)
    sy = lambda value: height - bottom - (value - ymin) / (ymax - ymin) * (height - top - bottom)
    colors = ["#4c78a8", "#e45756", "#54a24b", "#f58518", "#b279a2"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#222"/>',
             f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#222"/>']
    for i in range(6):
        xv, yv = xmin + i * (xmax - xmin) / 5, ymin + i * (ymax - ymin) / 5
        parts += [f'<text x="{sx(xv):.1f}" y="{height-bottom+22}" text-anchor="middle" font-size="12">{xv:.3g}</text>',
                  f'<text x="{left-10}" y="{sy(yv)+4:.1f}" text-anchor="end" font-size="12">{yv:.3g}</text>']
    if horizontal is not None:
        parts.append(f'<line x1="{left}" y1="{sy(horizontal):.1f}" x2="{width-right}" y2="{sy(horizontal):.1f}" stroke="#222" stroke-dasharray="5 5"/>')
    for index, item in enumerate(series):
        color = item.get("color", colors[index % len(colors)])
        points = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in item["points"])
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
        if item.get("markers", True):
            parts.extend(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3" fill="{color}"/>' for x, y in item["points"])
        legend_y = top + 18 * index
        parts += [f'<line x1="{width-300}" y1="{legend_y}" x2="{width-270}" y2="{legend_y}" stroke="{color}" stroke-width="2"/>',
                  f'<text x="{width-260}" y="{legend_y+4}" font-size="12">{item["label"]}</text>']
    parts += [f'<text x="{(left+width-right)/2}" y="{height-20}" text-anchor="middle" font-size="14">{x_label}</text>',
              f'<text x="20" y="{(top+height-bottom)/2}" text-anchor="middle" font-size="14" transform="rotate(-90 20 {(top+height-bottom)/2})">{y_label}</text>', '</svg>']
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    rng = random.Random(BOOTSTRAP_SEED)
    metadata, raw = read_log(PRIMARY)
    validate_log(PRIMARY, metadata, raw)
    physical = metadata["configuration"]["PhysicalConfig"]
    rows = [scenario_features(row, physical) for row in sorted(raw, key=lambda item: item["scenario_seed"])]
    write_csv(TABLES / "scenario_features.csv", rows)
    overall = summarize_primary(rows, rng)
    write_csv(TABLES / "overall_summary.csv", [overall])
    by_count = source_count_summary(rows)
    write_csv(TABLES / "source_count_summary.csv", by_count)

    components = ["movement_s", "measurement_s", "switching_s", "optical_s", "laser_s"]
    total = sum(row["virtual_time_s"] for row in rows)
    costs = [{"component": component, "mean_time_s": statistics.fmean(row[component] for row in rows),
              "share_of_total": sum(row[component] for row in rows) / total,
              "local_cost_elasticity": sum(row[component] for row in rows) / total}
             for component in components]
    write_csv(TABLES / "cost_decomposition.csv", costs)

    thresholds = []
    for threshold in (200, 220, 240, 250, 260, 275, 300, 325, 350):
        met = sum(row["time_per_source_s"] <= threshold for row in rows)
        thresholds.append({"metric": "time_per_source_s", "threshold_s": threshold, "cases_meeting": met,
                           "rate": met / len(rows)})
    for threshold in (2750, 3000, 3250, 3500, 3750, 4000):
        met = sum(row["virtual_time_s"] <= threshold for row in rows)
        thresholds.append({"metric": "case_virtual_time_s", "threshold_s": threshold, "cases_meeting": met,
                           "rate": met / len(rows)})
    write_csv(TABLES / "threshold_sensitivity.csv", thresholds)

    predictors = ["source_count", "mean_radial_m", "radial_std_m", "maximum_radial_m", "outer_source_fraction",
                  "mean_reception_radius_m", "minimum_reception_radius_m", "reception_radius_std_m",
                  "maximum_angular_gap_deg", "centroid_offset_m", "mean_nearest_neighbor_m", "minimum_nearest_neighbor_m"]
    correlations = [{"predictor": predictor, "response": response,
                     "spearman_rho": spearman([float(row[predictor]) for row in rows], [float(row[response]) for row in rows])}
                    for response in ("virtual_time_s", "time_per_source_s") for predictor in predictors]
    write_csv(TABLES / "spearman_correlations.csv", correlations)
    write_csv(TABLES / "exploratory_hc3_regression.csv", hc3(rows, "virtual_time_s") + hc3(rows, "time_per_source_s"))

    counterfactuals = []
    for factor, component in (("speed", "movement_s"), ("measure_duration", "measurement_s"),
                              ("switch_duration", "switching_s"), ("optical_duration", "optical_s"),
                              ("laser_duration", "laser_s")):
        for multiplier in (0.8, 0.9, 1.0, 1.1, 1.2):
            component_multiplier = 1 / multiplier if factor == "speed" else multiplier
            adjusted = [row["virtual_time_s"] + row[component] * (component_multiplier - 1) for row in rows]
            ratio = sum(adjusted) / sum(row["source_count"] for row in rows)
            counterfactuals.append({"factor": factor, "input_multiplier": multiplier,
                                    "aggregate_time_per_source_s": ratio,
                                    "change_from_baseline_s_per_source": ratio - overall["aggregate_time_per_source_s"],
                                    "mean_case_time_s": statistics.fmean(adjusted),
                                    "frozen_trajectory": True})
    write_csv(TABLES / "frozen_trajectory_cost_sensitivity.csv", counterfactuals)

    opt = REPOSITORY / "task3/results/raw/optimization"
    base30_meta, base30 = read_log(opt / "optimization_049_validation30.jsonl.gz")
    cand30_meta, cand30 = read_log(opt / "optimization_057_validation30.jsonl.gz")
    validate_log(opt / "optimization_049_validation30.jsonl.gz", base30_meta, base30)
    validate_log(opt / "optimization_057_validation30.jsonl.gz", cand30_meta, cand30)
    base30 = [row for row in base30 if row["policy"] == "candidate_041_dynamic_open_route_deferred_cross_view"]
    cand30 = [row for row in cand30 if row["policy"] == "candidate_057_posterior_free"]
    paired_rows = [paired_summary("057 minus 041 (full mechanism bundle, validation)", base30, cand30, rng)]

    development_files = ["optimization_049_051_development5.jsonl.gz", "optimization_053_development5.jsonl.gz",
                         "optimization_054_055_development5.jsonl.gz", "optimization_056_057_development5.jsonl.gz"]
    development: dict[str, list[dict[str, Any]]] = {}
    truths: dict[int, Any] = {}
    for filename in development_files:
        meta, part = read_log(opt / filename)
        validate_log(opt / filename, meta, part)
        for row in part:
            seed = row["scenario_seed"]
            truth = row["sources"]
            if seed in truths and truths[seed] != truth:
                raise ValueError(f"development truth mismatch at seed {seed}")
            truths[seed] = truth
            development.setdefault(row["policy"], []).append(row)
    comparisons = [
        ("probe budget 24 minus 0, fixed-order background", "candidate_049_joint_completion", "candidate_054_enroute_probe"),
        ("probe budget 24 minus 0, free-order background", "candidate_053_free_order", "candidate_055_free_probe"),
        ("posterior on minus off, fixed-order background", "candidate_054_enroute_probe", "candidate_056_posterior_probe"),
        ("posterior on minus off, free-order background", "candidate_055_free_probe", "candidate_057_posterior_free"),
    ]
    paired_rows.extend(paired_summary(label, development[left], development[right], rng) for label, left, right in comparisons)
    write_csv(TABLES / "existing_paired_mechanism_effects.csv", paired_rows)

    svg_plot(FIGURES / "source_count_response.svg",
             [{"label": "mean case time", "points": [(row["source_count"], row["mean_case_time_s"]) for row in by_count]}],
             "Source count", "Mean virtual time per case (s)")
    per_source_thresholds = [row for row in thresholds if row["metric"] == "time_per_source_s"]
    svg_plot(FIGURES / "per_source_threshold_sensitivity.svg",
             [{"label": "empirical attainment", "points": [(row["threshold_s"], row["rate"]) for row in per_source_thresholds]}],
             "Time threshold (s/source)", "Fraction of cases meeting threshold", y_domain=(0, 1), horizontal=0.5)
    factor_series = [{"label": factor, "points": [(row["input_multiplier"], row["aggregate_time_per_source_s"])
                     for row in counterfactuals if row["factor"] == factor]}
                     for factor in ("speed", "measure_duration", "switch_duration", "optical_duration", "laser_duration")]
    svg_plot(FIGURES / "frozen_trajectory_cost_sensitivity.svg", factor_series,
             "Input multiplier", "Aggregate virtual time (s/source)")

    metadata_output = {
        "analysis": "post-hoc sensitivity analysis using existing simulations only",
        "primary_input": str(PRIMARY.relative_to(REPOSITORY)),
        "primary_sha256": hashlib.sha256(PRIMARY.read_bytes()).hexdigest(),
        "analysis_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_repetitions": BOOTSTRAP_REPS,
        "new_simulations_run": False,
        "limitations": ["scenario associations are observational", "cost counterfactuals freeze actions and routes",
                        "five-case mechanism effects are development diagnostics", "all results use the local simulator"],
    }
    (ROOT / "data_only").mkdir(parents=True, exist_ok=True)
    (ROOT / "data_only/analysis_metadata.json").write_text(json.dumps(metadata_output, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"overall": overall, "paired": paired_rows}, indent=2))


if __name__ == "__main__":
    main()
