from __future__ import annotations

import argparse
import csv
from datetime import datetime, timezone
import json
from pathlib import Path
import secrets
import statistics
from typing import Any

from experiments.t4_local.benchmark import run_batch


def _quantile(values: list[float], probability: float) -> float:
    ordered = sorted(values)
    index = (len(ordered) - 1) * probability
    lower = int(index)
    upper = min(lower + 1, len(ordered) - 1)
    return ordered[lower] * (upper - index) + ordered[upper] * (index - lower)


def _case_summary(row: dict[str, str]) -> dict[str, Any]:
    return {
        "seed": int(row["seed"]),
        "virtual_time_s": float(row["virtual_time_s"]),
        "all_cleared": row["all_cleared"] == "True",
        "emitter_count": int(row["emitter_count"]),
        "directional_count": int(row["directional_count"]),
        "movement_distance_m": float(row["movement_distance_m"]),
        "measure_count": int(row["measure_count"]),
        "no_signal_count": int(row["no_signal_count"]),
    }


def _metric(values: list[float]) -> dict[str, float]:
    return {
        "minimum": min(values),
        "mean": statistics.fmean(values),
        "population_stddev": statistics.pstdev(values),
        "p25": _quantile(values, 0.25),
        "median": _quantile(values, 0.5),
        "p75": _quantile(values, 0.75),
        "p90": _quantile(values, 0.9),
        "p95": _quantile(values, 0.95),
        "p99": _quantile(values, 0.99),
        "maximum": max(values),
    }


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Run T4 local cases selected from operating-system entropy"
    )
    parser.add_argument("--cases", type=int, default=1000)
    parser.add_argument("--strategy", default="replacement_aware_clear_probe")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--lattice-spacing", type=float, default=731.0)
    parser.add_argument("--replacement-distance", type=float, default=400.0)
    parser.add_argument("--max-replaced-waypoints", type=int, default=2)
    parser.add_argument("--early-clear-radius", type=float)
    parser.add_argument("--directional-probability", type=float, default=0.5)
    parser.add_argument("--route-length-slack", type=float)
    parser.add_argument("--heuristic-depth", type=int)
    parser.add_argument("--geometry-credit", type=float)
    parser.add_argument(
        "--selected-seeds",
        type=Path,
        help="reuse a manifest originally sampled from OS entropy for a paired A/B run",
    )
    args = parser.parse_args()
    if args.cases <= 0:
        parser.error("--cases must be positive")

    if args.selected_seeds:
        source_manifest = json.loads(args.selected_seeds.read_text(encoding="utf-8"))
        available_seeds = [int(seed) for seed in source_manifest["seeds"]]
        if args.cases > len(available_seeds):
            parser.error("--cases exceeds the selected seed manifest")
        selected_seeds = available_seeds[: args.cases]
        selection_method = f"paired reuse of OS-entropy manifest: {args.selected_seeds}"
        generated_at = source_manifest["generated_at_utc"]
    else:
        random_source = secrets.SystemRandom()
        seeds: set[int] = set()
        while len(seeds) < args.cases:
            seeds.add(random_source.randrange(0, 2**32))
        selected_seeds = list(seeds)
        random_source.shuffle(selected_seeds)
        selection_method = "secrets.SystemRandom backed by operating-system entropy"
        generated_at = datetime.now(timezone.utc).isoformat()

    args.output_dir.mkdir(parents=True, exist_ok=True)
    manifest = {
        "selection_method": selection_method,
        "selection_rng_seed": None,
        "generated_at_utc": generated_at,
        "seed_domain": "[0, 2**32)",
        "unique": True,
        "cases": len(selected_seeds),
        "seeds": selected_seeds,
    }
    (args.output_dir / "selected_seeds.json").write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8"
    )

    strategy_config = {
        "grid_spacing": 600.0,
        "grid_half_extent": 1800.0,
        "lattice_spacing": args.lattice_spacing,
        "replacement_distance_m": args.replacement_distance,
        "max_replaced_waypoints": args.max_replaced_waypoints,
    }
    if args.early_clear_radius is not None:
        strategy_config["early_clear_radius_m"] = args.early_clear_radius
    if args.route_length_slack is not None:
        strategy_config["route_length_slack_m"] = args.route_length_slack
    if args.heuristic_depth is not None:
        strategy_config["heuristic_depth"] = args.heuristic_depth
    if args.geometry_credit is not None:
        strategy_config["geometry_credit_s"] = args.geometry_credit
    base_summary = run_batch(
        args.strategy,
        selected_seeds,
        args.output_dir,
        strategy_config,
        {"directional_probability": args.directional_probability},
    )

    with (args.output_dir / "cases.csv").open(newline="", encoding="utf-8") as handle:
        cases = list(csv.DictReader(handle))
    ranked = sorted(cases, key=lambda row: float(row["virtual_time_s"]))
    times = [float(row["virtual_time_s"]) for row in cases]
    movements = [float(row["movement_distance_m"]) for row in cases]
    measurements = [float(row["measure_count"]) for row in cases]
    report = {
        "strategy": args.strategy,
        "strategy_config": strategy_config,
        "simulator_config": {"directional_probability": args.directional_probability},
        "random_selection": {key: value for key, value in manifest.items() if key != "seeds"},
        "aggregate_clear_rate": base_summary["aggregate_clear_rate"],
        "all_clear_case_rate": base_summary["all_clear_case_rate"],
        "failure_seeds": base_summary["failure_seeds"],
        "virtual_time_s": _metric(times),
        "movement_distance_m": _metric(movements),
        "measure_count": _metric(measurements),
        "fastest_case": _case_summary(ranked[0]),
        "slowest_case": _case_summary(ranked[-1]),
        "fastest_10": [_case_summary(row) for row in ranked[:10]],
        "slowest_10": [_case_summary(row) for row in ranked[-10:]],
        "base_batch_summary": base_summary,
    }
    (args.output_dir / "random_summary.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    lines = [
        "# T4 random local benchmark",
        "",
        f"- strategy: `{args.strategy}`",
        f"- cases: `{len(cases)}` unique seeds selected from OS entropy",
        f"- all-clear rate: `{report['all_clear_case_rate']}`",
        f"- minimum virtual time: `{report['virtual_time_s']['minimum']}` s",
        f"- mean virtual time: `{report['virtual_time_s']['mean']}` s",
        f"- median virtual time: `{report['virtual_time_s']['median']}` s",
        f"- P90/P95/P99: `{report['virtual_time_s']['p90']}` / "
        f"`{report['virtual_time_s']['p95']}` / `{report['virtual_time_s']['p99']}` s",
        f"- maximum virtual time: `{report['virtual_time_s']['maximum']}` s",
        f"- population standard deviation: `{report['virtual_time_s']['population_stddev']}` s",
        f"- fastest seed: `{report['fastest_case']['seed']}`",
        f"- slowest seed: `{report['slowest_case']['seed']}`",
    ]
    (args.output_dir / "random_summary.md").write_text(
        "\n".join(lines) + "\n", encoding="utf-8"
    )
    print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
