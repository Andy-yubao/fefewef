"""Render the Q3 source-count response from the audited summary table."""

from __future__ import annotations

import csv
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np


plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


ROOT = Path(__file__).resolve().parents[4]
SOURCE = ROOT / "results" / "task3_sensitivity_analysis" / "data_only" / "tables" / "source_count_summary.csv"


def load_rows() -> list[dict[str, float]]:
    with SOURCE.open("r", encoding="utf-8", newline="") as handle:
        rows = [{key: float(value) for key, value in row.items()}
                for row in csv.DictReader(handle)]

    counts = [int(row["source_count"]) for row in rows]
    assert counts == list(range(10, 17))
    assert sum(int(row["cases"]) for row in rows) == 100
    assert all(int(row["all_clear_cases"]) == int(row["cases"]) for row in rows)
    for row in rows:
        expected = row["mean_case_time_s"] / row["source_count"]
        assert np.isclose(row["mean_time_per_source_s"], expected, rtol=0.0, atol=1e-9)
    return rows


def main() -> None:
    rows = load_rows()
    counts = np.array([row["source_count"] for row in rows])
    case_time = np.array([row["mean_case_time_s"] for row in rows])
    per_source = np.array([row["mean_time_per_source_s"] for row in rows])

    fig, (ax_total, ax_unit) = plt.subplots(
        2, 1, figsize=(8.4, 7.3), sharex=True, constrained_layout=True,
        gridspec_kw={"height_ratios": [1, 1]},
    )

    for ax in (ax_total, ax_unit):
        ax.grid(True, linewidth=0.5, alpha=0.30)
        ax.set_xlim(9.7, 16.3)
        ax.set_xticks(counts)

    ax_total.plot(counts, case_time, color="#1769aa", linewidth=2.0, zorder=3)
    ax_total.scatter(counts, case_time, s=55, color="#1769aa", edgecolors="white",
                     linewidth=0.9, zorder=4)
    ax_total.set_ylabel("平均每场总完成时间 T / (s/场)")
    ax_total.set_ylim(2750, 3850)
    ax_total.set_title("Q3 源数响应：场总时间与单位源时间", fontsize=14, pad=10)
    ax_unit.plot(counts, per_source, color="#8056a5", linewidth=2.0, zorder=3)
    ax_unit.scatter(counts, per_source, s=55, color="#8056a5", edgecolors="white",
                    linewidth=0.9, zorder=4)
    ax_unit.set_xlabel("源数 N / 个")
    ax_unit.set_ylabel("平均单位源完成时间 T/N / (s/源)")
    ax_unit.set_ylim(195, 315)
    out_dir = ROOT / "paper_assets" / "paper_figures" / "section7"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "fig1_q3_source_count_response.png", dpi=220)
    fig.savefig(out_dir / "fig1_q3_source_count_response.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
