from __future__ import annotations

import math

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
import numpy as np

from common import GREEN, RED, Point, draw_region_boundary, save, setup
from src.q1 import clip_polygon_with_disk, clipped_region_diameter


def main() -> None:
    setup()
    polygon = [Point(1380.0, -760.0), Point(2180.0, -620.0), Point(2120.0, 720.0), Point(1420.0, 610.0)]
    region = clip_polygon_with_disk(polygon)
    result = clipped_region_diameter(region)

    fig, ax = plt.subplots(figsize=(7.1, 6.0))
    ax.add_patch(Circle((0.0, 0.0), 1800.0, fill=False, edgecolor="#697783", linewidth=1.5, label="target disk"))
    ax.add_patch(
        Polygon(
            [(point.x, point.y) for point in polygon],
            closed=True,
            facecolor="#AFC6D8",
            edgecolor="#527B9D",
            linewidth=1.5,
            linestyle="--",
            alpha=0.28,
            label=r"half-plane polygon $P$",
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
    ax.contourf(xx, yy, mask.astype(float), levels=[0.5, 1.5], colors=[GREEN], alpha=0.43)
    draw_region_boundary(ax, region)
    ax.plot(
        [result.first.x, result.second.x],
        [result.first.y, result.second.y],
        color=RED,
        linewidth=2.1,
        marker="o",
        markersize=4,
        label=rf"$D={result.distance:.1f}$ m",
    )
    ax.annotate("circular arc", xy=(1790, 120), xytext=(1510, 900), arrowprops={"arrowstyle": "->", "color": "#5E6872"})
    ax.set(xlabel="x (m)", ylabel="y (m)", xlim=(1100, 2260), ylim=(-1020, 1100))
    ax.set_aspect("equal")
    ax.grid(alpha=0.14)
    ax.legend(loc="lower right", frameon=False)
    save(fig, "fig3_active_target_disk_clipping")


if __name__ == "__main__":
    main()

