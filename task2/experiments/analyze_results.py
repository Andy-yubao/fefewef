"""Summaries, paired comparisons, and cluster bootstrap intervals."""
from __future__ import annotations

from pathlib import Path
import numpy as np
import pandas as pd


TASK_ROOT = Path(__file__).resolve().parents[1]
RAW = TASK_ROOT / "results" / "raw"
TABLES = TASK_ROOT / "results" / "tables"


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
                        f"{prefix}_p95": x.quantile(.95), f"{prefix}_p99": x.quantile(.99),
                        f"{prefix}_max": x.max()})
        row.update({"detection_probability": g["detected"].mean(),
                    "no_signal_rate": (g["outcome"] == "no_signal").mean(),
                    "near_rate": (g["outcome"] == "near").mean(),
                    "move_distance_mean": g["move_distance_m"].mean(),
                    "move_distance_median": g["move_distance_m"].median(),
                    "move_time_mean": g["move_time_s"].mean(),
                    "selection_runtime_mean": g["selection_runtime_s"].mean(),
                    "selection_runtime_median": g["selection_runtime_s"].median(),
                    "selection_runtime_p95": g["selection_runtime_s"].quantile(.95),
                    "candidate_count_mean": g["candidate_count"].mean()})
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


def main():
    TABLES.mkdir(parents=True, exist_ok=True)
    df = pd.read_csv(RAW / "evaluations.csv")
    summary = summarize(df)
    summary.to_csv(TABLES / "strategy_summary.csv", index=False)
    pairwise = paired_comparisons(df)
    pairwise.to_csv(TABLES / "pairwise_comparison.csv", index=False)
    pairwise[pairwise["strategy_b"] == "random"].to_csv(
        TABLES / "improvement_vs_random.csv", index=False)
    sensitivity(df, "error_model").to_csv(TABLES / "sensitivity_error.csv",
                                            index=False)
    sensitivity(df, "radius_mode").to_csv(TABLES / "sensitivity_radius.csv",
                                            index=False)
    print(summary[["strategy", "diameter_mean", "diameter_median", "diameter_p95",
                   "detection_probability", "move_distance_mean",
                   "selection_runtime_mean"]].to_string(index=False))


if __name__ == "__main__":
    main()

