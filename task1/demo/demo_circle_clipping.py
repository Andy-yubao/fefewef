from __future__ import annotations

import math
from pathlib import Path

import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
import numpy as np

from common import BLUE, GREEN, RED, Point, draw_region_boundary, setup
from src.q1 import clip_polygon_with_disk, clipped_region_diameter


def main() -> None:
    setup()
    plt.rcParams.update({"font.family": "sans-serif", "svg.fonttype": "none", "pdf.fonttype": 42})
    polygon = [
        Point(-1200.0, 900.0),
        Point(1200.0, 900.0),
        Point(1050.0, 2100.0),
        Point(-1050.0, 2100.0),
    ]
    region = clip_polygon_with_disk(polygon)
    result = clipped_region_diameter(region)

    fig, ax = plt.subplots(figsize=(7.2, 3.8))
    ax.add_patch(
        Circle(
            (0.0, 0.0),
            1800.0,
            fill=False,
            edgecolor="#697783",
            linewidth=1.25,
        )
    )
    ax.add_patch(
        Polygon(
            [(point.x, point.y) for point in polygon],
            closed=True,
            facecolor="#DDE8F0",
            edgecolor=BLUE,
            linewidth=1.0,
            linestyle="--",
            alpha=0.38,
        )
    )

    grid_x = np.linspace(-1300.0, 1300.0, 360)
    grid_y = np.linspace(850.0, 1850.0, 260)
    xx, yy = np.meshgrid(grid_x, grid_y)
    mask = xx * xx + yy * yy <= 1800.0**2
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        edge_x, edge_y = end.x - start.x, end.y - start.y
        mask &= edge_x * (yy - start.y) - edge_y * (xx - start.x) >= 0.0
    ax.contourf(xx, yy, mask.astype(float), levels=[0.5, 1.5], colors=[GREEN], alpha=0.45)

    draw_region_boundary(ax, region, linewidth=2.0)
    ax.plot(
        [result.first.x, result.second.x],
        [result.first.y, result.second.y],
        color=RED,
        linewidth=1.8,
        marker="o",
        markersize=3.5,
        zorder=5,
    )
    ax.plot([0.0, 0.0], [0.0, 1800.0], color="#596773", linewidth=0.9)
    ax.scatter([0.0], [0.0], s=25, color="#263746", zorder=5)

    ax.annotate(
        r"有效圆弧 $\gamma$",
        xy=(500.0, 1725.0),
        xytext=(930.0, 1930.0),
        arrowprops={"arrowstyle": "->", "color": "#596773", "linewidth": 0.8},
        fontsize=9.5,
        color="#263746",
    )
    ax.text(30.0, 280.0, r"$R_0$", fontsize=10, color="#263746")
    ax.text(-85.0, -130.0, r"$O$", fontsize=10, color="#263746")
    ax.text(0.0, 1250.0, r"$\Omega=P\cap B(O,R_0)$", fontsize=10.5, ha="center", color="#376F5B")
    ax.text(0.0, 770.0, rf"$D={result.distance:.1f}\,\mathrm{{m}}$", fontsize=9.5, ha="center", color=RED)
    ax.text(-1120.0, 2020.0, r"$P$", fontsize=11, color=BLUE)

    ax.set_xlim(-1950.0, 1950.0)
    ax.set_ylim(-180.0, 2150.0)
    ax.set_aspect("equal")
    ax.axis("off")
    figure_dir = Path(__file__).resolve().parents[1] / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(figure_dir / "fig3_active_target_disk_clipping.svg", bbox_inches="tight")
    fig.savefig(figure_dir / "fig3_active_target_disk_clipping.pdf", bbox_inches="tight")
    fig.savefig(figure_dir / "fig3_active_target_disk_clipping.png", dpi=600, bbox_inches="tight")
    plt.close(fig)


if __name__ == "__main__":
    main()
