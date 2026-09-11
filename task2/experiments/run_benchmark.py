"""Fair benchmark: shared scenarios, candidates, evaluator, and seed stream."""
from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
import time

import numpy as np
import pandas as pd
from shapely.geometry import Point

from src.config import PhysicalConfig, SearchConfig
from src.geometry.regions import (disk, first_feasible_region, localization_region,
                                  region_area_diameter, sample_region_random)
from src.localization.observation import observe
from src.strategies import StrategyContext, select_all
from experiments.scenario_generator import generate_base_scenarios, sample_error


TASK_ROOT = Path(__file__).resolve().parents[1]
RAW = TASK_ROOT / "results" / "raw"
TABLES = TASK_ROOT / "results" / "tables"


def posterior_for(scenario, cfg, search, seed):
    s1 = np.array([scenario["s1_x"], scenario["s1_y"]])
    reg = first_feasible_region(s1, scenario["bearing1_rad"], cfg,
                                reception_radius=None,
                                resolution=search.polygon_resolution)
    rng = np.random.default_rng(seed)
    pts = sample_region_random(reg, 64, rng)
    # Explicit modeling prior: independent uniform reception radius, truncated
    # below by the distance required for the observed first detection.
    d1 = np.linalg.norm(pts - s1, axis=1)
    low = np.maximum(cfg.reception_min, d1)
    radii = rng.uniform(low, cfg.reception_max)
    return reg, pts, radii


def evaluate_outcome(scenario, point, error2, first_region, cfg, search):
    g = np.array([scenario["target_x"], scenario["target_y"]])
    s1 = np.array([scenario["s1_x"], scenario["s1_y"]])
    outcome = observe(point, g, scenario["radius"], error2, cfg.near_radius)
    if outcome["kind"] == "near":
        area, diameter = 0.0, 0.0  # direct optical exact localization is triggered
    elif outcome["kind"] == "no_signal":
        # Guaranteed implication despite unknown R: no signal => distance > 1000.
        reg = first_region.difference(
            disk(point, cfg.reception_min, search.polygon_resolution))
        area, diameter = region_area_diameter(reg)
    else:
        reg = localization_region(
            [s1, point], [scenario["bearing1_rad"], outcome["bearing"]], cfg,
            [cfg.reception_max, cfg.reception_max], search.polygon_resolution)
        area, diameter = region_area_diameter(reg)
    move = float(np.linalg.norm(point - s1))
    return outcome["kind"], area, diameter, move, move / cfg.speed


def run(base_scenarios=400, replicates=25, seed=20260911,
        quick=False, strategies=None):
    RAW.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    cfg = PhysicalConfig()
    search = SearchConfig(grid_step=300.0 if quick else 250.0,
                          polygon_resolution=40 if quick else 64,
                          shortlist_size=4 if quick else 6,
                          objective_target_samples=6 if quick else 10,
                          objective_error_samples=3)
    scenarios = generate_base_scenarios(base_scenarios, seed, cfg)
    pd.DataFrame(scenarios).to_csv(RAW / "base_scenarios.csv", index=False)
    eval_rows, select_rows = [], []
    master = np.random.SeedSequence(seed)
    streams = master.spawn(base_scenarios)
    wall_start = time.perf_counter()
    for k, sc in enumerate(scenarios):
        reg, posterior, radii = posterior_for(sc, cfg, search,
                                              int(streams[k].generate_state(1)[0]))
        ctx = StrategyContext(
            np.array([sc["s1_x"], sc["s1_y"]]), sc["bearing1_rad"], reg,
            posterior, radii, cfg, search, seed + k * 37)
        selected = select_all(ctx, strategies)
        for name, result in selected.items():
            select_rows.append({"scenario_id": sc["scenario_id"],
                                "strategy": name, "s2_x": result.point[0],
                                "s2_y": result.point[1],
                                "selection_objective": result.objective,
                                "selection_runtime_s": result.runtime_s,
                                "candidate_count": result.candidate_count})
        rng = np.random.default_rng(streams[k].spawn(1)[0])
        errors = [sample_error(rng, sc["error_model"],
                               math.radians(cfg.bearing_error_deg))
                  for _ in range(replicates)]
        for rep, e2 in enumerate(errors):
            for name, result in selected.items():
                kind, area, diameter, move, move_time = evaluate_outcome(
                    sc, result.point, e2, reg, cfg, search)
                eval_rows.append({
                    "scenario_id": sc["scenario_id"], "replicate": rep,
                    "strategy": name, "radius_mode": sc["radius_mode"],
                    "error_model": sc["error_model"], "outcome": kind,
                    "detected": kind != "no_signal", "area_m2": area,
                    "diameter_m": diameter, "move_distance_m": move,
                    "move_time_s": move_time,
                    "selection_runtime_s": result.runtime_s,
                    "candidate_count": result.candidate_count,
                })
        if (k + 1) % max(1, base_scenarios // 10) == 0:
            print(f"completed {k + 1}/{base_scenarios} base scenarios", flush=True)
    pd.DataFrame(select_rows).to_csv(RAW / "selected_points.csv", index=False)
    pd.DataFrame(eval_rows).to_csv(RAW / "evaluations.csv", index=False)
    manifest = {"seed": seed, "base_scenarios": base_scenarios,
                "replicates": replicates,
                "effective_scenarios": base_scenarios * replicates,
                "strategy_evaluations": len(eval_rows),
                "elapsed_s": time.perf_counter() - wall_start,
                "physical_config": cfg.__dict__, "search_config": search.__dict__}
    (RAW / "run_manifest.json").write_text(json.dumps(manifest, indent=2),
                                            encoding="utf-8")
    return pd.DataFrame(eval_rows)


if __name__ == "__main__":
    p = argparse.ArgumentParser()
    p.add_argument("--base-scenarios", type=int, default=400)
    p.add_argument("--replicates", type=int, default=25)
    p.add_argument("--seed", type=int, default=20260911)
    p.add_argument("--quick", action="store_true")
    args = p.parse_args()
    run(args.base_scenarios, args.replicates, args.seed, args.quick)

