#!/usr/bin/env python3
"""Analyze the controlled Task 4 factorial sensitivity experiment."""

from __future__ import annotations

import argparse
import csv
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "controlled_experiment"
BOOTSTRAP_SEED = 20260914
BOOTSTRAP_REPS = 10_000
STRATEGIES = ("double_ring_optical_clear_probe", "adaptive_double_ring_clear_probe")
COUNTS = (10, 13, 16)
PROBABILITIES = (0.0, 0.25, 0.5, 0.75, 1.0)


def load_rows(path: Path) -> list[dict[str, Any]]:
    rows = []
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
            rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def quantile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def bootstrap_ci(values: list[float], rng: random.Random) -> tuple[float, float]:
    n = len(values)
    estimates = [statistics.fmean(values[rng.randrange(n)] for _ in range(n)) for _ in range(BOOTSTRAP_REPS)]
    return quantile(estimates, 0.025), quantile(estimates, 0.975)


def wilson(successes: int, total: int) -> tuple[float, float]:
    z = 1.959963984540054
    rate = successes / total
    denominator = 1 + z * z / total
    center = (rate + z * z / (2 * total)) / denominator
    radius = z * math.sqrt(rate * (1 - rate) / total + z * z / (4 * total**2)) / denominator
    return center - radius, center + radius


def key(row: dict[str, Any]) -> tuple[int, float, str, int]:
    return row["emitter_count"], row["directional_probability"], row["strategy"], row["base_seed"]


def cell_summary(part: list[dict[str, Any]], rng: random.Random) -> dict[str, Any]:
    times = [row["virtual_time_s"] for row in part]
    mean_low, mean_high = bootstrap_ci(times, rng)
    target = sum(row["within_6000"] for row in part)
    rate_low, rate_high = wilson(target, len(part))
    return {
        "emitter_count": part[0]["emitter_count"],
        "directional_probability": part[0]["directional_probability"],
        "strategy": part[0]["strategy"],
        "cases": len(part),
        "total_emitters": sum(row["emitter_count"] for row in part),
        "total_directional": sum(row["realized_directional_count"] for row in part),
        "realized_directional_fraction": statistics.fmean(row["realized_directional_fraction"] for row in part),
        "all_clear_cases": sum(row["all_cleared"] for row in part),
        "mean_time_s": statistics.fmean(times),
        "mean_time_ci95_low_s": mean_low,
        "mean_time_ci95_high_s": mean_high,
        "median_time_s": statistics.median(times),
        "p95_time_s": quantile(times, 0.95),
        "maximum_time_s": max(times),
        "within_6000_cases": target,
        "within_6000_rate": target / len(part),
        "within_6000_wilson_low": rate_low,
        "within_6000_wilson_high": rate_high,
        "mean_movement_time_s": statistics.fmean(row["movement_time_s"] for row in part),
        "mean_measure_time_s": statistics.fmean(row["measure_time_s"] for row in part),
        "mean_switch_time_s": statistics.fmean(row["switch_time_s"] for row in part),
        "mean_optical_time_s": statistics.fmean(row["optical_time_s"] for row in part),
        "mean_measure_count": statistics.fmean(row["measure_count"] for row in part),
        "mean_no_signal_rate": statistics.fmean(row["no_signal_rate"] for row in part),
        "mean_directional_loss_count": statistics.fmean(row["directional_loss_count"] for row in part),
        "mean_post_last_clear_time_s": statistics.fmean(row["post_last_clear_time_s"] for row in part),
    }


def difference_summary(label: str, metadata: dict[str, Any], differences: list[dict[str, float]], rng: random.Random) -> dict[str, Any]:
    times = [row["virtual_time_s"] for row in differences]
    low, high = bootstrap_ci(times, rng)
    output = {"contrast": label, **metadata, "paired_cases": len(times),
              "mean_time_difference_s": statistics.fmean(times), "ci95_low_s": low, "ci95_high_s": high,
              "median_time_difference_s": statistics.median(times),
              "positive_difference_rate": statistics.fmean(value > 0 for value in times)}
    for component in ("movement_time_s", "measure_time_s", "switch_time_s", "optical_time_s"):
        output[f"mean_{component}_difference"] = statistics.fmean(row[component] for row in differences)
    return output


def subtract(high: dict[str, Any], low: dict[str, Any]) -> dict[str, float]:
    return {column: high[column] - low[column] for column in
            ("virtual_time_s", "movement_time_s", "measure_time_s", "switch_time_s", "optical_time_s")}


def factorial_effect_sizes(rows: list[dict[str, Any]], strategy: str) -> dict[str, Any]:
    part = [row for row in rows if row["strategy"] == strategy]
    values = [row["virtual_time_s"] for row in part]
    grand = statistics.fmean(values)
    replicates = len({row["base_seed"] for row in part})
    n_means = {n: statistics.fmean(row["virtual_time_s"] for row in part if row["emitter_count"] == n) for n in COUNTS}
    p_means = {p: statistics.fmean(row["virtual_time_s"] for row in part if row["directional_probability"] == p) for p in PROBABILITIES}
    cell_means = {(n, p): statistics.fmean(row["virtual_time_s"] for row in part if row["emitter_count"] == n and row["directional_probability"] == p) for n in COUNTS for p in PROBABILITIES}
    seed_means = {seed: statistics.fmean(row["virtual_time_s"] for row in part if row["base_seed"] == seed) for seed in {row["base_seed"] for row in part}}
    ss_n = replicates * len(PROBABILITIES) * sum((n_means[n] - grand) ** 2 for n in COUNTS)
    ss_p = replicates * len(COUNTS) * sum((p_means[p] - grand) ** 2 for p in PROBABILITIES)
    ss_interaction = replicates * sum((cell_means[n, p] - n_means[n] - p_means[p] + grand) ** 2 for n in COUNTS for p in PROBABILITIES)
    ss_block = len(COUNTS) * len(PROBABILITIES) * sum((value - grand) ** 2 for value in seed_means.values())
    ss_total = sum((value - grand) ** 2 for value in values)
    ss_residual = max(ss_total - ss_n - ss_p - ss_interaction - ss_block, 0.0)
    treatment = ss_n + ss_p + ss_interaction
    return {
        "strategy": strategy,
        "grand_mean_time_s": grand,
        "ss_emitter_count": ss_n,
        "ss_directional_probability": ss_p,
        "ss_interaction": ss_interaction,
        "ss_seed_block": ss_block,
        "ss_residual": ss_residual,
        "treatment_ss_share_emitter_count": ss_n / treatment,
        "treatment_ss_share_directional_probability": ss_p / treatment,
        "treatment_ss_share_interaction": ss_interaction / treatment,
        "partial_eta_squared_emitter_count": ss_n / (ss_n + ss_residual),
        "partial_eta_squared_directional_probability": ss_p / (ss_p + ss_residual),
        "partial_eta_squared_interaction": ss_interaction / (ss_interaction + ss_residual),
        "model_note": "Balanced randomized-block decomposition; base_seed is the block. Partial eta squared uses factor SS/(factor SS+residual SS).",
    }


def svg_plot(path: Path, series: list[dict[str, Any]], y_label: str,
             horizontal: float | None = None, legend_location: str = "upper-right") -> None:
    """Write an SVG; the mean-time plot may move its legend inside the lower right."""
    width, height = 900, 560
    left, right, top, bottom = 90, 30, 35, 75
    xmin, xmax = 0.0, 1.0
    all_y = [y for item in series for _, y in item["points"]]
    ymin, ymax = min(all_y), max(all_y)
    padding = max((ymax - ymin) * 0.08, 1)
    ymin, ymax = ymin - padding, ymax + padding
    if horizontal is not None:
        ymin, ymax = min(ymin, horizontal), max(ymax, horizontal)
    sx = lambda value: left + value * (width - left - right)
    sy = lambda value: height - bottom - (value - ymin) / (ymax - ymin) * (height - top - bottom)
    colors = ["#4c78a8", "#72b7b2", "#e45756", "#f58518", "#54a24b", "#b279a2"]
    parts = [f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">', '<rect width="100%" height="100%" fill="white"/>',
             f'<line x1="{left}" y1="{height-bottom}" x2="{width-right}" y2="{height-bottom}" stroke="#222"/>', f'<line x1="{left}" y1="{top}" x2="{left}" y2="{height-bottom}" stroke="#222"/>']
    for i in range(5):
        x = i / 4
        parts.append(f'<text x="{sx(x):.1f}" y="{height-bottom+22}" text-anchor="middle" font-size="12">{x:.2f}</text>')
    for i in range(6):
        y = ymin + i * (ymax - ymin) / 5
        parts.append(f'<text x="{left-10}" y="{sy(y)+4:.1f}" text-anchor="end" font-size="12">{y:.0f}</text>')
    if horizontal is not None:
        parts.append(f'<line x1="{left}" y1="{sy(horizontal):.1f}" x2="{width-right}" y2="{sy(horizontal):.1f}" stroke="#222" stroke-dasharray="5 5"/>')
    for index, item in enumerate(series):
        color = colors[index % len(colors)]
        points = " ".join(f"{sx(x):.1f},{sy(y):.1f}" for x, y in item["points"])
        parts.append(f'<polyline points="{points}" fill="none" stroke="{color}" stroke-width="2"/>')
        parts.extend(f'<circle cx="{sx(x):.1f}" cy="{sy(y):.1f}" r="4" fill="{color}"/>' for x, y in item["points"])
        if legend_location == "lower-right":
            legend_x = width - 270
            legend_y = height - bottom - 100 + 18 * index
        elif legend_location == "upper-right":
            legend_x = width - 270
            legend_y = top + 18 * index
        else:
            raise ValueError(f"unsupported legend location: {legend_location}")
        parts += [f'<line x1="{legend_x}" y1="{legend_y}" x2="{legend_x+30}" y2="{legend_y}" stroke="{color}" stroke-width="2"/>',
                  f'<text x="{legend_x+40}" y="{legend_y+4}" font-size="12">{item["label"]}</text>']
    parts += [f'<text x="{(left+width-right)/2}" y="{height-20}" text-anchor="middle" font-size="14">Directional probability p</text>',
              f'<text x="20" y="{(top+height-bottom)/2}" text-anchor="middle" font-size="14" transform="rotate(-90 20 {(top+height-bottom)/2})">{y_label}</text>', '</svg>']
    path.write_text("\n".join(parts) + "\n", encoding="utf-8")


def render_response_figures(figures: Path, cells: list[dict[str, Any]], strategy_effects: list[dict[str, Any]],
                            render_existing_figures: bool = True) -> None:
    """Render the revised first figure and, when requested, the unchanged companion figures."""
    time_series, target_series, gain_series = [], [], []
    for strategy in STRATEGIES:
        short = "baseline" if strategy == STRATEGIES[0] else "adaptive"
        for n in COUNTS:
            selected = [row for row in cells if row["strategy"] == strategy and row["emitter_count"] == n]
            if len(selected) != len(PROBABILITIES):
                raise ValueError("factor_cell_summary.csv is incomplete")
            time_series.append({"label": f"{short}, N={n}", "points": [(row["directional_probability"], row["mean_time_s"]) for row in selected]})
            target_series.append({"label": f"{short}, N={n}", "points": [(row["directional_probability"], 100 * row["within_6000_rate"]) for row in selected]})
    for n in COUNTS:
        selected = [row for row in strategy_effects if row["emitter_count"] == n]
        if len(selected) != len(PROBABILITIES):
            raise ValueError("strategy_effect_by_cell.csv is incomplete")
        gain_series.append({"label": f"N={n}", "points": [(row["directional_probability"], -row["mean_time_difference_s"]) for row in selected]})
    svg_plot(figures / "mean_time_response_v2.svg", time_series, "Mean virtual time (s)",
             horizontal=6000, legend_location="lower-right")
    if render_existing_figures:
        svg_plot(figures / "within_6000_response.svg", target_series, "Fully cleared within 6000 s (%)")
        svg_plot(figures / "adaptive_time_saving.svg", gain_series, "Adaptive time saving vs baseline (s)", horizontal=0)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--experiment-dir", type=Path, default=EXPERIMENT)
    parser.add_argument("--render-mean-time-v2-only", action="store_true",
                        help="render only the revised mean-time figure from audited aggregate tables")
    args = parser.parse_args()
    experiment = args.experiment_dir
    tables = experiment / "tables"
    figures = experiment / "figures"
    tables.mkdir(parents=True, exist_ok=True)
    figures.mkdir(parents=True, exist_ok=True)
    if args.render_mean_time_v2_only:
        render_response_figures(
            figures,
            load_rows(tables / "factor_cell_summary.csv"),
            load_rows(tables / "strategy_effect_by_cell.csv"),
            render_existing_figures=False,
        )
        return
    rows = load_rows(experiment / "raw_cases.csv")
    rng = random.Random(BOOTSTRAP_SEED)
    seeds = sorted({row["base_seed"] for row in rows})
    expected = 2 * len(seeds) * len(COUNTS) * len(PROBABILITIES)
    if len(rows) != expected or len({key(row) for row in rows}) != expected:
        raise ValueError("controlled data are incomplete or contain duplicate factor keys")
    if any(not row["all_cleared"] for row in rows):
        raise ValueError("controlled data contain incomplete cases; inspect before aggregate analysis")
    if max(abs(row["cost_accounting_residual_s"]) for row in rows) > 1e-6:
        raise ValueError("cost accounting residual exceeds tolerance")
    lookup = {key(row): row for row in rows}

    cells = []
    for n in COUNTS:
        for p in PROBABILITIES:
            for strategy in STRATEGIES:
                part = [row for row in rows if row["emitter_count"] == n and row["directional_probability"] == p and row["strategy"] == strategy]
                cells.append(cell_summary(part, rng))
    write_csv(tables / "factor_cell_summary.csv", cells)

    strategy_effects = []
    for n in COUNTS:
        for p in PROBABILITIES:
            differences = [subtract(lookup[n, p, STRATEGIES[1], seed], lookup[n, p, STRATEGIES[0], seed]) for seed in seeds]
            strategy_effects.append(difference_summary("candidate_minus_baseline", {"emitter_count": n, "directional_probability": p}, differences, rng))
    write_csv(tables / "strategy_effect_by_cell.csv", strategy_effects)

    directional_effects = []
    for n in COUNTS:
        for strategy in STRATEGIES:
            differences = [subtract(lookup[n, 1.0, strategy, seed], lookup[n, 0.0, strategy, seed]) for seed in seeds]
            directional_effects.append(difference_summary("p1_minus_p0", {"emitter_count": n, "strategy": strategy}, differences, rng))
    write_csv(tables / "directional_effect_p1_minus_p0.csv", directional_effects)

    count_effects = []
    for p in PROBABILITIES:
        for strategy in STRATEGIES:
            differences = [subtract(lookup[16, p, strategy, seed], lookup[10, p, strategy, seed]) for seed in seeds]
            count_effects.append(difference_summary("n16_minus_n10", {"directional_probability": p, "strategy": strategy}, differences, rng))
    write_csv(tables / "emitter_count_effect_n16_minus_n10.csv", count_effects)

    adjacent_effects = []
    for n in COUNTS:
        for strategy in STRATEGIES:
            for low_p, high_p in zip(PROBABILITIES[:-1], PROBABILITIES[1:]):
                differences = [subtract(lookup[n, high_p, strategy, seed], lookup[n, low_p, strategy, seed]) for seed in seeds]
                adjacent_effects.append(difference_summary("adjacent_p_increment", {"emitter_count": n, "strategy": strategy, "p_low": low_p, "p_high": high_p}, differences, rng))
    write_csv(tables / "adjacent_directional_probability_effects.csv", adjacent_effects)

    interactions = []
    for strategy in STRATEGIES:
        differences = []
        for seed in seeds:
            at_16 = subtract(lookup[16, 1.0, strategy, seed], lookup[16, 0.0, strategy, seed])
            at_10 = subtract(lookup[10, 1.0, strategy, seed], lookup[10, 0.0, strategy, seed])
            differences.append({component: at_16[component] - at_10[component] for component in at_16})
        interactions.append(difference_summary("(p1-p0 at n16) minus (p1-p0 at n10)", {"strategy": strategy}, differences, rng))
    write_csv(tables / "count_direction_interaction_contrast.csv", interactions)

    effect_sizes = [factorial_effect_sizes(rows, strategy) for strategy in STRATEGIES]
    write_csv(tables / "blocked_factorial_effect_sizes.csv", effect_sizes)

    render_response_figures(figures, cells, strategy_effects)

    metadata = {
        "analysis": "controlled blocked full-factorial sensitivity analysis",
        "source": "controlled_experiment/raw_cases.csv",
        "runtime_dependencies": "Python standard library only",
        "bootstrap_seed": BOOTSTRAP_SEED,
        "bootstrap_repetitions": BOOTSTRAP_REPS,
        "bootstrap_unit": "base_seed; all reported contrasts are within-seed before resampling",
        "integrity": {"expected_rows": expected, "observed_rows": len(rows), "unique_factor_keys": len({key(row) for row in rows}),
                      "all_clear_runs": sum(row["all_cleared"] for row in rows),
                      "maximum_absolute_cost_residual_s": max(abs(row["cost_accounting_residual_s"]) for row in rows)},
    }
    (experiment / "analysis_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"directional_effects": directional_effects, "count_effects": count_effects,
                      "interactions": interactions, "effect_sizes": effect_sizes}, indent=2))


if __name__ == "__main__":
    main()
