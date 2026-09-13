#!/usr/bin/env python3
"""Run the controlled Task 4 emitter-count/type-probability experiment.

For each base seed, one ordered 16-emitter template is generated. Smaller N
uses a prefix of the same template, and p changes only the directional flags.
All positions, channels, receive radii, and pre-generated directions are frozen.
"""

from __future__ import annotations

import argparse
from concurrent.futures import ProcessPoolExecutor
import csv
from dataclasses import asdict
from datetime import datetime, timezone
import hashlib
import json
import math
from pathlib import Path
import random
import shlex
import statistics
import sys
import time
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[3]
if str(REPOSITORY_ROOT) not in sys.path:
    sys.path.insert(0, str(REPOSITORY_ROOT))

from experiments.t4_local.engine import Emitter, LocalSimulator, SimulatorConfig
from task4.client import InProcessClient
from task4.strategies import make_strategy


BASELINE = "double_ring_optical_clear_probe"
CANDIDATE = "adaptive_double_ring_clear_probe"
BASELINE_CONFIG = {
    "grid_spacing": 600.0,
    "grid_half_extent": 1800.0,
    "lattice_spacing": 731.0,
    "replacement_distance_m": 550.0,
    "max_replaced_waypoints": 0,
    "early_clear_radius_m": 35.0,
    "route_length_slack_m": 100.0,
}
CANDIDATE_CONFIG = BASELINE_CONFIG | {"early_clear_radius_m": 50.0}
EMITTER_COUNTS = (10, 13, 16)
DIRECTIONAL_PROBABILITIES = (0.0, 0.25, 0.5, 0.75, 1.0)


def source_hash(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def make_template(seed: int) -> list[dict[str, float | int]]:
    config = SimulatorConfig(seed=seed)
    rng = random.Random(seed)
    channels = rng.sample(range(1, 21), 16)
    template = []
    for channel in channels:
        radial_distance = config.arena_radius_m * math.sqrt(rng.random())
        angle = rng.random() * 2 * math.pi
        template.append(
            {
                "channel": channel,
                "x": radial_distance * math.cos(angle),
                "y": radial_distance * math.sin(angle),
                "receive_radius_m": rng.uniform(config.receive_radius_min_m, config.receive_radius_max_m),
                "direction_deg": rng.uniform(0.0, 360.0),
                "directional_score": rng.random(),
            }
        )
    return template


def instantiate(template: list[dict[str, float | int]], emitter_count: int, probability: float) -> list[Emitter]:
    emitters = []
    for item in template[:emitter_count]:
        directional = float(item["directional_score"]) < probability
        emitters.append(
            Emitter(
                channel=int(item["channel"]),
                x=float(item["x"]),
                y=float(item["y"]),
                receive_radius_m=float(item["receive_radius_m"]),
                directional=directional,
                direction_deg=float(item["direction_deg"]) if directional else None,
            )
        )
    return emitters


def run_one(
    strategy_name: str,
    strategy_config: dict[str, Any],
    seed: int,
    emitter_count: int,
    probability: float,
    template: list[dict[str, float | int]],
) -> dict[str, Any]:
    config = SimulatorConfig(
        seed=seed,
        min_emitters=emitter_count,
        max_emitters=emitter_count,
        directional_probability=probability,
    )
    simulator = LocalSimulator(config, emitters=instantiate(template, emitter_count, probability))
    client = InProcessClient(simulator, config.robot_id)
    strategy = make_strategy(strategy_name, **strategy_config)
    started = time.perf_counter()
    result = strategy.run(client)
    wall_time = time.perf_counter() - started
    truth = simulator.truth_summary()
    stats = truth["stats"]
    switch_time = stats["channel_switch_count"] * config.switch_time_s
    optical_time = stats["optical_count"] * config.optical_time_s
    successful_clear_time = stats["clear_success_count"] * config.clear_time_s
    accounting = stats["movement_time_s"] + stats["measure_time_s"] + switch_time + optical_time + successful_clear_time
    return {
        "base_seed": seed,
        "emitter_count": emitter_count,
        "directional_probability": probability,
        "realized_directional_count": truth["directional_count"],
        "realized_directional_fraction": truth["directional_count"] / emitter_count,
        "strategy": strategy_name,
        "all_cleared": truth["all_cleared"],
        "cleared_count": truth["cleared_count"],
        "virtual_time_s": truth["virtual_time_s"],
        "within_6000": bool(truth["all_cleared"] and truth["virtual_time_s"] <= 6000),
        "movement_time_s": stats["movement_time_s"],
        "movement_distance_m": stats["movement_distance_m"],
        "measure_time_s": stats["measure_time_s"],
        "measure_count": stats["measure_count"],
        "no_signal_count": stats["no_signal_count"],
        "no_signal_rate": stats["no_signal_count"] / stats["measure_count"],
        "channel_switch_count": stats["channel_switch_count"],
        "switch_time_s": switch_time,
        "optical_count": stats["optical_count"],
        "optical_time_s": optical_time,
        "clear_success_count": stats["clear_success_count"],
        "successful_clear_time_s": successful_clear_time,
        "directional_loss_count": truth["directional_loss_count"],
        "directional_reacquisition_count": truth["directional_reacquisition_count"],
        "first_clear_time_s": truth["first_clear_time_s"],
        "last_clear_time_s": truth["last_clear_time_s"],
        "post_last_clear_time_s": truth["virtual_time_s"] - truth["last_clear_time_s"] if truth["all_cleared"] else None,
        "seen_channel_count": len(result.seen_channels),
        "cost_accounting_residual_s": truth["virtual_time_s"] - accounting,
        "wall_time_s": wall_time,
    }


def run_pair(arguments: tuple[int, int, float]) -> tuple[dict[str, Any], dict[str, Any]]:
    seed, emitter_count, probability = arguments
    template = make_template(seed)
    baseline = run_one(BASELINE, BASELINE_CONFIG, seed, emitter_count, probability, template)
    candidate = run_one(CANDIDATE, CANDIDATE_CONFIG, seed, emitter_count, probability, template)
    if baseline["realized_directional_count"] != candidate["realized_directional_count"]:
        raise RuntimeError("paired strategies received different emitter types")
    if abs(baseline["cost_accounting_residual_s"]) > 1e-6 or abs(candidate["cost_accounting_residual_s"]) > 1e-6:
        raise RuntimeError("time cost accounting failed")
    return baseline, candidate


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--seed-start", type=int, default=60000)
    parser.add_argument("--replicates", type=int, default=100)
    parser.add_argument("--workers", type=int, default=4)
    args = parser.parse_args()
    if args.replicates < 1 or args.workers < 1:
        parser.error("replicates and workers must be positive")
    args.output_dir.mkdir(parents=True, exist_ok=True)
    raw_path = args.output_dir / "raw_cases.csv"
    manifest_path = args.output_dir / "design.json"
    if raw_path.exists() or manifest_path.exists():
        parser.error("controlled experiment outputs already exist; use a new output directory")

    seeds = list(range(args.seed_start, args.seed_start + args.replicates))
    arguments = [(seed, count, probability) for seed in seeds for count in EMITTER_COUNTS for probability in DIRECTIONAL_PROBABILITIES]
    design = {
        "generated_at_utc": datetime.now(timezone.utc).isoformat(),
        "command": shlex.join(sys.argv),
        "design": "blocked full factorial with nested emitter prefixes and monotone type-score thresholds",
        "base_seeds": seeds,
        "replicates_per_cell": args.replicates,
        "emitter_counts": EMITTER_COUNTS,
        "directional_probabilities": DIRECTIONAL_PROBABILITIES,
        "factor_cells": len(EMITTER_COUNTS) * len(DIRECTIONAL_PROBABILITIES),
        "paired_cases_per_strategy": len(arguments),
        "total_strategy_runs": 2 * len(arguments),
        "workers": args.workers,
        "baseline": {"strategy": BASELINE, "strategy_config": BASELINE_CONFIG},
        "candidate": {"strategy": CANDIDATE, "strategy_config": CANDIDATE_CONFIG},
        "controlled_attributes": ["channel", "x", "y", "receive_radius_m", "direction_deg"],
        "type_rule": "directional iff pre-generated directional_score < directional_probability",
        "nesting_rule": "N=10 and N=13 use prefixes of the same ordered N=16 template",
        "generator_note": "All latent attributes are sampled independently before factor levels are applied; this is a controlled local generator, not the official generator.",
        "source_sha256": {
            "adaptive_double_ring_clear_probe.py": source_hash(REPOSITORY_ROOT / "task4/strategies/adaptive_double_ring_clear_probe.py"),
            "double_ring_optical_clear_probe.py": source_hash(REPOSITORY_ROOT / "task4/strategies/double_ring_optical_clear_probe.py"),
            "run_controlled_experiment.py": source_hash(Path(__file__)),
        },
    }
    manifest_path.write_text(json.dumps(design, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")

    rows: list[dict[str, Any]] = []
    with ProcessPoolExecutor(max_workers=args.workers) as executor:
        for index, (baseline, candidate) in enumerate(executor.map(run_pair, arguments), start=1):
            rows.extend((baseline, candidate))
            if index % 50 == 0 or index == len(arguments):
                print(f"completed {index}/{len(arguments)} paired cases", flush=True)
    with raw_path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    failures = [row for row in rows if not row["all_cleared"]]
    completion = {
        "rows": len(rows),
        "paired_cases": len(arguments),
        "failure_count": len(failures),
        "failure_keys": [[row["base_seed"], row["emitter_count"], row["directional_probability"], row["strategy"]] for row in failures],
        "mean_wall_time_s_per_run": statistics.fmean(row["wall_time_s"] for row in rows),
        "total_recorded_worker_wall_time_s": sum(row["wall_time_s"] for row in rows),
    }
    (args.output_dir / "run_summary.json").write_text(json.dumps(completion, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(completion, indent=2))


if __name__ == "__main__":
    main()
