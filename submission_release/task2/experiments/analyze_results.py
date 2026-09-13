"""Summaries and paired comparisons for the four paper strategies."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd

TASK_ROOT = Path(__file__).resolve().parents[1]
RAW = TASK_ROOT / "results" / "raw"
TABLES = TASK_ROOT / "results" / "tables"


def summarize(df: pd.DataFrame) -> pd.DataFrame:
    rows = []
    for name, group in df.groupby("strategy", sort=True):
        d, a = group["diameter_m"], group["area_m2"]
        rows.append({
            "strategy": name, "n": len(group),
            "diameter_mean": d.mean(), "diameter_median": d.median(),
            "diameter_std": d.std(), "diameter_p90": d.quantile(.90),
            "diameter_p75": d.quantile(.75), "diameter_p95": d.quantile(.95),
            "diameter_p99": d.quantile(.99), "diameter_max": d.max(),
            "area_mean": a.mean(), "area_median": a.median(),
            "area_std": a.std(), "area_p90": a.quantile(.90),
            "area_p75": a.quantile(.75), "area_p95": a.quantile(.95),
            "area_p99": a.quantile(.99), "area_max": a.max(),
            "detection_probability": group["detected"].mean(),
            "bearing_probability": (group["outcome"] == "bearing").mean(),
            "no_signal_rate": (group["outcome"] == "no_signal").mean(),
            "near_rate": (group["outcome"] == "near").mean(),
            "move_distance_mean": group["move_distance_m"].mean(),
            "move_distance_median": group["move_distance_m"].median(),
            "move_distance_p95": group["move_distance_m"].quantile(.95),
            "move_time_mean": group["move_time_s"].mean(),
            "selection_runtime_mean": group["selection_runtime_s"].mean(),
            "selection_runtime_median": group["selection_runtime_s"].median(),
            "selection_runtime_p95": group["selection_runtime_s"].quantile(.95),
            "candidate_count_mean": group["candidate_count"].mean(),
            "exact_objective_evaluation_count_mean":
                group["exact_objective_evaluation_count"].mean(),
        })
    return pd.DataFrame(rows).sort_values("diameter_mean")


def paired_comparisons(df: pd.DataFrame) -> pd.DataFrame:
    wide = df.pivot(index=["scenario_id", "replicate"],
                    columns="strategy", values="diameter_m")
    rows = []
    for first in wide.columns:
        for second in wide.columns:
            if first == second:
                continue
            delta = (wide[second] - wide[first]).dropna().to_numpy()
            rows.append({
                "strategy_a": first, "strategy_b": second,
                "win_rate_a": float(np.mean(delta > 1e-9)),
                "tie_rate": float(np.mean(np.abs(delta) <= 1e-9)),
                "loss_rate_a": float(np.mean(delta < -1e-9)),
                "mean_improvement_m": float(np.mean(delta)),
                "median_improvement_m": float(np.median(delta)),
            })
    return pd.DataFrame(rows)


def main() -> None:
    TABLES.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(RAW / "evaluations.csv")
    expected = {"gdop_mean", "geometry", "fim_e", "random"}
    actual = set(df["strategy"].unique())
    if actual != expected:
        raise ValueError(f"strategy set mismatch: {sorted(actual)}")
    summary = summarize(df)
    summary.to_csv(TABLES / "strategy_summary.csv", index=False)
    paired_comparisons(df).to_csv(TABLES / "pairwise_comparison.csv", index=False)
    df.groupby(["strategy", "error_model"], as_index=False).agg(
        n=("diameter_m", "size"), diameter_mean=("diameter_m", "mean"),
        diameter_median=("diameter_m", "median"),
        diameter_p95=("diameter_m", lambda x: x.quantile(.95)),
        detection_probability=("detected", "mean"),
        move_distance_mean=("move_distance_m", "mean"),
    ).to_csv(TABLES / "sensitivity_error.csv", index=False)
    df.groupby(["strategy", "radius_mode"], as_index=False).agg(
        n=("diameter_m", "size"), diameter_mean=("diameter_m", "mean"),
        diameter_median=("diameter_m", "median"),
        diameter_p95=("diameter_m", lambda x: x.quantile(.95)),
        detection_probability=("detected", "mean"),
        move_distance_mean=("move_distance_m", "mean"),
    ).to_csv(TABLES / "sensitivity_radius.csv", index=False)
    print(summary[["strategy", "n", "diameter_mean", "diameter_median",
                   "diameter_p95", "move_distance_mean",
                   "selection_runtime_mean"]].to_string(index=False))


if __name__ == "__main__":
    main()
