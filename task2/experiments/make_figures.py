"""Generate publication-ready figures from raw experiment results."""
from __future__ import annotations

import math
from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import seaborn as sns
from shapely import wkt

from src.config import PhysicalConfig, SearchConfig
from src.geometry.regions import (candidate_regions, first_feasible_region,
                                  guaranteed_reception_region,
                                  sample_region_random,
                                  theoretical_candidate_region)
from src.strategies import StrategyContext, select_all


TASK_ROOT = Path(__file__).resolve().parents[1]
RAW = TASK_ROOT / "results" / "raw"
TABLES = TASK_ROOT / "results" / "tables"
FIGURES = TASK_ROOT / "results" / "figures"
PALETTE = "tab10"


def save(fig, name):
    fig.savefig(FIGURES / name, dpi=240, bbox_inches="tight")
    fig.savefig(FIGURES / f"{Path(name).stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def xy_fill(ax, geom, **kwargs):
    geoms = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for g in geoms:
        if g.is_empty: continue
        x, y = g.exterior.xy
        ax.fill(x, y, **kwargs)


def reconstruct_first(sc, seed=20260911):
    cfg, search = PhysicalConfig(), SearchConfig()
    s1 = np.array([sc.s1_x, sc.s1_y])
    reg = first_feasible_region(s1, sc.bearing1_rad, cfg,
                                resolution=search.polygon_resolution)
    rng = np.random.default_rng(seed + int(sc.scenario_id))
    pts = sample_region_random(reg, search.posterior_samples, rng)
    low = np.maximum(cfg.reception_min, np.linalg.norm(pts - s1, axis=1))
    radii = rng.uniform(low, cfg.reception_max)
    return cfg, search, s1, reg, pts, radii


def region_figures(scenarios, selections):
    sc = scenarios.iloc[0]
    cfg, search, s1, reg, pts, radii = reconstruct_first(sc)
    cand = candidate_regions(s1, pts, cfg, search.grid_step, radii,
                             domain=search.candidate_domain,
                             pruning_mode=search.pruning_mode)
    cf = theoretical_candidate_region(reg, cfg, search.polygon_resolution)
    cg = guaranteed_reception_region(reg, cfg, search.polygon_resolution)
    chosen = selections[(selections.scenario_id == sc.scenario_id) &
                        (selections.strategy == "expected_diameter")].iloc[0]
    fig, ax = plt.subplots(figsize=(8, 7), constrained_layout=True)
    theta = np.linspace(0, 2 * np.pi, 400)
    ax.plot(cfg.target_radius*np.cos(theta), cfg.target_radius*np.sin(theta),
            color="black", lw=1.2, label=r"target domain $\Omega$")
    xy_fill(ax, cf, color="#8ecae6", alpha=.16, label=r"theoretical $C_f$")
    if not cg.is_empty:
        xy_fill(ax, cg, color="#90be6d", alpha=.35,
                label=r"guaranteed reception $C_g$")
    xy_fill(ax, reg, color="#f4a261", alpha=.55, label=r"first region $F_1$")
    p = cand["points"]
    ax.scatter(p[cand["recommended"], 0], p[cand["recommended"], 1], s=9,
               color="#277da1", alpha=.65, label="practical candidates")
    ax.scatter(chosen.s2_x, chosen.s2_y, marker="*", s=180, color="#d62828",
               edgecolor="white", label=r"ED $S_2^*$", zorder=6)
    ax.scatter(sc.target_x, sc.target_y, marker="X", s=80, color="#6a4c93",
               label="simulated truth")
    ax.scatter(*s1, marker="^", s=75, color="black", label=r"$S_1$")
    ax.set(aspect="equal", xlabel="x (m)", ylabel="y (m)",
           title="Q2 geometry and candidate regions")
    ax.legend(fontsize=8, ncol=2)
    save(fig, "q2_geometry_candidate_regions.png")


def objective_and_selection_figures(sc):
    cfg, search, s1, reg, pts, radii = reconstruct_first(sc, 617)
    ctx = StrategyContext(s1, sc.bearing1_rad, reg, pts, radii, cfg, search,
                          617 + int(sc.scenario_id))
    names = ["expected_diameter", "geometry", "gdop_mean", "fim_e", "random"]
    results = select_all(ctx, names)
    res = results["expected_diameter"]
    p = np.asarray(res.diagnostics["grid_points"])
    z = np.asarray(res.diagnostics["objective_surface"], float)
    finite = np.isfinite(z)
    fig, ax = plt.subplots(figsize=(7.5, 6.5), constrained_layout=True)
    m = ax.scatter(p[finite, 0], p[finite, 1], c=z[finite], s=42,
                   cmap="viridis_r", edgecolor="none")
    xy_fill(ax, reg, color="#f4a261", alpha=.18)
    ax.scatter(*res.point, marker="*", s=170, c="#d62828", edgecolor="white",
               label=r"$S_2^*$")
    ax.scatter(*s1, marker="^", s=65, c="black", label=r"$S_1$")
    ax.set(title="Expected posterior-diameter search surface",
           aspect="equal", xlabel="x (m)", ylabel="y (m)")
    fig.colorbar(m, ax=ax, label="Expected diameter (m)")
    ax.legend()
    save(fig, "expected_diameter_objective_surface.png")
    fig, ax = plt.subplots(figsize=(7, 6))
    xy_fill(ax, reg, color="#f4a261", alpha=.35)
    ax.scatter(pts[:,0], pts[:,1], s=8, color="#555555", alpha=.5,
               label="posterior particles")
    for j, (name, res) in enumerate(results.items()):
        ax.scatter(*res.point, s=65, marker=(j % 5) + 3, label=name)
    ax.scatter(*s1, marker="^", s=90, c="black", label="S1")
    ax.set(aspect="equal", xlabel="x (m)", ylabel="y (m)",
           title="Selected second detection points")
    ax.legend(fontsize=7, ncol=2)
    save(fig, "selected_points_comparison.png")


def result_figures(df, summary):
    order = summary.sort_values("diameter_mean")["strategy"].tolist()
    sample = df.groupby("strategy", group_keys=False).sample(
        n=min(2500, df.groupby("strategy").size().min()), random_state=13)
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.boxenplot(data=sample, x="strategy", y="diameter_m", order=order,
                  hue="strategy", palette=PALETTE, legend=False, ax=ax)
    ax.tick_params(axis="x", rotation=35)
    ax.set(xlabel="", ylabel="Localization diameter (m)")
    save(fig, "diameter_distribution.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    for name, g in df.groupby("strategy"):
        x = np.sort(g.diameter_m.to_numpy())
        ax.plot(x, np.arange(1, len(x)+1)/len(x), label=name)
    ax.set(xlabel="Localization diameter (m)", ylabel="Empirical CDF", xlim=(0, None))
    ax.grid(alpha=.25); ax.legend(fontsize=7, ncol=2)
    save(fig, "diameter_cdf.png")

    long = summary.melt(id_vars="strategy",
                        value_vars=["diameter_mean","diameter_p95","diameter_max"],
                        var_name="metric", value_name="diameter_m")
    fig, ax = plt.subplots(figsize=(11, 5))
    sns.barplot(data=long, x="strategy", y="diameter_m", hue="metric",
                order=order, ax=ax)
    ax.tick_params(axis="x", rotation=35); ax.set(xlabel="", ylabel="Diameter (m)")
    save(fig, "q2_strategy_tail_comparison.png")

    fig, ax = plt.subplots(figsize=(7, 5))
    ax.scatter(summary.move_distance_mean, summary.diameter_mean, s=65)
    for r in summary.itertuples():
        ax.annotate(r.strategy, (r.move_distance_mean, r.diameter_mean), fontsize=7,
                    xytext=(3,3), textcoords="offset points")
    ax.set(xlabel="Mean movement distance (m)", ylabel="Mean diameter (m)",
           title="Movement–localization Pareto plane")
    ax.grid(alpha=.25); save(fig, "pareto_movement_localization.png")

    fig, ax = plt.subplots(figsize=(10, 4.5))
    sns.barplot(data=summary, x="strategy", y="detection_probability",
                order=order, hue="strategy", palette=PALETTE, legend=False, ax=ax)
    ax.tick_params(axis="x", rotation=35); ax.set(xlabel="", ylabel="Detection probability", ylim=(0,1.05))
    save(fig, "detection_success.png")


def sensitivity_figures():
    for factor, filename, label in [
        ("error_model", "sensitivity_error.csv", "Bearing-error model"),
        ("radius_mode", "sensitivity_radius.csv", "Reception-radius mode")]:
        d = pd.read_csv(TABLES / filename)
        fig, ax = plt.subplots(figsize=(10, 5))
        sns.lineplot(data=d, x=factor, y="diameter_mean", hue="strategy",
                     marker="o", ax=ax)
        ax.set(xlabel=label, ylabel="Mean localization diameter (m)")
        ax.tick_params(axis="x", rotation=20); ax.legend(fontsize=7, ncol=2)
        ax.grid(alpha=.25)
        save(fig, "error_sensitivity.png" if factor == "error_model" else
             "radius_sensitivity.png")


def ablation_and_convergence_figures():
    path = TABLES / "ablation_expected_diameter.csv"
    if path.exists():
        d = pd.read_csv(path)
        keep = d[d.study.isin(["ED-old-hidden-R-update",
                               "ED-corrected-observable-update"])]
        fig, axes = plt.subplots(1, 3, figsize=(11, 3.8), constrained_layout=True)
        metrics = [("realized_diameter_mean_m", "Mean diameter (m)"),
                   ("realized_diameter_p95_m", "P95 diameter (m)"),
                   ("selected_point_shift_mean_m", "Point shift vs full (m)")]
        for ax, (col, label) in zip(axes, metrics):
            sns.barplot(data=keep, x="study", y=col, hue="study",
                        palette=["#b56576", "#2a9d8f"], legend=False, ax=ax)
            ax.set(xlabel="", ylabel=label)
            ax.tick_params(axis="x", rotation=18, labelsize=7)
        save(fig, "hidden_radius_fix_comparison.png")
    path = TABLES / "sampling_convergence.csv"
    if path.exists():
        d = pd.read_csv(path)
        fig, axes = plt.subplots(1, 2, figsize=(10, 4), constrained_layout=True)
        for ne, g in d.groupby("error_samples"):
            axes[0].plot(g.target_samples, g.expected_diameter_mean_m,
                         marker="o", label=f"{int(ne)} errors")
            axes[1].plot(g.target_samples, g.selection_runtime_mean_s,
                         marker="o", label=f"{int(ne)} errors")
        axes[0].set(xlabel="Target samples", ylabel="Expected diameter (m)")
        axes[1].set(xlabel="Target samples", ylabel="Selection runtime (s)")
        for ax in axes: ax.grid(alpha=.25)
        axes[0].legend(fontsize=7)
        save(fig, "sampling_convergence.png")


def representative_case_figures():
    table = TABLES / "representative_cases.csv"
    case_dir = TASK_ROOT / "results" / "case_studies"
    if not table.exists():
        return
    cases = pd.read_csv(table).head(6)
    n = len(cases)
    fig, axes = plt.subplots(2, 3, figsize=(13, 8.5), constrained_layout=True)
    for ax in axes.flat:
        ax.set_visible(False)
    for ax, case in zip(axes.flat, cases.itertuples()):
        ax.set_visible(True)
        import json
        geometry = json.loads((case_dir / f"case_{int(case.scenario_id):03d}.json")
                              .read_text(encoding="utf-8"))
        f1, cf, cg = (wkt.loads(geometry[k]) for k in
                      ["f1_wkt", "cf_wkt", "cg_wkt"])
        xy_fill(ax, cf, color="#8ecae6", alpha=.12)
        if not cg.is_empty: xy_fill(ax, cg, color="#90be6d", alpha=.28)
        xy_fill(ax, f1, color="#f4a261", alpha=.42)
        if geometry["illustrative_zero_error_f2_wkt"]:
            xy_fill(ax, wkt.loads(geometry["illustrative_zero_error_f2_wkt"]),
                    color="#e63946", alpha=.50)
        ax.scatter(case.s1_x, case.s1_y, marker="^", c="black", s=42)
        ax.scatter(case.s2_x, case.s2_y, marker="*", c="#d62828", s=90)
        ax.scatter(case.target_x, case.target_y, marker="X", c="#6a4c93", s=48)
        ax.set(title=f"{case.case_reason} (#{int(case.scenario_id)})",
               aspect="equal", xticks=[], yticks=[])
    save(fig, "representative_case_studies.png")


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="paper")
    df = pd.read_csv(RAW / "evaluations.csv")
    scenarios = pd.read_csv(RAW / "base_scenarios.csv")
    selections = pd.read_csv(RAW / "selected_points.csv")
    summary = pd.read_csv(TABLES / "strategy_summary.csv")
    region_figures(scenarios, selections)
    objective_and_selection_figures(scenarios.iloc[0])
    result_figures(df, summary)
    sensitivity_figures()
    ablation_and_convergence_figures()
    representative_case_figures()


if __name__ == "__main__":
    main()
