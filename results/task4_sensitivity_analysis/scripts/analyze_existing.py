#!/usr/bin/env python3
"""Sensitivity analysis using only the copied Task 4 100+100 data.

The script deliberately uses only the Python standard library so the archived
analysis remains runnable in the repository's minimal execution environment.
"""

from __future__ import annotations

import csv
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Callable, Iterable


ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT.parent / "task4_mixed100_vs_directional100"
TABLES = ROOT / "data_only" / "tables"
FIGURES = ROOT / "data_only" / "figures"
BOOTSTRAP_SEED = 20260913
BOOTSTRAP_REPS = 10_000


def load_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    with path.open(encoding="utf-8", newline="") as handle:
        for raw in csv.DictReader(handle):
            row: dict[str, Any] = {}
            for key, value in raw.items():
                if value in {"True", "False"}:
                    row[key] = value == "True"
                elif value == "":
                    row[key] = None
                else:
                    try:
                        number = float(value)
                        row[key] = int(number) if number.is_integer() else number
                    except ValueError:
                        row[key] = value
            row["directional_fraction"] = row["directional_count"] / row["emitter_count"]
            rows.append(row)
    return sorted(rows, key=lambda item: item["seed"])


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(f"refusing to write empty table: {path}")
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def quantile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def bootstrap_mean_ci(values: list[float], rng: random.Random) -> tuple[float, float]:
    n = len(values)
    draws = [statistics.fmean(values[rng.randrange(n)] for _ in range(n)) for _ in range(BOOTSTRAP_REPS)]
    return quantile(draws, 0.025), quantile(draws, 0.975)


def wilson(successes: int, total: int) -> tuple[float, float]:
    z = 1.959963984540054
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total**2)) / denominator
    return center - radius, center + radius


def inverse(matrix: list[list[float]]) -> list[list[float]]:
    n = len(matrix)
    augmented = [row[:] + [float(i == j) for j in range(n)] for i, row in enumerate(matrix)]
    for column in range(n):
        pivot = max(range(column, n), key=lambda row: abs(augmented[row][column]))
        if abs(augmented[pivot][column]) < 1e-12:
            raise ValueError("singular regression matrix")
        augmented[column], augmented[pivot] = augmented[pivot], augmented[column]
        scale = augmented[column][column]
        augmented[column] = [value / scale for value in augmented[column]]
        for row in range(n):
            if row == column:
                continue
            factor = augmented[row][column]
            augmented[row] = [left - factor * right for left, right in zip(augmented[row], augmented[column])]
    return [row[n:] for row in augmented]


def matvec(matrix: list[list[float]], vector: list[float]) -> list[float]:
    return [sum(a * b for a, b in zip(row, vector)) for row in matrix]


def matmul(left: list[list[float]], right: list[list[float]]) -> list[list[float]]:
    columns = list(zip(*right))
    return [[sum(a * b for a, b in zip(row, column)) for column in columns] for row in left]


def hc3_ols(rows: list[dict[str, Any]], response: str, label: str) -> list[dict[str, Any]]:
    mean_n = statistics.fmean(row["emitter_count"] for row in rows)
    mean_share = statistics.fmean(row["directional_fraction"] for row in rows)
    x, y = [], []
    for row in rows:
        centered_n = row["emitter_count"] - mean_n
        share10 = (row["directional_fraction"] - mean_share) / 0.1
        x.append([1.0, centered_n, share10, centered_n * share10])
        y.append(float(row[response]))
    p = len(x[0])
    xtx = [[sum(row[i] * row[j] for row in x) for j in range(p)] for i in range(p)]
    xty = [sum(row[i] * value for row, value in zip(x, y)) for i in range(p)]
    xtx_inverse = inverse(xtx)
    beta = matvec(xtx_inverse, xty)
    residual = [value - sum(a * b for a, b in zip(row, beta)) for row, value in zip(x, y)]
    leverage = [sum(row[i] * xtx_inverse[i][j] * row[j] for i in range(p) for j in range(p)) for row in x]
    meat = [[0.0] * p for _ in range(p)]
    for row, error, hat in zip(x, residual, leverage):
        scaled_squared = (error / max(1 - hat, 1e-12)) ** 2
        for i in range(p):
            for j in range(p):
                meat[i][j] += row[i] * row[j] * scaled_squared
    covariance = matmul(matmul(xtx_inverse, meat), xtx_inverse)
    standard_errors = [math.sqrt(max(covariance[i][i], 0.0)) for i in range(p)]
    mean_y = statistics.fmean(y)
    r_squared = 1 - sum(value**2 for value in residual) / sum((value - mean_y) ** 2 for value in y)
    names = ["intercept", "emitter_count (+1)", "directional_share (+10pp)", "interaction (+1 x +10pp)"]
    output = []
    for name, estimate, error in zip(names, beta, standard_errors):
        z_value = estimate / error if error else math.inf
        output.append({"model": label, "response": response, "term": name, "estimate": estimate,
                       "hc3_se": error, "ci95_low": estimate - 1.96 * error,
                       "ci95_high": estimate + 1.96 * error,
                       "p_value_normal_approx": math.erfc(abs(z_value) / math.sqrt(2)),
                       "n": len(y), "r_squared": r_squared})
    return output


def ranks(values: list[float]) -> list[float]:
    ordered = sorted(range(len(values)), key=values.__getitem__)
    result = [0.0] * len(values)
    start = 0
    while start < len(ordered):
        end = start + 1
        while end < len(ordered) and values[ordered[end]] == values[ordered[start]]:
            end += 1
        average_rank = (start + 1 + end) / 2
        for index in ordered[start:end]:
            result[index] = average_rank
        start = end
    return result


def pearson(first: list[float], second: list[float]) -> float:
    mean_first, mean_second = statistics.fmean(first), statistics.fmean(second)
    numerator = sum((a - mean_first) * (b - mean_second) for a, b in zip(first, second))
    denominator = math.sqrt(sum((a - mean_first) ** 2 for a in first) * sum((b - mean_second) ** 2 for b in second))
    return numerator / denominator


def spearman(first: list[float], second: list[float]) -> tuple[float, float]:
    rho = pearson(ranks(first), ranks(second))
    n = len(first)
    t_value = rho * math.sqrt((n - 2) / max(1 - rho * rho, 1e-12))
    return rho, math.erfc(abs(t_value) / math.sqrt(2))


def fraction_bin(value: float) -> str:
    if value < 0.4:
        return "<40%"
    if value < 0.5:
        return "40-<50%"
    if value < 0.6:
        return "50-<60%"
    return ">=60%"


def summarize_scenario(rows: list[dict[str, Any]], scenario: str, strategy: str, rng: random.Random) -> dict[str, Any]:
    times = [row["virtual_time_s"] for row in rows]
    ci_low, ci_high = bootstrap_mean_ci(times, rng)
    target = sum(value <= 6000 for value in times)
    target_low, target_high = wilson(target, len(rows))
    return {"scenario": scenario, "strategy": strategy, "cases": len(rows),
            "emitter_total": sum(row["emitter_count"] for row in rows),
            "directional_total": sum(row["directional_count"] for row in rows),
            "omnidirectional_total": sum(row["emitter_count"] - row["directional_count"] for row in rows),
            "all_clear_cases": sum(row["all_cleared"] for row in rows),
            "mean_time_s": statistics.fmean(times), "mean_time_bootstrap_ci95_low": ci_low,
            "mean_time_bootstrap_ci95_high": ci_high, "median_time_s": statistics.median(times),
            "p95_time_s": quantile(times, 0.95), "maximum_time_s": max(times),
            "within_6000_cases": target, "within_6000_rate": target / len(rows),
            "within_6000_wilson_ci95_low": target_low, "within_6000_wilson_ci95_high": target_high}


def summarize_groups(rows: list[dict[str, Any]], key_function: Callable[[dict[str, Any]], Any], strategy: str) -> list[dict[str, Any]]:
    groups: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(key_function(row), []).append(row)
    output = []
    for key, part in groups.items():
        output.append({"strategy": strategy, "group": key, "cases": len(part),
                       "mean_emitter_count": statistics.fmean(row["emitter_count"] for row in part),
                       "mean_directional_fraction": statistics.fmean(row["directional_fraction"] for row in part),
                       "mean_time_s": statistics.fmean(row["virtual_time_s"] for row in part),
                       "median_time_s": statistics.median(row["virtual_time_s"] for row in part),
                       "p95_time_s": quantile((row["virtual_time_s"] for row in part), 0.95),
                       "within_6000_rate": statistics.fmean(row["virtual_time_s"] <= 6000 for row in part),
                       "mean_movement_distance_m": statistics.fmean(row["movement_distance_m"] for row in part),
                       "mean_measure_count": statistics.fmean(row["measure_count"] for row in part),
                       "mean_no_signal_rate": statistics.fmean(row["no_signal_rate"] for row in part),
                       "mean_directional_loss_count": statistics.fmean(row["directional_loss_count"] for row in part)})
    return sorted(output, key=lambda row: str(row["group"]))


def summarize_paired_groups(rows: list[dict[str, Any]], key_function: Callable[[dict[str, Any]], Any]) -> list[dict[str, Any]]:
    groups: dict[Any, list[dict[str, Any]]] = {}
    for row in rows:
        groups.setdefault(key_function(row), []).append(row)
    output = []
    for key, part in groups.items():
        delta = [row["virtual_time_delta_s"] for row in part]
        output.append({"group": key, "cases": len(part),
                       "mean_directional_fraction": statistics.fmean(row["directional_fraction"] for row in part),
                       "mean_delta_s": statistics.fmean(delta), "median_delta_s": statistics.median(delta),
                       "p95_delta_s": quantile(delta, 0.95),
                       "candidate_faster_rate": statistics.fmean(value < 0 for value in delta),
                       "candidate_slower_rate": statistics.fmean(value > 0 for value in delta),
                       "gained_6000_cases": sum(row["baseline_virtual_time_s"] > 6000 >= row["candidate_virtual_time_s"] for row in part),
                       "lost_6000_cases": sum(row["candidate_virtual_time_s"] > 6000 >= row["baseline_virtual_time_s"] for row in part)})
    return sorted(output, key=lambda row: str(row["group"]))


def svg_plot(path: Path, series: list[dict[str, Any]], x_label: str, y_label: str,
             x_domain: tuple[float, float] | None = None, y_domain: tuple[float, float] | None = None,
             vertical: float | None = None, horizontal: float | None = None) -> None:
    width, height = 900, 560
    left, right, top, bottom = 90, 30, 35, 75
    all_x = [point[0] for item in series for point in item["points"]]
    all_y = [point[1] for item in series for point in item["points"]]
    xmin, xmax = x_domain or (min(all_x), max(all_x))
    ymin, ymax = y_domain or (min(all_y), max(all_y))
    sx = lambda value: left + (value - xmin) / (xmax - xmin) * (width - left - right)
    sy = lambda value: height - bottom - (value - ymin) / (ymax - ymin) * (height - top - bottom)
    colors = ["#4c78a8", "#72b7b2", "#e45756", "#f58518", "#54a24b", "#b279a2"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
             '<rect width="100%" height="100%" fill="white"/>',
             f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#222"/>',
             f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#222"/>']
    for i in range(6):
        xv, yv = xmin + i * (xmax - xmin) / 5, ymin + i * (ymax - ymin) / 5
        parts += [f'<text x="{sx(xv):.1f}" y="{height-bottom+22}" text-anchor="middle" font-size="12">{xv:.2g}</text>',
                  f'<text x="{left-10}" y="{sy(yv)+4:.1f}" text-anchor="end" font-size="12">{yv:.2g}</text>']
    if vertical is not None:
        parts.append(f'<line x1="{sx(vertical):.1f}" y1="{top}" x2="{sx(vertical):.1f}" y2="{height-bottom}" stroke="#222" stroke-dasharray="5 5"/>')
    if horizontal is not None:
        parts.append(f'<line x1="{left}" y1="{sy(horizontal):.1f}" x2="{width-right}" y2="{sy(horizontal):.1f}" stroke="#222" stroke-dasharray="5 5"/>')
    for index, item in enumerate(series):
        color, dash = item.get("color", colors[index % len(colors)]), ' stroke-dasharray="8 5"' if item.get("dashed") else ""
        points = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in item["points"])
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"{dash}/>')
        if item.get("markers"):
            parts.extend(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="3" fill="{color}"/>' for x, y in item["points"])
        legend_y = top + 18 * index
        parts += [f'<line x1="{width-265}" y1="{legend_y}" x2="{width-235}" y2="{legend_y}" stroke="{color}" stroke-width="2"{dash}/>',
                  f'<text x="{width-225}" y="{legend_y+4}" font-size="12">{item["label"]}</text>']
    parts += [f'<text x="{(left+width-right)/2}" y="{height-20}" text-anchor="middle" font-size="14">{x_label}</text>',
              f'<text x="20" y="{(top+height-bottom)/2}" text-anchor="middle" font-size="14" transform="rotate(-90 20 {(top+height-bottom)/2})">{y_label}</text>', '</svg>']
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    FIGURES.mkdir(parents=True, exist_ok=True)
    rng = random.Random(BOOTSTRAP_SEED)
    frames = {(scenario, strategy): load_csv(SOURCE / folder / strategy / "cases.csv")
              for scenario, folder in (("mixed", "mixed100"), ("all_directional", "all_directional100"))
              for strategy in ("baseline", "candidate")}
    scenario_rows = [summarize_scenario(rows, scenario, strategy, rng) for (scenario, strategy), rows in frames.items()]
    write_csv(TABLES / "scenario_summary.csv", scenario_rows)

    by_count, by_fraction = [], []
    for strategy in ("baseline", "candidate"):
        mixed = frames[("mixed", strategy)]
        by_count.extend(summarize_groups(mixed, lambda row: row["emitter_count"], strategy))
        by_fraction.extend(summarize_groups(mixed, lambda row: fraction_bin(row["directional_fraction"]), strategy))
    write_csv(TABLES / "mixed_by_emitter_count.csv", by_count)
    write_csv(TABLES / "mixed_by_directional_fraction.csv", by_fraction)

    paired_sets: dict[str, list[dict[str, Any]]] = {}
    for scenario in ("mixed", "all_directional"):
        baseline, candidate = frames[(scenario, "baseline")], frames[(scenario, "candidate")]
        assert [row["seed"] for row in baseline] == [row["seed"] for row in candidate]
        paired = [{"seed": b["seed"], "emitter_count": b["emitter_count"],
                   "directional_count": b["directional_count"], "directional_fraction": b["directional_fraction"],
                   "baseline_virtual_time_s": b["virtual_time_s"], "candidate_virtual_time_s": c["virtual_time_s"],
                   "virtual_time_delta_s": c["virtual_time_s"] - b["virtual_time_s"]}
                  for b, c in zip(baseline, candidate)]
        paired_sets[scenario] = paired
        write_csv(TABLES / f"{scenario}_paired_deltas.csv", paired)
    write_csv(TABLES / "paired_delta_by_emitter_count.csv", summarize_paired_groups(paired_sets["mixed"], lambda row: row["emitter_count"]))
    write_csv(TABLES / "paired_delta_by_directional_fraction.csv", summarize_paired_groups(paired_sets["mixed"], lambda row: fraction_bin(row["directional_fraction"])))

    cost_columns = {"movement_time_s": "movement", "measure_time_s": "measurement", "switch_time_s": "channel_switch", "optical_time_s": "optical", "successful_clear_time_s": "successful_clear"}
    costs = []
    for (scenario, strategy), rows in frames.items():
        mean_total = statistics.fmean(row["virtual_time_s"] for row in rows)
        for column, component in cost_columns.items():
            mean_component = statistics.fmean(row[column] for row in rows)
            costs.append({"scenario": scenario, "strategy": strategy, "component": component,
                          "mean_time_s": mean_component, "share_of_mean_total": mean_component / mean_total})
    write_csv(TABLES / "cost_decomposition.csv", costs)

    threshold_rows = []
    for (scenario, strategy), rows in frames.items():
        for threshold in range(5000, 9001, 250):
            successes = sum(row["virtual_time_s"] <= threshold for row in rows)
            threshold_rows.append({"scenario": scenario, "strategy": strategy, "threshold_s": threshold,
                                   "success_cases": successes, "success_rate": successes / len(rows)})
    write_csv(TABLES / "threshold_rates.csv", threshold_rows)

    stability = []
    for scenario, paired in paired_sets.items():
        values = [row["virtual_time_delta_s"] for row in paired]
        ci_low, ci_high = bootstrap_mean_ci(values, rng)
        leave_one_out = [(sum(values) - value) / (len(values) - 1) for value in values]
        stability.append({"comparison": f"candidate_minus_baseline__{scenario}", "estimate_s": statistics.fmean(values),
                          "bootstrap_ci95_low_s": ci_low, "bootstrap_ci95_high_s": ci_high,
                          "leave_one_out_min_s": min(leave_one_out), "leave_one_out_max_s": max(leave_one_out)})
    for strategy in ("baseline", "candidate"):
        differences = [d["virtual_time_s"] - m["virtual_time_s"] for d, m in zip(frames[("all_directional", strategy)], frames[("mixed", strategy)])]
        ci_low, ci_high = bootstrap_mean_ci(differences, rng)
        leave_one_out = [(sum(differences) - value) / 99 for value in differences]
        stability.append({"comparison": f"all_directional_minus_mixed__{strategy}__seed_aligned_not_instance_paired",
                          "estimate_s": statistics.fmean(differences), "bootstrap_ci95_low_s": ci_low,
                          "bootstrap_ci95_high_s": ci_high, "leave_one_out_min_s": min(leave_one_out),
                          "leave_one_out_max_s": max(leave_one_out)})
    write_csv(TABLES / "bootstrap_and_leave_one_out.csv", stability)

    regressions = []
    for strategy in ("baseline", "candidate"):
        regressions.extend(hc3_ols(frames[("mixed", strategy)], "virtual_time_s", f"mixed_{strategy}"))
    regressions.extend(hc3_ols(paired_sets["mixed"], "virtual_time_delta_s", "mixed_paired_delta"))
    write_csv(TABLES / "exploratory_hc3_regression.csv", regressions)
    correlations = []
    for strategy in ("baseline", "candidate"):
        rows = frames[("mixed", strategy)]
        for predictor in ("emitter_count", "directional_count", "directional_fraction"):
            rho, p_value = spearman([row[predictor] for row in rows], [row["virtual_time_s"] for row in rows])
            correlations.append({"strategy": strategy, "predictor": predictor, "spearman_rho": rho,
                                 "p_value_normal_approx": p_value})
    write_csv(TABLES / "spearman_correlations.csv", correlations)

    colors = {("mixed", "baseline"): "#4c78a8", ("mixed", "candidate"): "#72b7b2",
              ("all_directional", "baseline"): "#e45756", ("all_directional", "candidate"): "#f58518"}
    ecdf_series, threshold_series = [], []
    for key, rows in frames.items():
        ordered = sorted(row["virtual_time_s"] for row in rows)
        ecdf_series.append({"label": f"{key[0]} / {key[1]}", "color": colors[key], "dashed": key[1] == "baseline",
                            "points": [(value, (index + 1) / len(ordered)) for index, value in enumerate(ordered)]})
        parts = [row for row in threshold_rows if row["scenario"] == key[0] and row["strategy"] == key[1]]
        threshold_series.append({"label": f"{key[0]} / {key[1]}", "color": colors[key], "dashed": key[1] == "baseline",
                                 "markers": True, "points": [(row["threshold_s"], row["success_rate"]) for row in parts]})
    svg_plot(FIGURES / "completion_time_ecdf.svg", ecdf_series, "Virtual completion time (s)", "Empirical cumulative probability", y_domain=(0, 1), vertical=6000)
    svg_plot(FIGURES / "threshold_sensitivity.svg", threshold_series, "Time threshold (s)", "Fraction fully cleared", x_domain=(5000, 9000), y_domain=(0, 1))
    candidate = frames[("mixed", "candidate")]
    svg_plot(FIGURES / "mixed_candidate_directional_fraction.svg",
             [{"label": "mixed candidate cases", "markers": True, "points": [(row["directional_fraction"], row["virtual_time_s"]) for row in sorted(candidate, key=lambda item: item["directional_fraction"])]}],
             "Directional fraction", "Virtual completion time (s)", x_domain=(0.15, 0.85), horizontal=6000)
    svg_plot(FIGURES / "mixed_paired_delta.svg",
             [{"label": "candidate - baseline", "markers": True, "points": [(row["directional_fraction"], row["virtual_time_delta_s"]) for row in sorted(paired_sets["mixed"], key=lambda item: item["directional_fraction"])]}],
             "Directional fraction", "Paired time delta (s)", x_domain=(0.15, 0.85), horizontal=0)

    metadata = {"analysis_type": "observational and paired post-hoc analysis; no new simulations",
                "source": "result/task4_mixed100_vs_directional100", "runtime_dependencies": "Python standard library only",
                "bootstrap_seed": BOOTSTRAP_SEED, "bootstrap_repetitions": BOOTSTRAP_REPS,
                "directional_fraction_bins": {"<40%": [0, 0.4], "40-<50%": [0.4, 0.5], "50-<60%": [0.5, 0.6], ">=60%": [0.6, 1]},
                "important_limitation": "Mixed and all-directional samples are seed-aligned but not strict type-only counterfactual pairs."}
    (ROOT / "data_only" / "analysis_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"scenario_summary": scenario_rows, "stability": stability}, indent=2))


if __name__ == "__main__":
    main()
