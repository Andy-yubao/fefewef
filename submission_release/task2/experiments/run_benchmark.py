"""Fair benchmark: shared scenarios, candidates, evaluator, and seed stream."""
from __future__ import annotations

import argparse
from datetime import datetime, timezone
import importlib.metadata
import json
import math
import platform
from pathlib import Path
import subprocess
import time

import numpy as np
import pandas as pd
from shapely.geometry import Point

from src.config import PhysicalConfig, SearchConfig
from src.geometry.regions import (first_feasible_region, sample_region_grid,
                                  sample_region_random)
from src.localization.observation import observe
from src.localization.update import update_region_from_observation
from src.strategies import StrategyContext, select_all
from experiments.scenario_generator import generate_base_scenarios, sample_error


TASK_ROOT = Path(__file__).resolve().parents[1]
RAW = TASK_ROOT / "results" / "raw"
TABLES = TASK_ROOT / "results" / "tables"
CORE_STRATEGIES = ["gdop_mean", "geometry", "fim_e", "random"]


def posterior_for(scenario, cfg, search, seed):
    s1 = np.array([scenario["s1_x"], scenario["s1_y"]])
    reg = first_feasible_region(s1, scenario["bearing1_rad"], cfg,
                                reception_radius=None,
                                resolution=search.polygon_resolution)
    rng = np.random.default_rng(seed)
    if search.posterior_sampling == "grid":
        pts = sample_region_grid(reg, search.posterior_grid_step,
                                 search.posterior_samples, rng)
    elif search.posterior_sampling == "random":
        pts = sample_region_random(reg, search.posterior_samples, rng)
    else:
        raise ValueError(search.posterior_sampling)
    d1 = np.linalg.norm(pts - s1, axis=1)
    low = np.maximum(cfg.reception_min, d1)
    if search.radius_prior == "conditional_uniform":
        radii = rng.uniform(low, cfg.reception_max)
    elif search.radius_prior.startswith("fixed_"):
        fixed = float(search.radius_prior.split("_", 1)[1])
        # Conditioning on the observed first bearing rules out R < |G-S1|.
        radii = np.maximum(fixed, d1)
    else:
        raise ValueError(search.radius_prior)
    return reg, pts, radii


def evaluate_outcome(scenario, point, error2, first_region, cfg, search):
    g = np.array([scenario["target_x"], scenario["target_y"]])
    s1 = np.array([scenario["s1_x"], scenario["s1_y"]])
    outcome = observe(point, g, scenario["radius"], error2, cfg.near_radius)
    update = update_region_from_observation(
        first_region, point, outcome, cfg, search.polygon_resolution)
    area, diameter = update.area, update.diameter
    move = float(np.linalg.norm(point - s1))
    return outcome["kind"], area, diameter, move, move / cfg.speed


def run(base_scenarios=400, replicates=25, seed=20260911,
        quick=False, strategies=None, search=None):
    RAW.mkdir(parents=True, exist_ok=True)
    TABLES.mkdir(parents=True, exist_ok=True)
    cfg = PhysicalConfig()
    if search is None:
        search = SearchConfig(
            grid_step=300.0 if quick else 250.0,
            refine_steps=(100.0,) if quick else (100.0, 50.0),
            polygon_resolution=40 if quick else 64,
            posterior_samples=32 if quick else 80,
            shortlist_size=4 if quick else 10,
            objective_target_samples=8 if quick else 80,
            objective_error_samples=3 if quick else 5)
    strategies = CORE_STRATEGIES if strategies is None else strategies
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
                                "candidate_count": result.candidate_count,
                                "exact_objective_evaluation_count":
                                    result.diagnostics.get(
                                        "exact_objective_evaluation_count", 0),
                                "search_levels": json.dumps(
                                    result.diagnostics.get("search_levels", []))})
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
                    "exact_objective_evaluation_count":
                        result.diagnostics.get(
                            "exact_objective_evaluation_count", 0),
                })
        if (k + 1) % max(1, base_scenarios // 10) == 0:
            print(f"completed {k + 1}/{base_scenarios} base scenarios", flush=True)
    pd.DataFrame(select_rows).to_csv(RAW / "selected_points.csv", index=False)
    pd.DataFrame(eval_rows).to_csv(RAW / "evaluations.csv", index=False)
    packages = ["numpy", "scipy", "shapely", "pandas", "matplotlib",
                "seaborn", "pytest"]
    try:
        commit = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=TASK_ROOT,
            text=True).strip()
    except Exception:
        commit = "unavailable"
    manifest = {"git_commit": commit,
                "generated_at_utc": datetime.now(timezone.utc).isoformat(),
                "python_version": platform.python_version(),
                "dependencies": {p: importlib.metadata.version(p) for p in packages},
                "seed": seed, "base_scenarios": base_scenarios,
                "replicates": replicates,
                "effective_scenarios": base_scenarios * replicates,
                "strategy_evaluations": len(eval_rows),
                "strategies": strategies,
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
    p.add_argument("--all-strategies", action="store_true")
    args = p.parse_args()
    run(args.base_scenarios, args.replicates, args.seed, args.quick,
        None if not args.all_strategies else [
            "random", "geometry", "gdop_mean", "gdop_worst", "fim_a",
            "fim_d", "fim_e", "eig"])
