"""Render the Q3 seven-point coverage certificate in the route-plot style."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle
import numpy as np


# Keep Chinese labels legible in the manuscript export.
plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False


TARGET_RADIUS_M = 1800.0
RECEPTION_RADIUS_M = 1000.0
RING_RADIUS_M = 1200.0


def main() -> None:
    theta = np.arange(6) * np.pi / 3.0
    ring = np.column_stack((
        RING_RADIUS_M * np.cos(theta),
        RING_RADIUS_M * np.sin(theta),
    ))
    points = np.vstack((np.zeros((1, 2)), ring))

    # The boundary midpoint between V1 and V2 is the analytic worst case.
    worst_angle = np.pi / 6.0
    worst_point = TARGET_RADIUS_M * np.array(
        [np.cos(worst_angle), np.sin(worst_angle)]
    )
    nearest_vertex = ring[0]

    fig, ax = plt.subplots(figsize=(8.2, 8.0), constrained_layout=True)

    target = Circle(
        (0.0, 0.0),
        TARGET_RADIUS_M,
        facecolor="#e8f1f8",
        edgecolor="#6f8797",
        linewidth=1.2,
        alpha=0.45,
        zorder=0,
    )
    ax.add_patch(target)

    # Reception disks are deliberately low-opacity so overlap is legible.
    for point in points:
        ax.add_patch(Circle(
            tuple(point),
            RECEPTION_RADIUS_M,
            facecolor="#b8d8e8",
            edgecolor="#78a9bf",
            linewidth=0.9,
            alpha=0.10,
            zorder=1,
        ))

    # The same skeleton style and colors as task3/experiments/plot_route.py.
    closed_ring = np.vstack((ring, ring[0]))
    ax.plot(
        closed_ring[:, 0],
        closed_ring[:, 1],
        color="#1769aa",
        linestyle="--",
        linewidth=1.6,
        zorder=2,
    )
    ax.plot(
        [0.0, ring[0, 0]],
        [0.0, ring[0, 1]],
        color="#1769aa",
        linestyle="--",
        linewidth=1.6,
        zorder=2,
    )
    ax.scatter(
        points[:, 0],
        points[:, 1],
        marker="o",
        s=75,
        facecolors="none",
        edgecolors="#8056a5",
        linewidth=1.5,
        zorder=4,
    )
    ax.scatter(
        [0.0],
        [0.0],
        marker="s",
        s=75,
        color="#222222",
        zorder=5,
    )

    for index, point in enumerate(ring, start=1):
        ax.annotate(
            f"V{index}",
            point,
            xytext=(6, -14),
            textcoords="offset points",
            fontsize=10,
            color="#603b82",
            fontweight="semibold",
        )

    ax.scatter(
        [worst_point[0]],
        [worst_point[1]],
        marker="X",
        s=72,
        color="#d1495b",
        zorder=5,
    )
    ax.plot(
        [nearest_vertex[0], worst_point[0]],
        [nearest_vertex[1], worst_point[1]],
        color="#c2415d",
        linestyle=":",
        linewidth=1.8,
        zorder=3,
    )
    ax.annotate(
        "最坏边界点\n968.902 m < 1000 m",
        worst_point,
        xytext=(-12, 20),
        textcoords="offset points",
        ha="right",
        fontsize=9,
        color="#287a48",
        bbox={
            "facecolor": "white",
            "edgecolor": "#3f9a5b",
            "alpha": 0.90,
            "boxstyle": "round,pad=0.3",
        },
    )

    handles = [
        Line2D([0], [0], color="#6f8797", lw=1.2,
               label="搜索边界（半径 1800 m）"),
        Line2D([0], [0], color="#78a9bf", lw=1.0,
               label="必接收圆（半径 1000 m）"),
        Line2D([0], [0], marker="o", color="none",
               markerfacecolor="none", markeredgecolor="#8056a5",
               markersize=8, label="理论覆盖点"),
        Line2D([0], [0], marker="s", color="none",
               markerfacecolor="#222222", markeredgecolor="#222222",
               markersize=7, label="原点"),
        Line2D([0], [0], marker="X", color="none",
               markerfacecolor="#d1495b", markeredgecolor="#d1495b",
               markersize=8, label="解析最坏点"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=9, framealpha=0.93)
    ax.set_title("Q3 七点覆盖骨架与 1000 m 保证", fontsize=14, pad=10)
    ax.set_xlabel("x / m")
    ax.set_ylabel("y / m")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-2050, 2050)
    ax.set_ylim(-2050, 2050)
    ax.grid(True, linewidth=0.5, alpha=0.30)

    out_dir = Path(__file__).resolve().parents[3] / "paper_figures" / "section5"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "fig2_q3_seven_point_coverage.png", dpi=220)
    fig.savefig(out_dir / "fig2_q3_seven_point_coverage.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
