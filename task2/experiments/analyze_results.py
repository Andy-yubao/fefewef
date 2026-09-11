"""Summaries, paired comparisons, and cluster bootstrap intervals."""
from __future__ import annotations

from pathlib import Path
import json
import math
import numpy as np
import pandas as pd

from src.config import PhysicalConfig, SearchConfig
from src.geometry.angles import intersection_angle
from src.geometry.regions import (first_feasible_region, region_area_diameter,
                                  theoretical_candidate_region,
                                  guaranteed_reception_region)
from src.localization.observation import observe
from src.localization.update import update_region_from_observation


TASK_ROOT = Path(__file__).resolve().parents[1]
RAW = TASK_ROOT / "results" / "raw"
TABLES = TASK_ROOT / "results" / "tables"
CASES = TASK_ROOT / "results" / "case_studies"


def q(p):
    return lambda x: x.quantile(p)


def summarize(df):
    rows = []
    for name, g in df.groupby("strategy", sort=True):
        row = {"strategy": name, "n": len(g)}
        for col, prefix in (("diameter_m", "diameter"), ("area_m2", "area")):
            x = g[col]
            row.update({f"{prefix}_mean": x.mean(), f"{prefix}_median": x.median(),
                        f"{prefix}_std": x.std(), f"{prefix}_p90": x.quantile(.90),
                        f"{prefix}_p75": x.quantile(.75),
                        f"{prefix}_p95": x.quantile(.95), f"{prefix}_p99": x.quantile(.99),
                        f"{prefix}_max": x.max()})
        row.update({"detection_probability": g["detected"].mean(),
                    "bearing_probability": (g["outcome"] == "bearing").mean(),
                    "no_signal_rate": (g["outcome"] == "no_signal").mean(),
                    "near_rate": (g["outcome"] == "near").mean(),
                    "move_distance_mean": g["move_distance_m"].mean(),
                    "move_distance_median": g["move_distance_m"].median(),
                    "move_distance_p95": g["move_distance_m"].quantile(.95),
                    "move_time_mean": g["move_time_s"].mean(),
                    "selection_runtime_mean": g["selection_runtime_s"].mean(),
                    "selection_runtime_median": g["selection_runtime_s"].median(),
                    "selection_runtime_p95": g["selection_runtime_s"].quantile(.95),
                    "candidate_count_mean": g["candidate_count"].mean(),
                    "exact_objective_evaluation_count_mean":
                        g["exact_objective_evaluation_count"].mean()})
        rows.append(row)
    return pd.DataFrame(rows).sort_values("diameter_mean")


def cluster_bootstrap(delta, scenario_ids, rng, n_boot=2000):
    unique = np.unique(scenario_ids)
    groups = {sid: delta[scenario_ids == sid] for sid in unique}
    means = np.empty(n_boot)
    for b in range(n_boot):
        chosen = rng.choice(unique, len(unique), replace=True)
        means[b] = np.mean(np.concatenate([groups[s] for s in chosen]))
    return np.quantile(means, [.025, .975])


def paired_comparisons(df, seed=20260911):
    wide = df.pivot(index=["scenario_id", "replicate"],
                    columns="strategy", values="diameter_m")
    rng = np.random.default_rng(seed)
    rows = []
    for a in wide.columns:
        for b in wide.columns:
            if a == b:
                continue
            z = wide[[a, b]].dropna()
            delta = (z[b] - z[a]).to_numpy()  # positive means A improves on B
            ids = z.index.get_level_values("scenario_id").to_numpy()
            lo, hi = cluster_bootstrap(delta, ids, rng)
            rows.append({"strategy_a": a, "strategy_b": b,
                         "win_rate_a": np.mean(delta > 1e-9),
                         "tie_rate": np.mean(np.abs(delta) <= 1e-9),
                         "loss_rate_a": np.mean(delta < -1e-9),
                         "mean_improvement_m": np.mean(delta),
                         "median_improvement_m": np.median(delta),
                         "mean_improvement_ci_low": lo,
                         "mean_improvement_ci_high": hi})
    return pd.DataFrame(rows)


def sensitivity(df, factor):
    return (df.groupby(["strategy", factor], as_index=False)
             .agg(n=("diameter_m", "size"), diameter_mean=("diameter_m", "mean"),
                 diameter_median=("diameter_m", "median"),
                 diameter_p95=("diameter_m", lambda x: x.quantile(.95)),
                 detection_probability=("detected", "mean"),
                  move_distance_mean=("move_distance_m", "mean")))


def robustness_and_cases(df):
    scenarios = pd.read_csv(RAW / "base_scenarios.csv")
    selected = pd.read_csv(RAW / "selected_points.csv")
    cfg, search = PhysicalConfig(), SearchConfig()
    features = []
    regions = {}
    for sc in scenarios.itertuples():
        s1 = np.array([sc.s1_x, sc.s1_y])
        reg = first_feasible_region(s1, sc.bearing1_rad, cfg,
                                    resolution=search.polygon_resolution)
        area, diam = region_area_diameter(reg)
        regions[sc.scenario_id] = reg
        features.append({"scenario_id": sc.scenario_id, "f1_area_m2": area,
                         "f1_diameter_m": diam,
                         "s1_target_distance_m": math.hypot(
                             sc.target_x-sc.s1_x, sc.target_y-sc.s1_y),
                         "bearing_orientation_deg":
                             math.degrees(sc.bearing1_rad) % 360})
    features = pd.DataFrame(features)
    ed = df[df.strategy == "expected_diameter"].merge(features, on="scenario_id")
    grouped = []
    for factor in ["f1_diameter_m", "f1_area_m2", "s1_target_distance_m",
                   "bearing_orientation_deg"]:
        labels = pd.qcut(ed[factor], 4, duplicates="drop")
        tmp = (ed.assign(group=labels.astype(str)).groupby("group", as_index=False)
               .agg(n=("diameter_m", "size"), diameter_mean=("diameter_m", "mean"),
                    diameter_p95=("diameter_m", lambda x: x.quantile(.95)),
                    no_signal_rate=("outcome", lambda x: (x == "no_signal").mean())))
        tmp.insert(0, "factor", factor)
        grouped.append(tmp)
    pd.concat(grouped, ignore_index=True).to_csv(
        TABLES / "robustness_geometry_groups.csv", index=False)

    means = df.groupby(["scenario_id", "strategy"], as_index=False).diameter_m.mean()
    wide = means.pivot(index="scenario_id", columns="strategy", values="diameter_m")
    baselines = [x for x in ["geometry", "gdop_mean", "fim_e", "random"]
                 if x in wide]
    wide["best_baseline"] = wide[baselines].min(axis=1)
    wide["ed_advantage"] = wide["best_baseline"] - wide["expected_diameter"]
    ed_sel = selected[selected.strategy == "expected_diameter"].set_index("scenario_id")
    sc_idx = scenarios.set_index("scenario_id")
    reasons = [
        ("ED-best", int(wide.ed_advantage.idxmax())),
        ("ED-worst", int(wide.ed_advantage.idxmin())),
        ("large-F1", int(features.set_index("scenario_id").f1_diameter_m.idxmax())),
        ("boundary-selected", int(max(ed_sel.index,
             key=lambda i: math.hypot(ed_sel.loc[i].s2_x, ed_sel.loc[i].s2_y)))),
    ]
    no_signal = ed[ed.outcome == "no_signal"]
    if not no_signal.empty:
        reasons.append(("large-after-no-signal", int(
            no_signal.loc[no_signal.diameter_m.idxmax()].scenario_id)))
    angles = {}
    for sid, row in ed_sel.iterrows():
        sc = sc_idx.loc[sid]
        angles[sid] = float(intersection_angle(
            np.array([sc.s1_x, sc.s1_y]), np.array([row.s2_x, row.s2_y]),
            np.array([sc.target_x, sc.target_y])))
    reasons.append(("near-parallel", min(angles, key=angles.get)))
    case_rows = []
    seen = set()
    CASES.mkdir(parents=True, exist_ok=True)
    for reason, sid in reasons:
        if sid in seen: continue
        seen.add(sid)
        sc = sc_idx.loc[sid]
        sel = ed_sel.loc[sid]
        record = ed[(ed.scenario_id == sid)].sort_values(
            "diameter_m", ascending=False).iloc[0]
        error = 0.0
        outcome = observe(np.array([sel.s2_x, sel.s2_y]),
                          np.array([sc.target_x, sc.target_y]), sc.radius, error,
                          cfg.near_radius)
        update = update_region_from_observation(
            regions[sid], np.array([sel.s2_x, sel.s2_y]), outcome, cfg,
            search.polygon_resolution)
        best_name = wide.loc[sid, baselines].idxmin()
        case_rows.append({"case_reason": reason, "scenario_id": sid,
                          "s1_x": sc.s1_x, "s1_y": sc.s1_y,
                          "bearing1_rad": sc.bearing1_rad,
                          "f1_area_m2": features.set_index("scenario_id").loc[sid].f1_area_m2,
                          "f1_diameter_m": features.set_index("scenario_id").loc[sid].f1_diameter_m,
                          "s2_x": sel.s2_x, "s2_y": sel.s2_y,
                          "target_x": sc.target_x, "target_y": sc.target_y,
                          "true_radius_m": sc.radius, "outcome": record.outcome,
                          "f2_area_m2": record.area_m2,
                          "f2_diameter_m": record.diameter_m,
                          "best_baseline": best_name,
                          "best_baseline_diameter_m": wide.loc[sid, best_name]})
        geometry = {"scenario_id": sid, "case_reason": reason,
                    "f1_wkt": regions[sid].wkt,
                    "cf_wkt": theoretical_candidate_region(regions[sid], cfg).wkt,
                    "cg_wkt": guaranteed_reception_region(regions[sid], cfg).wkt,
                    "illustrative_zero_error_f2_wkt":
                        None if update.region is None else update.region.wkt}
        (CASES / f"case_{sid:03d}.json").write_text(
            json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8")
    pd.DataFrame(case_rows).to_csv(TABLES / "representative_cases.csv", index=False)


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(RAW / "evaluations.csv")
    summary = summarize(df)
    summary.to_csv(TABLES / "strategy_summary.csv", index=False)
    pairwise = paired_comparisons(df)
    pairwise.to_csv(TABLES / "pairwise_comparison.csv", index=False)
    pairwise[pairwise["strategy_a"] == "expected_diameter"].to_csv(
        TABLES / "pairwise_expected_diameter.csv", index=False)
    pairwise[pairwise["strategy_b"] == "random"].to_csv(
        TABLES / "improvement_vs_random.csv", index=False)
    sensitivity(df, "error_model").to_csv(TABLES / "sensitivity_error.csv",
                                            index=False)
    sensitivity(df, "radius_mode").to_csv(TABLES / "sensitivity_radius.csv",
                                             index=False)
    robustness_and_cases(df)
    print(summary[["strategy", "diameter_mean", "diameter_median", "diameter_p95",
                   "detection_probability", "move_distance_mean",
                   "selection_runtime_mean"]].to_string(index=False))


if __name__ == "__main__":
    main()
