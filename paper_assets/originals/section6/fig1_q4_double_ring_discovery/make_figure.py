"""Render the Q4 certified double-ring directional-discovery structure."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Wedge
import numpy as np


plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ARENA_RADIUS_M = 1800.0
INNER_RADIUS_M = 980.0
RECEPTION_RADIUS_M = 1000.0
OUTER_RADIUS_M = ARENA_RADIUS_M / np.cos(np.pi / 12.0) + 0.25


def ring(radius: float, angles: np.ndarray) -> np.ndarray:
    return np.column_stack((radius * np.cos(angles), radius * np.sin(angles)))


def main() -> None:
    inner_angles = np.pi / 12.0 + np.arange(12) * np.pi / 6.0
    outer_angles = np.arange(12) * np.pi / 6.0
    inner = ring(INNER_RADIUS_M, inner_angles)
    outer = ring(OUTER_RADIUS_M, outer_angles)

    fig, ax = plt.subplots(figsize=(8.6, 8.0), constrained_layout=True)
    ax.add_patch(Circle(
        (0, 0), ARENA_RADIUS_M, facecolor="#e8f1f8", edgecolor="#6f8797",
        linewidth=1.25, alpha=0.50, zorder=0,
    ))

    # Triangulation skeleton: origin, inner dodecagon, and outer dodecagon.
    closed_inner = np.vstack((inner, inner[0]))
    closed_outer = np.vstack((outer, outer[0]))
    ax.plot(closed_inner[:, 0], closed_inner[:, 1], "--", color="#1769aa", lw=1.25, zorder=2)
    ax.plot(closed_outer[:, 0], closed_outer[:, 1], "--", color="#1769aa", lw=1.25, zorder=2)
    for index in range(12):
        ax.plot([inner[index, 0], outer[index, 0]], [inner[index, 1], outer[index, 1]],
                "--", color="#1769aa", lw=0.85, alpha=0.75, zorder=2)
        ax.plot([inner[index, 0], outer[(index + 1) % 12, 0]],
                [inner[index, 1], outer[(index + 1) % 12, 1]],
                "--", color="#1769aa", lw=0.85, alpha=0.75, zorder=2)
        ax.plot([0, inner[index, 0]], [0, inner[index, 1]],
                "--", color="#1769aa", lw=0.70, alpha=0.55, zorder=1)

    ax.scatter([0], [0], marker="s", s=62, color="#222222", zorder=5)
    ax.scatter(inner[:, 0], inner[:, 1], marker="o", s=54, facecolors="none",
               edgecolors="#8056a5", linewidth=1.45, zorder=5)
    ax.scatter(outer[:, 0], outer[:, 1], marker="o", s=54, facecolors="none",
               edgecolors="#8056a5", linewidth=1.45, zorder=5)

    # Source examples: omni, ordinary directional, and a boundary-outward extreme.
    omni = np.array([-430.0, 520.0])
    directional = np.array([-520.0, -640.0])
    # Tangency point of one outer-dodecagon side and the 1800 m arena circle.
    # Its outward normal is the most adverse orientation at the boundary.
    extreme_angle = np.pi / 12.0
    extreme = ARENA_RADIUS_M * np.array([np.cos(extreme_angle), np.sin(extreme_angle)])
    ax.scatter(*omni, marker="o", s=98, color="#d1495b", edgecolors="white", linewidth=0.8, zorder=8)
    ax.scatter(*directional, marker=(3, 0, 140), s=160, color="#d78d32", edgecolors="white", linewidth=0.8, zorder=8)
    ax.scatter(*extreme, marker=(3, 0, np.degrees(extreme_angle)), s=170, color="#d1495b", edgecolors="white", linewidth=0.8, zorder=9)

    # Faint half-planes make the two directional orientations explicit.
    ax.add_patch(Wedge(tuple(directional), 460, 50, 230, facecolor="#d78d32", alpha=0.10,
                       edgecolor="#bd7422", linestyle=":", linewidth=1.0, zorder=3))
    ax.add_patch(Wedge(tuple(extreme), 390, -75, 105, facecolor="#d1495b", alpha=0.12,
                       edgecolor="#c2415d", linestyle=":", linewidth=1.1, zorder=4))

    # The outward-facing boundary source can still reach the outer-ring point.
    outer_tangent_vertex = outer[0]
    distance = np.linalg.norm(extreme - outer_tangent_vertex)
    ax.plot([extreme[0], outer_tangent_vertex[0]], [extreme[1], outer_tangent_vertex[1]],
            color="#3f9a5b", linestyle=":", linewidth=2.0, zorder=6)
    ax.annotate(
        f"切线极端情形仍可发现\n外环检测点距源 {distance:.1f} m < 1000 m",
        xy=extreme,
        xytext=(760, 850),
        fontsize=9.4,
        color="#287a48",
        bbox={"facecolor": "white", "edgecolor": "#3f9a5b", "alpha": 0.94,
              "boxstyle": "round,pad=0.34"},
        arrowprops={"arrowstyle": "-", "color": "#3f9a5b", "lw": 1.0},
        zorder=10,
    )

    handles = [
        Line2D([0], [0], color="#6f8797", lw=1.25, label="搜索边界（半径 1800 m）"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="none",
               markeredgecolor="#8056a5", markersize=8, label="双环覆盖点（24 点）"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#d1495b",
               markersize=8, label="一般位置全向源"),
        Line2D([0], [0], marker="^", color="none", markerfacecolor="#d78d32",
               markersize=9, label="一般位置定向源"),
        Line2D([0], [0], marker=">", color="none", markerfacecolor="#d1495b",
               markersize=9, label="边界外向定向源（极端）"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=8.8, framealpha=0.94)
    ax.set_title("Q4 25 点双环定向发现结构", fontsize=14, pad=10)
    ax.set_xlabel("x / m")
    ax.set_ylabel("y / m")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-2150, 2300)
    ax.set_ylim(-2150, 2150)
    ax.grid(True, linewidth=0.5, alpha=0.30)

    out_dir = Path(__file__).resolve().parents[3] / "paper_figures" / "section6"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "fig1_q4_double_ring_discovery.png", dpi=220)
    fig.savefig(out_dir / "fig1_q4_double_ring_discovery.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
