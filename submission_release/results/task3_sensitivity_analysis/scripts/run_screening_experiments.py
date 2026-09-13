#!/usr/bin/env python3
"""Run a time-bounded Task 3 sensitivity screening design."""

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
import shlex
import statistics
import sys
import time
from typing import Any

import numpy as np

REPOSITORY = Path(__file__).resolve().parents[3]
if str(REPOSITORY) not in sys.path:
    sys.path.insert(0, str(REPOSITORY))

from task3.src.config import PhysicalConfig, PlannerConfig
from task3.src.dynamic_open_route_controller import DynamicOpenRouteController
from task3.src.mock_simulator import MockSimulator, Scenario, Source, random_scenario
from task3.src.policies import POLICIES


BASE_OVERRIDES = dict(POLICIES["candidate_057_posterior_free"].planner_overrides)
P1_CONFIGS: dict[str, dict[str, Any]] = {
    "default": {},
    "grid_2p5": {"grid_step_m": 2.5},
    "grid_10": {"grid_step_m": 10.0},
    "probe_budget_0": {"opportunistic_probe_budget": 0},
    "probe_budget_48": {"opportunistic_probe_budget": 48},
    "probe_limit_0": {"optical_probe_limit": 0},
    "probe_limit_3": {"optical_probe_limit": 3},
    "completion_samples_15": {"completion_sample_count": 15},
    "posterior_off": {"posterior_completion": False},
    "free_order_off": {"free_coverage_order": False},
    "shared_stops_off": {"shared_stop_measurements": False},
}
P2_L9 = (
    (10, 0.5, (975.0, 1475.0)), (10, 1.0, (1000.0, 1500.0)), (10, 1.5, (1100.0, 1600.0)),
    (13, 0.5, (1000.0, 1500.0)), (13, 1.0, (1100.0, 1600.0)), (13, 1.5, (975.0, 1475.0)),
    (16, 0.5, (1100.0, 1600.0)), (16, 1.0, (975.0, 1475.0)), (16, 1.5, (1000.0, 1500.0)),
)
P3_PATTERNS = ("area_uniform", "boundary_heavy", "clustered", "near_pairs", "large_angular_gap")
FIELDS = (
    "phase", "block_seed", "configuration", "source_count", "bearing_error_deg",
    "reception_min_m", "reception_max_m", "spatial_pattern", "planner_overrides_json",
    "success", "controller_success", "cleared_count", "all_sources", "clear_ratio",
    "virtual_time_s", "time_per_source_s", "movement_s", "measurement_s", "switching_s",
    "optical_s", "laser_s", "action_count", "wall_runtime_s", "fallback_misses",
    "probe_attempts", "probe_successes", "termination_reason", "error",
)


class ScaledErrorSimulator(MockSimulator):
    """Use the configured error bound while preserving the location-fixed law."""

    def _error_deg(self, channel: int, position: tuple[float, float]) -> float:
        key = f"{self.scenario.seed}:{channel}:{position[0]:.6f}:{position[1]:.6f}".encode()
        value = int.from_bytes(hashlib.sha256(key).digest()[:8], "big") / 2**64
        return 1.99 * self.physical.bearing_error_deg * value - 0.995 * self.physical.bearing_error_deg


def latent_template(seed: int, pattern: str) -> list[tuple[int, tuple[float, float], float]]:
    rng = np.random.default_rng(seed)
    channels = rng.choice(np.arange(1, 21), 16, replace=False)
    radius_u, angle_u, receive_u = rng.random(16), rng.random(16), rng.random(16)
    if pattern == "area_uniform":
        radii, angles = 1800 * np.sqrt(radius_u), 2 * math.pi * angle_u
        points = np.column_stack((radii * np.cos(angles), radii * np.sin(angles)))
    elif pattern == "boundary_heavy":
        radii, angles = 1800 * np.sqrt(0.75 + 0.25 * radius_u), 2 * math.pi * angle_u
        points = np.column_stack((radii * np.cos(angles), radii * np.sin(angles)))
    elif pattern == "large_angular_gap":
        radii, angles = 1800 * np.sqrt(radius_u), 1.5 * math.pi * angle_u
        points = np.column_stack((radii * np.cos(angles), radii * np.sin(angles)))
    elif pattern == "clustered":
        center_radius = 900 * math.sqrt(float(rng.random()))
        center_angle = 2 * math.pi * float(rng.random())
        center = np.array([center_radius * math.cos(center_angle), center_radius * math.sin(center_angle)])
        points = center + rng.normal(0, 220, (16, 2))
        norms = np.linalg.norm(points, axis=1)
        points = np.array([point if norm <= 1795 else point * 1795 / norm for point, norm in zip(points, norms)])
    elif pattern == "near_pairs":
        base_r = 1700 * np.sqrt(rng.random(8))
        base_a = 2 * math.pi * rng.random(8)
        bases = np.column_stack((base_r * np.cos(base_a), base_r * np.sin(base_a)))
        offsets = np.column_stack((20 * np.cos(2 * math.pi * rng.random(8)), 20 * np.sin(2 * math.pi * rng.random(8))))
        points = np.vstack([value for pair in zip(bases, bases + offsets) for value in pair])
    else:
        raise ValueError(pattern)
    return [(int(channel), (float(point[0]), float(point[1])), float(u))
            for channel, point, u in zip(channels, points, receive_u)]


def scenario_from_template(seed: int, count: int, pattern: str, reception: tuple[float, float]) -> Scenario:
    low, high = reception
    items = latent_template(seed, pattern)[:count]
    sources = tuple(Source(channel, point, low + u * (high - low)) for channel, point, u in items)
    return Scenario(f"screen-{seed}-{pattern}-{count}-{low:g}-{high:g}", seed, sources)


def execute(spec: dict[str, Any]) -> dict[str, Any]:
    started = time.perf_counter()
    try:
        physical = PhysicalConfig(
            bearing_error_deg=spec["bearing_error_deg"],
            reception_min_m=spec["reception_min_m"],
            reception_max_m=spec["reception_max_m"],
        )
        if spec["phase"] == "P1":
            scenario = random_scenario(spec["block_seed"], physical)
        else:
            scenario = scenario_from_template(
                spec["block_seed"], spec["source_count"], spec["spatial_pattern"],
                (spec["reception_min_m"], spec["reception_max_m"]),
            )
        overrides = BASE_OVERRIDES | spec["planner_overrides"] | {"seed": spec["block_seed"]}
        planner = PlannerConfig(**overrides)
        simulator = ScaledErrorSimulator(scenario, physical)
        result = DynamicOpenRouteController(simulator, physical, planner, scenario.total).run()
        strict_success = len(simulator.cleared) == scenario.total
        diagnostics = result.diagnostics
        probes = [row for row in diagnostics if row["type"] == "bounded_enroute_probe"]
        breakdown = asdict(result.time_breakdown)
        return {
            **{key: spec[key] for key in ("phase", "block_seed", "configuration", "bearing_error_deg",
                                          "reception_min_m", "reception_max_m", "spatial_pattern")},
            "source_count": scenario.total,
            "planner_overrides_json": json.dumps(spec["planner_overrides"], sort_keys=True),
            "success": strict_success, "controller_success": result.success,
            "cleared_count": len(simulator.cleared), "all_sources": scenario.total,
            "clear_ratio": len(simulator.cleared) / scenario.total,
            "virtual_time_s": result.virtual_time_s,
            "time_per_source_s": result.virtual_time_s / scenario.total,
            **{key: breakdown[key] for key in ("movement_s", "measurement_s", "switching_s", "optical_s", "laser_s")},
            "action_count": result.action_count, "wall_runtime_s": time.perf_counter() - started,
            "fallback_misses": sum(row["type"] == "fallback_miss" for row in diagnostics),
            "probe_attempts": len(probes), "probe_successes": sum(row["success"] for row in probes),
            "termination_reason": result.termination_reason, "error": "",
        }
    except Exception as exc:
        return {**{key: spec.get(key, "") for key in FIELDS}, "success": False,
                "wall_runtime_s": time.perf_counter() - started, "error": f"{type(exc).__name__}: {exc}"}


def specifications(phase: str, replicates: int) -> list[dict[str, Any]]:
    specs = []
    if phase in ("all", "P1"):
        for offset in range(replicates):
            for name, overrides in P1_CONFIGS.items():
                specs.append({"phase": "P1", "block_seed": 20800000 + offset, "configuration": name,
                              "source_count": None, "bearing_error_deg": 1.0,
                              "reception_min_m": 1000.0, "reception_max_m": 1500.0,
                              "spatial_pattern": "area_uniform", "planner_overrides": overrides})
    if phase in ("all", "P2"):
        for offset in range(replicates):
            for count, error, reception in P2_L9:
                specs.append({"phase": "P2", "block_seed": 20810000 + offset,
                              "configuration": f"n{count}_e{error:g}_r{int(reception[0])}",
                              "source_count": count, "bearing_error_deg": error,
                              "reception_min_m": reception[0], "reception_max_m": reception[1],
                              "spatial_pattern": "area_uniform", "planner_overrides": {}})
    if phase in ("all", "P3"):
        p3_replicates = max(1, replicates // 2)
        for offset in range(p3_replicates):
            for pattern in P3_PATTERNS:
                for count in (10, 13, 16):
                    specs.append({"phase": "P3", "block_seed": 20820000 + offset,
                                  "configuration": f"{pattern}_n{count}", "source_count": count,
                                  "bearing_error_deg": 1.0, "reception_min_m": 1000.0,
                                  "reception_max_m": 1500.0, "spatial_pattern": pattern,
                                  "planner_overrides": {}})
    return specs


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--phase", choices=("all", "P1", "P2", "P3"), default="all")
    parser.add_argument("--replicates", type=int, default=12)
    parser.add_argument("--workers", type=int, default=30)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    specs = specifications(args.phase, args.replicates)
    manifest = {
        "created_utc": datetime.now(timezone.utc).isoformat(), "command": shlex.join(sys.argv),
        "design": "time-bounded sensitivity screening; common-seed blocks",
        "phase": args.phase, "replicates": args.replicates, "workers": args.workers,
        "runs": len(specs), "P1_configurations": P1_CONFIGS, "P2_L9": P2_L9,
        "P3_patterns": P3_PATTERNS, "base_policy": "candidate_057_posterior_free",
        "source_sha256": {str(path.relative_to(REPOSITORY)): hashlib.sha256(path.read_bytes()).hexdigest()
                          for path in sorted((REPOSITORY / "task3/src").glob("*.py"))},
    }
    (args.output_dir / "design.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    path = args.output_dir / "raw_runs.csv"
    rows = []
    started = time.perf_counter()
    with path.open("x", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS)
        writer.writeheader()
        with ProcessPoolExecutor(max_workers=args.workers) as executor:
            for index, row in enumerate(executor.map(execute, specs, chunksize=1), start=1):
                writer.writerow({key: row.get(key, "") for key in FIELDS})
                rows.append(row)
                if index % 25 == 0 or index == len(specs):
                    handle.flush()
                    print(f"completed {index}/{len(specs)}", flush=True)
    summary = {"runs": len(rows), "successful": sum(bool(row.get("success")) for row in rows),
               "errors": sum(bool(row.get("error")) for row in rows),
               "elapsed_wall_s": time.perf_counter() - started,
               "worker_wall_s": sum(float(row.get("wall_runtime_s", 0)) for row in rows),
               "mean_worker_wall_s": statistics.fmean(float(row.get("wall_runtime_s", 0)) for row in rows)}
    (args.output_dir / "run_summary.json").write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
