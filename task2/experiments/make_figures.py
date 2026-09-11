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

from src.config import PhysicalConfig, SearchConfig
from src.geometry.regions import (candidate_regions, first_feasible_region,
                                  sample_region_random)
from src.strategies import StrategyContext, select_all


TASK_ROOT = Path(__file__).resolve().parents[1]
RAW = TASK_ROOT / "results" / "raw"
TABLES = TASK_ROOT / "results" / "tables"
FIGURES = TASK_ROOT / "results" / "figures"
PALETTE = "tab10"


def save(fig, name):
    fig.savefig(FIGURES / name, dpi=240, bbox_inches="tight")
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
    pts = sample_region_random(reg, 64, rng)
    low = np.maximum(cfg.reception_min, np.linalg.norm(pts - s1, axis=1))
    radii = rng.uniform(low, cfg.reception_max)
    return cfg, search, s1, reg, pts, radii


def region_figures(scenarios):
    ids = [0, len(scenarios) // 3, 2 * len(scenarios) // 3]
    fig, axes = plt.subplots(1, 3, figsize=(14, 4.5), constrained_layout=True)
    for ax, i in zip(axes, ids):
        sc = scenarios.iloc[i]
        cfg, search, s1, reg, pts, radii = reconstruct_first(sc)
        cand = candidate_regions(s1, pts, cfg, search.grid_step, radii)
        theta = np.linspace(0, 2 * np.pi, 400)
        ax.plot(cfg.target_radius*np.cos(theta), cfg.target_radius*np.sin(theta),
                color="black", lw=1, label="target boundary")
        xy_fill(ax, reg, color="#f4a261", alpha=.45, label="target possible region")
        p = cand["points"]
        ax.scatter(p[cand["feasible"], 0], p[cand["feasible"], 1], s=7,
                   color="#8ecae6", label="S2 feasible")
        ax.scatter(p[cand["recommended"], 0], p[cand["recommended"], 1], s=10,
                   color="#2a9d8f", label="S2 recommended")
        ax.scatter(*s1, marker="^", s=55, color="red", label="S1")
        ax.set(title=f"Scenario {int(sc.scenario_id)}", aspect="equal",
               xlabel="x (m)", ylabel="y (m)")
    handles, labels = axes[0].get_legend_handles_labels()
    fig.legend(handles, labels, loc="outside lower center", ncol=5)
    save(fig, "regions_typical_scenarios.png")


def objective_and_selection_figures(sc):
    cfg, search, s1, reg, pts, radii = reconstruct_first(sc, 617)
    ctx = StrategyContext(s1, sc.bearing1_rad, reg, pts, radii, cfg, search,
                          617 + int(sc.scenario_id))
    results = select_all(ctx)
    names = ["geometry", "gdop_mean", "fim_a", "fim_d", "fim_e",
             "expected_diameter", "minimax_diameter", "eig"]
    fig, axes = plt.subplots(2, 4, figsize=(15, 7.5), constrained_layout=True)
    for ax, name in zip(axes.flat, names):
        res = results[name]
        p = np.asarray(res.diagnostics["grid_points"])
        z = np.asarray(res.diagnostics["objective_surface"], float)
        finite = np.isfinite(z)
        if finite.any():
            lo, hi = np.quantile(z[finite], [.02, .98])
            z = np.clip(z, lo, hi)
        m = ax.scatter(p[finite,0], p[finite,1], c=z[finite], s=20, cmap="viridis")
        ax.scatter(*res.point, marker="*", s=130, c="red", edgecolor="white")
        ax.scatter(*s1, marker="^", s=45, c="black")
        ax.set(title=name, aspect="equal", xticks=[], yticks=[])
        fig.colorbar(m, ax=ax, shrink=.7)
    save(fig, "objective_heatmaps.png")
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
                        value_vars=["diameter_mean","diameter_median","diameter_p95"],
                        var_name="metric", value_name="diameter_m")
    fig, ax = plt.subplots(figsize=(11, 5))
    sns.barplot(data=long, x="strategy", y="diameter_m", hue="metric",
                order=order, ax=ax)
    ax.tick_params(axis="x", rotation=35); ax.set(xlabel="", ylabel="Diameter (m)")
    save(fig, "diameter_summary.png")

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


def main():
    FIGURES.mkdir(parents=True, exist_ok=True)
    sns.set_theme(style="whitegrid", context="paper")
    df = pd.read_csv(RAW / "evaluations.csv")
    scenarios = pd.read_csv(RAW / "base_scenarios.csv")
    summary = pd.read_csv(TABLES / "strategy_summary.csv")
    region_figures(scenarios)
    objective_and_selection_figures(scenarios.iloc[0])
    result_figures(df, summary)
    sensitivity_figures()


if __name__ == "__main__":
    main()

