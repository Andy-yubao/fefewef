"""Q2 ablation, sensitivity, convergence, and representative-case tables."""
from __future__ import annotations

from dataclasses import replace
import math
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

from src.config import PhysicalConfig, SearchConfig
from src.geometry.regions import region_area_diameter
from src.strategies import StrategyContext
from src.strategies.selectors import select_expected_diameter
from experiments.run_benchmark import evaluate_outcome, posterior_for
from experiments.scenario_generator import generate_base_scenarios, sample_error

ROOT = Path(__file__).resolve().parents[1]
TABLES = ROOT / "results" / "tables"
RAW = ROOT / "results" / "raw"
SEED = 20260911


def _scenario_records(search, scenarios, label, replicates=5):
    cfg = PhysicalConfig()
    rows = []
    streams = np.random.SeedSequence(SEED + 41).spawn(len(scenarios))
    for k, sc in enumerate(scenarios):
        pseed = int(streams[k].generate_state(1)[0])
        region, points, radii = posterior_for(sc, cfg, search, pseed)
        ctx = StrategyContext(
            np.array([sc["s1_x"], sc["s1_y"]]), sc["bearing1_rad"],
            region, points, radii, cfg, search, SEED + k * 37)
        selected = select_expected_diameter(ctx)
        erng = np.random.default_rng(SEED + 9000 + k)
        errors = [sample_error(erng, sc["error_model"],
                               math.radians(cfg.bearing_error_deg))
                  for _ in range(replicates)]
        realized = [evaluate_outcome(sc, selected.point, e, region, cfg, search)[2]
                    for e in errors]
        area, f1_diameter = region_area_diameter(region)
        rows.append({"study": label, "scenario_id": sc["scenario_id"],
                     "selected_x": selected.point[0],
                     "selected_y": selected.point[1],
                     "objective_m": selected.objective,
                     "realized_mean_diameter_m": np.mean(realized),
                     "realized_p95_diameter_m": np.quantile(realized, .95),
                     "selection_runtime_s": selected.runtime_s,
                     "candidate_count": selected.candidate_count,
                     "exact_evaluation_count": selected.diagnostics[
                         "exact_objective_evaluation_count"],
                     "f1_area_m2": area, "f1_diameter_m": f1_diameter})
    return pd.DataFrame(rows)


def _with_reference_metrics(raw, reference_label):
    ref = raw[raw.study == reference_label].set_index("scenario_id")
    out = raw.copy()
    out["selected_point_shift_m"] = [
        np.hypot(r.selected_x - ref.loc[r.scenario_id, "selected_x"],
                 r.selected_y - ref.loc[r.scenario_id, "selected_y"])
        for r in out.itertuples()]
    out["objective_delta_m"] = [
        r.objective_m - ref.loc[r.scenario_id, "objective_m"]
        for r in out.itertuples()]
    return out


def _summary(raw, factor="study", reference_label=None):
    rows = []
    ref = None if reference_label is None else raw[raw.study == reference_label]
    for label, g in raw.groupby(factor, sort=False):
        row = {factor: label, "n_scenarios": len(g),
               "expected_diameter_mean_m": g.objective_m.mean(),
               "realized_diameter_mean_m": g.realized_mean_diameter_m.mean(),
               "realized_diameter_p95_m": g.realized_p95_diameter_m.quantile(.95),
               "selected_point_shift_mean_m": g.selected_point_shift_m.mean(),
               "selection_runtime_mean_s": g.selection_runtime_s.mean(),
               "candidate_count_mean": g.candidate_count.mean(),
               "exact_evaluation_count_mean": g.exact_evaluation_count.mean(),
               "selection_stability_within_100m":
                   (g.selected_point_shift_m <= 100).mean()}
        if ref is not None and len(g) == len(ref):
            row["scenario_objective_rank_spearman"] = spearmanr(
                g.sort_values("scenario_id").objective_m,
                ref.sort_values("scenario_id").objective_m).statistic
        rows.append(row)
    return pd.DataFrame(rows)


def main(n_study_scenarios=24, n_convergence_scenarios=12):
    TABLES.mkdir(parents=True, exist_ok=True)
    scenarios = generate_base_scenarios(n_study_scenarios, SEED)
    default = SearchConfig()

    ablations = {
        "ED-full": default,
        "ED-no-coarse-to-fine-100m": replace(
            default, grid_step=100.0, coarse_to_fine=False),
        "ED-current-coarse-250m": replace(default, coarse_to_fine=False),
        "ED-old-hidden-R-update": replace(default, observable_update=False),
        "ED-corrected-observable-update": default,
        "ED-current-pruning": replace(
            default, pruning_mode="current", min_detection_probability=.25,
            min_median_abs_sin_angle=.12),
        "ED-without-pdet-threshold": default,
        "ED-low-sampling-10x3": replace(
            default, objective_target_samples=10, objective_error_samples=3),
        "ED-medium-sampling-20x5": replace(
            default, objective_target_samples=20, objective_error_samples=5),
        "ED-high-sampling-40x9": replace(
            default, objective_target_samples=40, objective_error_samples=9),
    }
    raw = pd.concat([_scenario_records(c, scenarios, label)
                     for label, c in ablations.items()], ignore_index=True)
    raw = _with_reference_metrics(raw, "ED-full")
    raw.to_csv(RAW / "ablation_expected_diameter_raw.csv", index=False)
    _summary(raw, reference_label="ED-full").to_csv(
        TABLES / "ablation_expected_diameter.csv", index=False)

    radius_cfgs = {x: replace(default, radius_prior=x) for x in
                   ["conditional_uniform", "fixed_1000", "fixed_1250",
                    "fixed_1500"]}
    radius_raw = pd.concat([_scenario_records(c, scenarios, label)
                            for label, c in radius_cfgs.items()], ignore_index=True)
    radius_raw = _with_reference_metrics(radius_raw, "conditional_uniform")
    _summary(radius_raw, reference_label="conditional_uniform").rename(
        columns={"study": "radius_prior"}).to_csv(
            TABLES / "sensitivity_radius_prior.csv", index=False)

    error_cfgs = {x: replace(default, objective_error_model=x) for x in
                  ["uniform", "truncated_gaussian", "endpoint"]}
    error_raw = pd.concat([_scenario_records(c, scenarios, label)
                           for label, c in error_cfgs.items()], ignore_index=True)
    error_raw = _with_reference_metrics(error_raw, "uniform")
    _summary(error_raw, reference_label="uniform").rename(
        columns={"study": "error_model"}).to_csv(
            TABLES / "sensitivity_error_model.csv", index=False)

    domain_cfgs = {
        "inside-target-disk": default,
        "theoretical-detectable-Cf": replace(default, candidate_domain="detectable"),
    }
    domain_raw = pd.concat([_scenario_records(c, scenarios, label)
                            for label, c in domain_cfgs.items()], ignore_index=True)
    domain_raw = _with_reference_metrics(domain_raw, "inside-target-disk")
    _summary(domain_raw, reference_label="inside-target-disk").to_csv(
        TABLES / "candidate_domain_sensitivity.csv", index=False)

    conv_scenarios = scenarios[:n_convergence_scenarios]
    conv_parts = []
    for nt in (10, 20, 40, 80):
        for ne in (3, 5, 9, 17):
            label = f"{nt}x{ne}"
            c = replace(default, objective_target_samples=nt,
                        objective_error_samples=ne)
            part = _scenario_records(c, conv_scenarios, label, 3)
            part["target_samples"] = nt
            part["error_samples"] = ne
            conv_parts.append(part)
    conv = pd.concat(conv_parts, ignore_index=True)
    conv = _with_reference_metrics(conv, "80x17")
    _summary(conv, reference_label="80x17").merge(
        conv[["study", "target_samples", "error_samples"]].drop_duplicates(),
        on="study").to_csv(TABLES / "sampling_convergence.csv", index=False)

    grids = {
        "coarse-250": replace(default, coarse_to_fine=False),
        "coarse-150": replace(default, grid_step=150.0, coarse_to_fine=False),
        "coarse-100": replace(default, grid_step=100.0, coarse_to_fine=False),
        "coarse-to-fine-250-100-50": default,
    }
    grid_raw = pd.concat([_scenario_records(c, conv_scenarios, label, 3)
                          for label, c in grids.items()], ignore_index=True)
    grid_raw = _with_reference_metrics(grid_raw, "coarse-to-fine-250-100-50")
    _summary(grid_raw, reference_label="coarse-to-fine-250-100-50").to_csv(
        TABLES / "grid_convergence.csv", index=False)
    print("study tables written to", TABLES)


if __name__ == "__main__":
    main()
