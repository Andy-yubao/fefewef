from __future__ import annotations

import math

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
import numpy as np

from common import GREEN, RED, Point, save, setup
from src.q1 import clip_polygon_with_disk, clipped_region_diameter


def main() -> None:
    setup()
    polygon = [Point(1380.0, -760.0), Point(2180.0, -620.0), Point(2120.0, 720.0), Point(1420.0, 610.0)]
    region = clip_polygon_with_disk(polygon)
    result = clipped_region_diameter(region)

    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    ax.add_patch(Circle((0.0, 0.0), 1800.0, fill=False, edgecolor="#697783", linewidth=1.5, label="目标圆域"))
    ax.add_patch(
        Polygon(
            [(point.y, point.x) for point in polygon],
            closed=True,
            facecolor="#AFC6D8",
            edgecolor="#527B9D",
            linewidth=1.5,
            linestyle="--",
            alpha=0.28,
            label=r"半平面多边形 $P$",
        )
    )
    # A fine fill is visual only; all reported geometry comes from analytic arcs.
    grid_x = np.linspace(1250.0, 1850.0, 280)
    grid_y = np.linspace(-800.0, 800.0, 280)
    xx, yy = np.meshgrid(grid_x, grid_y)
    mask = xx * xx + yy * yy <= 1800.0**2
    poly_constraints = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        edge_x, edge_y = end.x - start.x, end.y - start.y
        poly_constraints.append(edge_x * (yy - start.y) - edge_y * (xx - start.x) >= 0.0)
    for constraint in poly_constraints:
        mask &= constraint
    ax.contourf(yy, xx, mask.astype(float), levels=[0.5, 1.5], colors=[GREEN], alpha=0.43)
    for segment in region.segments:
        ax.plot([segment.start.y, segment.end.y], [segment.start.x, segment.end.x], color=GREEN, linewidth=2.0)
    for arc in region.arcs:
        angles = np.linspace(arc.start_angle, arc.end_angle, 240)
        ax.plot(arc.radius * np.sin(angles), arc.radius * np.cos(angles), color=GREEN, linewidth=2.0)
    ax.plot(
        [result.first.y, result.second.y],
        [result.first.x, result.second.x],
        color=RED,
        linewidth=2.1,
        marker="o",
        markersize=4,
        label=rf"直径 $D={result.distance:.1f}$ m",
    )
    ax.annotate("有效圆弧", xy=(120, 1790), xytext=(480, 2050), arrowprops={"arrowstyle": "->", "color": "#5E6872"})
    ax.set(xlabel="y / m", ylabel="x / m", xlim=(-1020, 1100), ylim=(1100, 2260))
    ax.set_aspect("equal")
    ax.grid(alpha=0.14)
    ax.legend(loc="lower left", frameon=False)
    save(fig, "fig3_active_target_disk_clipping")


if __name__ == "__main__":
    main()
