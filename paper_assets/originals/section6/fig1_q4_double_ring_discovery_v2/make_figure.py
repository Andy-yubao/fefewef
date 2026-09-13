"""Render the revised Q4 double-ring directional-discovery certificate."""

from __future__ import annotations

from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, FancyArrowPatch, Wedge
import numpy as np


plt.rcParams["font.sans-serif"] = ["SimHei", "DejaVu Sans"]
plt.rcParams["axes.unicode_minus"] = False

ARENA_RADIUS_M = 1800.0
INNER_RADIUS_M = 980.0
RECEPTION_RADIUS_M = 1000.0
OUTER_OFFSET_M = 0.25
OUTER_RADIUS_M = ARENA_RADIUS_M / np.cos(np.pi / 12.0) + OUTER_OFFSET_M


def ring(radius: float, angles: np.ndarray) -> np.ndarray:
    return np.column_stack((radius * np.cos(angles), radius * np.sin(angles)))


def main() -> None:
    inner_angles = np.pi / 12.0 + np.arange(12) * np.pi / 6.0
    outer_angles = np.arange(12) * np.pi / 6.0
    inner = ring(INNER_RADIUS_M, inner_angles)
    outer = ring(OUTER_RADIUS_M, outer_angles)

    fig, ax = plt.subplots(figsize=(8.8, 8.0), constrained_layout=True)
    ax.add_patch(Circle(
        (0, 0), ARENA_RADIUS_M, facecolor="#e8f1f8", edgecolor="#6f8797",
        linewidth=1.25, alpha=0.50, zorder=0,
    ))

    closed_inner = np.vstack((inner, inner[0]))
    closed_outer = np.vstack((outer, outer[0]))
    ax.plot(closed_inner[:, 0], closed_inner[:, 1], "--", color="#1769aa", lw=1.25, zorder=2)
    ax.plot(closed_outer[:, 0], closed_outer[:, 1], "--", color="#1769aa", lw=1.25, zorder=2)
    for index in range(12):
        ax.plot([inner[index, 0], outer[index, 0]],
                [inner[index, 1], outer[index, 1]],
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

    omni = np.array([-430.0, 520.0])
    directional = np.array([-520.0, -640.0])
    directional_bisector_deg = 140.0
    extreme_angle = np.pi / 12.0
    extreme_bisector_deg = float(np.degrees(extreme_angle))
    # A regular-polygon marker has its reference vertex at 90 degrees, so its
    # rotation must be the desired tip direction minus 90 degrees.
    directional_marker_rotation_deg = directional_bisector_deg - 90.0
    extreme_marker_rotation_deg = extreme_bisector_deg - 90.0
    normal = np.array([np.cos(extreme_angle), np.sin(extreme_angle)])
    tangent = np.array([-np.sin(extreme_angle), np.cos(extreme_angle)])
    extreme = ARENA_RADIUS_M * normal

    ax.scatter(*omni, marker="o", s=98, color="#d1495b", edgecolors="white",
               linewidth=0.8, zorder=8)
    ax.scatter(*directional, marker=(3, 0, directional_marker_rotation_deg), s=160, color="#d78d32",
               edgecolors="white", linewidth=0.8, zorder=8)
    ax.scatter(*extreme, marker=(3, 0, extreme_marker_rotation_deg), s=170,
               color="#d1495b", edgecolors="white", linewidth=0.8, zorder=9)

    ax.add_patch(Wedge(tuple(directional), 460, 50, 230, facecolor="#d78d32",
                       alpha=0.10, edgecolor="#bd7422", linestyle=":",
                       linewidth=1.0, zorder=3))
    ax.add_patch(Wedge(tuple(extreme), 440, -75, 105, facecolor="#d1495b",
                       alpha=0.12, edgecolor="#c2415d", linestyle=":",
                       linewidth=1.1, zorder=4))

    # In the extreme construction, the source is on the arena boundary and
    # points along the outward normal. The adjacent outer-ring side is 0.24 m
    # beyond the tangent, so both endpoints lie in the closed emitting half-plane.
    tangent_half_length = 520.0
    tangent_a = extreme - tangent_half_length * tangent
    tangent_b = extreme + tangent_half_length * tangent
    ax.plot([tangent_a[0], tangent_b[0]], [tangent_a[1], tangent_b[1]],
            color="#70838e", linestyle="-.", linewidth=1.25, zorder=5)
    arrow_end = extreme + 310.0 * normal
    ax.add_patch(FancyArrowPatch(
        tuple(extreme), tuple(arrow_end), arrowstyle="-|>", mutation_scale=13,
        color="#c2415d", linewidth=1.3, zorder=7,
    ))
    ax.annotate("外法向发射", xy=tuple(arrow_end), xytext=(-2, 8),
                textcoords="offset points", ha="center", fontsize=8.8,
                color="#a9364b", zorder=9)
    ax.annotate("源点切线", xy=tuple(tangent_b), xytext=(-8, 5),
                textcoords="offset points", ha="right", fontsize=8.5,
                color="#586c78", zorder=9)

    nearest_outer = outer[0]
    distance = float(np.linalg.norm(extreme - nearest_outer))
    side_offset = float(np.dot(nearest_outer - extreme, normal))
    assert distance < RECEPTION_RADIUS_M
    assert side_offset > 0.0
    ax.plot([extreme[0], nearest_outer[0]], [extreme[1], nearest_outer[1]],
            color="#3f9a5b", linestyle=":", linewidth=2.0, zorder=6)
    ax.annotate(
        "边界外向极端情形\n"
        f"外环边位于源点切线外侧 {side_offset:.2f} m，端点仍在发射半平面内\n"
        f"最近外环点距源 {distance:.1f} m < 1000 m，因此仍可发现",
        xy=tuple(extreme), xytext=(560, 920), fontsize=8.7, color="#287a48",
        bbox={"facecolor": "white", "edgecolor": "#3f9a5b", "alpha": 0.95,
              "boxstyle": "round,pad=0.34"},
        arrowprops={"arrowstyle": "-", "color": "#3f9a5b", "lw": 1.0},
        zorder=10,
    )

    handles = [
        Line2D([0], [0], color="#6f8797", lw=1.25,
               label="搜索边界（半径 1800 m）"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="none",
               markeredgecolor="#8056a5", markersize=8,
               label="双环覆盖点（24 点）"),
        Line2D([0], [0], marker="s", color="none", markerfacecolor="#222222",
               markeredgecolor="#222222", markersize=7, label="中心覆盖点（1 点）"),
        Line2D([0], [0], marker="o", color="none", markerfacecolor="#d1495b",
               markeredgecolor="#d1495b", markersize=8, label="一般位置全向源"),
        Line2D([0], [0], marker="^", color="none",
               markerfacecolor="#d78d32", markeredgecolor="#d78d32",
               markersize=9, label="一般位置定向源"),
        Line2D([0], [0], marker="^", color="none",
               markerfacecolor="#d1495b", markeredgecolor="#d1495b",
               markersize=9, label="边界外向定向源（极端）"),
        Line2D([0], [0], color="#70838e", linestyle="-.", lw=1.25,
               label="极端源点处切线"),
    ]
    ax.legend(handles=handles, loc="lower left", fontsize=8.2, framealpha=0.94)
    ax.set_title("Q4 25 点双环定向发现结构", fontsize=14, pad=10)
    ax.set_xlabel("x / m")
    ax.set_ylabel("y / m")
    ax.set_aspect("equal", adjustable="box")
    ax.set_xlim(-2150, 2420)
    ax.set_ylim(-2150, 2200)
    ax.grid(True, linewidth=0.5, alpha=0.30)

    out_dir = Path(__file__).resolve().parents[3] / "paper_figures" / "section6"
    out_dir.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_dir / "fig1_q4_double_ring_discovery_v2.png", dpi=220)
    fig.savefig(out_dir / "fig1_q4_double_ring_discovery_v2.svg")
    plt.close(fig)


if __name__ == "__main__":
    main()
