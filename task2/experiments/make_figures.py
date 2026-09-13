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

plt.rcParams.update({
    "font.family": "sans-serif",
    "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans SC", "DejaVu Sans"],
    "axes.unicode_minus": False,
    "pdf.fonttype": 42,
})

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
DISPLAY_STRATEGIES = ["gdop_mean", "geometry", "fim_e", "random"]
DISPLAY_LABELS = {
    "gdop_mean": "GDOP均值",
    "geometry": "几何法",
    "fim_e": "FIM E最优",
    "random": "随机法",
}
PAPER_ASSETS = TASK_ROOT.parent / "paper_assets"


def save(fig, name):
    stem = Path(name).stem
    fig.savefig(FIGURES / f"{stem}.png", dpi=240, bbox_inches="tight")
    fig.savefig(FIGURES / f"{stem}.pdf", bbox_inches="tight")
    plt.close(fig)


def save_paper_figure(fig, stem, original_dir):
    """Save the normal task2 output and a named paper-use copy plus source copy."""
    original_dir = PAPER_ASSETS / "originals" / "section6" / original_dir
    paper_dir = PAPER_ASSETS / "paper_figures" / "section6"
    original_dir.mkdir(parents=True, exist_ok=True)
    paper_dir.mkdir(parents=True, exist_ok=True)
    for directory, filename in [
        (FIGURES, stem),
        (original_dir, f"source_{stem}"),
        (paper_dir, stem.replace("q2_geometry_candidate_regions", "section6_fig1_candidate_regions")
                 .replace("selected_points_comparison", "section6_fig2_selected_points")
                 .replace("diameter_cdf", "section6_fig3_diameter_cdf")),
    ]:
        fig.savefig(directory / f"{filename}.png", dpi=240)
        fig.savefig(directory / f"{filename}.pdf")
    plt.close(fig)


def xy_fill(ax, geom, *, swap_xy=False, **kwargs):
    geoms = [geom] if geom.geom_type == "Polygon" else list(geom.geoms)
    for g in geoms:
        if g.is_empty: continue
        x, y = g.exterior.xy
        if swap_xy:
            x, y = y, x
        ax.fill(x, y, **kwargs)


def displayed_point(point):
    """Use (y, x) for paper figures that need a quarter-turn display."""
    return point[1], point[0]


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
                        (selections.strategy == "gdop_mean")].iloc[0]
    fig, ax = plt.subplots(figsize=(10.8, 5.8), constrained_layout=True)
    theta = np.linspace(0, 2 * np.pi, 400)
    ax.plot(cfg.target_radius*np.sin(theta), cfg.target_radius*np.cos(theta),
            color="black", lw=1.2, label=r"目标域 $\Omega$")
    xy_fill(ax, cf, swap_xy=True, color="#8ecae6", alpha=.16, label=r"理论候选域 $C_f$")
    if not cg.is_empty:
        xy_fill(ax, cg, swap_xy=True, color="#90be6d", alpha=.35,
                label=r"保证接收域 $C_g$")
    xy_fill(ax, reg, swap_xy=True, color="#f4a261", alpha=.55, label=r"第一可行域 $F_1$")
    p = cand["points"]
    ax.scatter(p[cand["recommended"], 1], p[cand["recommended"], 0], s=9,
               color="#277da1", alpha=.65, label="实际候选点")
    ax.scatter(chosen.s2_y, chosen.s2_x, marker="*", s=220, color="#d62828",
               edgecolor="white", label=r"GDOP均值点 $S_2^*$", zorder=6)
    ax.scatter(sc.target_y, sc.target_x, marker="X", s=80, color="#6a4c93",
               label="模拟真实位置")
    ax.scatter(*displayed_point(s1), marker="^", s=75, color="black", label=r"$S_1$")
    ax.set(aspect="equal", xlabel="x (m)", ylabel="y (m)",
           title="GDOP均值选点与候选区域")
    ax.legend(fontsize=8, ncol=2, loc="upper right")
    save_paper_figure(fig, "q2_geometry_candidate_regions", "fig1_candidate_regions")


def objective_and_selection_figures(sc):
    cfg, search, s1, reg, pts, radii = reconstruct_first(sc, 617)
    ctx = StrategyContext(s1, sc.bearing1_rad, reg, pts, radii, cfg, search,
                          617 + int(sc.scenario_id))
    names = DISPLAY_STRATEGIES
    results = select_all(ctx, names)
    res = results["gdop_mean"]
    p = np.asarray(res.diagnostics["grid_points"])
    z = np.asarray(res.diagnostics["objective_surface"], float)
    finite = np.isfinite(z)
    fig, ax = plt.subplots(figsize=(9.2, 5.0), constrained_layout=True)
    m = ax.scatter(p[finite, 0], p[finite, 1], c=z[finite], s=42,
                   cmap="viridis_r", edgecolor="none")
    xy_fill(ax, reg, color="#f4a261", alpha=.18)
    ax.scatter(*res.point, marker="*", s=170, c="#d62828", edgecolor="white",
               label=r"$S_2^*$")
    ax.scatter(*s1, marker="^", s=65, c="black", label=r"$S_1$")
    ax.set(title="GDOP均值选点目标面",
           aspect="equal", xlabel="x (m)", ylabel="y (m)")
    fig.colorbar(m, ax=ax, label="期望直径 (m)")
    ax.legend()
    save(fig, "expected_diameter_objective_surface.png")
    fig, ax = plt.subplots(figsize=(10.2, 5.8))
    xy_fill(ax, reg, swap_xy=True, color="#f4a261", alpha=.35)
    ax.scatter(pts[:,1], pts[:,0], s=8, color="#555555", alpha=.5,
               label="后验粒子")
    for j, name in enumerate(DISPLAY_STRATEGIES):
        res = results[name]
        ax.scatter(*displayed_point(res.point), s=125 if name == "gdop_mean" else 72,
                    marker="*" if name == "gdop_mean" else (j % 5) + 3,
                    linewidth=0.8, edgecolor="white" if name == "gdop_mean" else "none",
                    label=DISPLAY_LABELS[name], zorder=6 if name == "gdop_mean" else 5)
    ax.scatter(*displayed_point(s1), marker="^", s=90, c="black", label=r"$S_1$")
    ax.set(aspect="equal", xlabel="x (m)", ylabel="y (m)",
           title="四种策略选取的第二检测点")
    ax.legend(fontsize=8, ncol=2, loc="upper right")
    save_paper_figure(fig, "selected_points_comparison", "fig2_selected_points")


def result_figures(df, summary):
    df = df[df.strategy.isin(DISPLAY_STRATEGIES)].copy()
    summary = summary[summary.strategy.isin(DISPLAY_STRATEGIES)].copy()
    order = DISPLAY_STRATEGIES
    sample = df.groupby("strategy", group_keys=False).sample(
        n=min(2500, df.groupby("strategy").size().min()), random_state=13)
    fig, ax = plt.subplots(figsize=(12, 5))
    sns.boxenplot(data=sample, x="strategy", y="diameter_m", order=order,
                  hue="strategy", palette=PALETTE, legend=False, ax=ax)
    ax.tick_params(axis="x", rotation=35)
    ax.set(xlabel="", ylabel="Localization diameter (m)")
    save(fig, "diameter_distribution.png")

    fig, ax = plt.subplots(figsize=(8, 5))
    for name in DISPLAY_STRATEGIES:
        g = df[df.strategy == name]
        x = np.sort(g.diameter_m.to_numpy())
        ax.plot(x, np.arange(1, len(x)+1)/len(x), label=DISPLAY_LABELS[name],
                linewidth=2.3 if name == "gdop_mean" else 1.2)
    ax.set(xlabel="定位区域直径 (m)", ylabel="经验累积分布", xlim=(0, None))
    ax.grid(alpha=.25); ax.legend(fontsize=8, ncol=2)
    save_paper_figure(fig, "diameter_cdf", "fig3_diameter_cdf")

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
    plt.rcParams.update({
        "font.family": "sans-serif",
        "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans SC", "DejaVu Sans"],
        "axes.unicode_minus": False,
        "pdf.fonttype": 42,
    })
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
