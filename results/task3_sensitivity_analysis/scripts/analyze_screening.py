#!/usr/bin/env python3
"""Analyze the time-bounded Task 3 controlled sensitivity screening."""

from __future__ import annotations

import csv
import hashlib
import json
import math
import random
import statistics
from pathlib import Path
from typing import Any, Iterable


ROOT = Path(__file__).resolve().parents[1]
EXPERIMENT = ROOT / "screening_experiment"
REPLICATION = ROOT / "screening_p3_complete"
TABLES = EXPERIMENT / "tables"
BOOTSTRAP_REPS = 10_000
BOOTSTRAP_SEED = 20260915


def load(path: Path) -> list[dict[str, Any]]:
    output = []
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
            output.append(row)
    return output


def write(path: Path, rows: list[dict[str, Any]]) -> None:
    if not rows:
        raise ValueError(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


def quantile(values: Iterable[float], probability: float) -> float:
    ordered = sorted(float(value) for value in values)
    index = (len(ordered) - 1) * probability
    low, high = math.floor(index), math.ceil(index)
    return ordered[low] + (ordered[high] - ordered[low]) * (index - low)


def bootstrap(values: list[float], rng: random.Random) -> tuple[float, float]:
    estimates = [statistics.fmean(values[rng.randrange(len(values))] for _ in values)
                 for _ in range(BOOTSTRAP_REPS)]
    return quantile(estimates, 0.025), quantile(estimates, 0.975)


def group_summary(part: list[dict[str, Any]], extra: dict[str, Any]) -> dict[str, Any]:
    times = [row["virtual_time_s"] for row in part]
    return {**extra, "runs": len(part), "successful_runs": sum(row["success"] for row in part),
            "sources": sum(row["source_count"] for row in part),
            "mean_case_time_s": statistics.fmean(times),
            "aggregate_time_per_source_s": sum(times) / sum(row["source_count"] for row in part),
            "p95_case_time_s": quantile(times, 0.95),
            "within_220_s_per_source_rate": statistics.fmean(row["time_per_source_s"] <= 220 for row in part),
            "mean_movement_s": statistics.fmean(row["movement_s"] for row in part),
            "mean_measurement_s": statistics.fmean(row["measurement_s"] for row in part),
            "mean_fallback_misses": statistics.fmean(row["fallback_misses"] for row in part),
            "probe_success_rate": sum(row["probe_successes"] for row in part) / max(sum(row["probe_attempts"] for row in part), 1)}


def p1_analysis(rows: list[dict[str, Any]], rng: random.Random) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    configurations = sorted({row["configuration"] for row in rows})
    summaries = [group_summary([row for row in rows if row["configuration"] == name], {"configuration": name})
                 for name in configurations]
    lookup = {(row["block_seed"], row["configuration"]): row for row in rows}
    seeds = sorted({row["block_seed"] for row in rows})
    effects = []
    for name in configurations:
        if name == "default":
            continue
        case_delta = [lookup[seed, name]["virtual_time_s"] - lookup[seed, "default"]["virtual_time_s"] for seed in seeds]
        source_delta = [case_delta[index] / lookup[seed, "default"]["source_count"] for index, seed in enumerate(seeds)]
        low, high = bootstrap(source_delta, rng)
        effects.append({"configuration": name, "paired_cases": len(seeds),
                        "mean_delta_s_per_source": statistics.fmean(source_delta),
                        "bootstrap_ci95_low_s_per_source": low, "bootstrap_ci95_high_s_per_source": high,
                        "mean_case_delta_s": statistics.fmean(case_delta),
                        "faster_than_default_cases": sum(value < 0 for value in case_delta),
                        "worst_regression_s": max(0.0, max(case_delta))})
    return summaries, sorted(effects, key=lambda row: row["mean_delta_s_per_source"])


def p2_analysis(rows: list[dict[str, Any]], rng: random.Random) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    factors = {
        "source_count": ("source_count", lambda row: str(row["source_count"])),
        "bearing_error_deg": ("bearing_error_deg", lambda row: f'{row["bearing_error_deg"]:g}'),
        "reception_band": ("reception_min_m", lambda row: f'{int(row["reception_min_m"])}-{int(row["reception_max_m"])}'),
    }
    summaries = []
    for factor, (_sort, getter) in factors.items():
        levels = sorted({getter(row) for row in rows}, key=lambda value: float(value.split("-")[0]))
        for level in levels:
            part = [row for row in rows if getter(row) == level]
            summaries.append(group_summary(part, {"factor": factor, "level": level}))

    contrast_specs = (
        ("source_count", "10", "16"),
        ("bearing_error_deg", "0.5", "1.5"),
        ("reception_band", "975-1475", "1100-1600"),
    )
    seeds = sorted({row["block_seed"] for row in rows})
    contrasts = []
    for factor, low_level, high_level in contrast_specs:
        getter = factors[factor][1]
        case_deltas, source_deltas = [], []
        for seed in seeds:
            low = [row for row in rows if row["block_seed"] == seed and getter(row) == low_level]
            high = [row for row in rows if row["block_seed"] == seed and getter(row) == high_level]
            case_deltas.append(statistics.fmean(row["virtual_time_s"] for row in high) -
                               statistics.fmean(row["virtual_time_s"] for row in low))
            source_deltas.append(statistics.fmean(row["time_per_source_s"] for row in high) -
                                 statistics.fmean(row["time_per_source_s"] for row in low))
        case_low, case_high = bootstrap(case_deltas, rng)
        source_low, source_high = bootstrap(source_deltas, rng)
        contrasts.append({"factor": factor, "contrast": f"{high_level} minus {low_level}", "blocks": len(seeds),
                          "mean_case_delta_s": statistics.fmean(case_deltas),
                          "case_delta_ci95_low_s": case_low, "case_delta_ci95_high_s": case_high,
                          "mean_delta_s_per_source": statistics.fmean(source_deltas),
                          "source_delta_ci95_low_s": source_low, "source_delta_ci95_high_s": source_high})
    return summaries, contrasts


def p3_analysis(rows: list[dict[str, Any]], rng: random.Random) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    patterns = sorted({row["spatial_pattern"] for row in rows})
    counts = sorted({row["source_count"] for row in rows})
    summaries = [group_summary([row for row in rows if row["spatial_pattern"] == pattern and row["source_count"] == count],
                               {"spatial_pattern": pattern, "source_count": count})
                 for pattern in patterns for count in counts]
    lookup = {(row["block_seed"], row["spatial_pattern"], row["source_count"]): row for row in rows}
    seeds = sorted({row["block_seed"] for row in rows})
    effects = []
    for pattern in patterns:
        if pattern == "area_uniform":
            continue
        for count in counts:
            deltas = [lookup[seed, pattern, count]["virtual_time_s"] - lookup[seed, "area_uniform", count]["virtual_time_s"]
                      for seed in seeds]
            low, high = bootstrap(deltas, rng)
            effects.append({"spatial_pattern": pattern, "source_count": count, "paired_cases": len(seeds),
                            "mean_case_delta_vs_area_uniform_s": statistics.fmean(deltas),
                            "bootstrap_ci95_low_s": low, "bootstrap_ci95_high_s": high,
                            "slower_than_area_uniform_cases": sum(value > 0 for value in deltas)})
    return summaries, effects


def main() -> None:
    rng = random.Random(BOOTSTRAP_SEED)
    rows = load(EXPERIMENT / "raw_runs.csv")
    if len(rows) != 330 or len({(row["phase"], row["block_seed"], row["configuration"]) for row in rows}) != 330:
        raise ValueError("screening experiment is incomplete or duplicated")
    if any(row["error"] or not row["success"] for row in rows):
        raise ValueError("screening contains errors or strict-clear failures")
    if any(row["success"] != row["controller_success"] for row in rows):
        raise ValueError("controller success disagrees with simulator truth")
    accounting_residual = max(abs(row["virtual_time_s"] - sum(row[key] for key in
        ("movement_s", "measurement_s", "switching_s", "optical_s", "laser_s"))) for row in rows)
    if accounting_residual > 1e-6:
        raise ValueError("virtual-time component accounting failed")
    p1 = [row for row in rows if row["phase"] == "P1"]
    p2 = [row for row in rows if row["phase"] == "P2"]
    p3 = [row for row in rows if row["phase"] == "P3"]
    p1_summary, p1_effects = p1_analysis(p1, rng)
    p2_summary, p2_effects = p2_analysis(p2, rng)
    p3_summary, p3_effects = p3_analysis(p3, rng)
    write(TABLES / "p1_configuration_summary.csv", p1_summary)
    write(TABLES / "p1_paired_effects_vs_default.csv", p1_effects)
    write(TABLES / "p2_l9_factor_level_summary.csv", p2_summary)
    write(TABLES / "p2_l9_extreme_level_contrasts.csv", p2_effects)
    write(TABLES / "p3_spatial_cell_summary.csv", p3_summary)
    write(TABLES / "p3_paired_effects_vs_area_uniform.csv", p3_effects)

    repeated = load(REPLICATION / "raw_runs.csv")
    fields = ("block_seed", "configuration", "success", "cleared_count", "virtual_time_s", "movement_s", "measurement_s")
    deterministic = sorted(tuple(row[field] for field in fields) for row in p3) == sorted(tuple(row[field] for field in fields) for row in repeated)
    metadata = {"analysis": "time-bounded controlled sensitivity screening", "bootstrap_repetitions": BOOTSTRAP_REPS,
                "bootstrap_seed": BOOTSTRAP_SEED, "formal_runs": len(rows), "P1_runs": len(p1), "P2_runs": len(p2),
                "P3_runs": len(p3), "strict_successful_runs": sum(row["success"] for row in rows),
                "maximum_time_accounting_residual_s": accounting_residual,
                "P3_repeat_runs_not_counted": len(repeated), "P3_repeat_deterministic_match": deterministic,
                "raw_sha256": hashlib.sha256((EXPERIMENT / "raw_runs.csv").read_bytes()).hexdigest(),
                "runner_sha256": hashlib.sha256((ROOT / "scripts/run_screening_experiments.py").read_bytes()).hexdigest(),
                "analysis_script_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
                "note": "Screening sample sizes are 12 blocks for P1/P2 and 6 for P3; intervals are diagnostic, not confirmatory."}
    (EXPERIMENT / "analysis_metadata.json").write_text(json.dumps(metadata, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"metadata": metadata, "P1_effects": p1_effects, "P2_effects": p2_effects,
                      "P3_effects": p3_effects}, indent=2))


if __name__ == "__main__":
    main()
