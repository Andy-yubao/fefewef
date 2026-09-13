from __future__ import annotations

from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, Polygon

from common import Point, setup
from src.q1 import (
    BearingObservation,
    clip_polygon_with_disk,
    clipped_region_diameter,
    distance,
    locate_polygon,
    minimum_enclosing_circle_polygon,
)


SENSORS = [
    Point(713.63, 1193.59),
    Point(-939.50, 362.10),
    Point(590.63, -611.06),
]
MEASURED_BEARINGS_DEG = [235.05529, 356.78364, 117.85767]

POLYGON_FACE = "#AFCFE3"
POLYGON_EDGE = "#70869A"
DIAMETER_COLOR = "#263746"
DIAMETER_CIRCLE_COLOR = "#D94B64"
MINIMUM_CIRCLE_COLOR = "#2878B5"


def observations() -> list[BearingObservation]:
    return [
        BearingObservation(sensor, bearing, error_deg=1.0)
        for sensor, bearing in zip(SENSORS, MEASURED_BEARINGS_DEG)
    ]


def main() -> None:
    setup()
    mpl.rcParams.update(
        {
            "font.family": "sans-serif",
            "font.sans-serif": [
                "Microsoft YaHei",
                "SimHei",
                "Noto Sans CJK SC",
                "Arial",
                "DejaVu Sans",
            ],
            "axes.unicode_minus": False,
            "pdf.fonttype": 42,
            "svg.fonttype": "none",
            "font.size": 9,
            "axes.titlesize": 12,
            "legend.fontsize": 8,
        }
    )

    polygon = locate_polygon(observations())
    region = clip_polygon_with_disk(polygon)
    diameter = clipped_region_diameter(region)
    minimum_circle = minimum_enclosing_circle_polygon(polygon)
    diameter_center = (diameter.first + diameter.second) * 0.5
    diameter_radius = diameter.distance / 2.0
    outside_indices = {
        index
        for index, vertex in enumerate(polygon)
        if distance(vertex, diameter_center) > diameter_radius + 1.0e-7
    }

    fig, ax = plt.subplots(figsize=(7.2, 5.4))
    polygon_xy = [(point.x, point.y) for point in polygon]
    ax.add_patch(
        Polygon(
            polygon_xy,
            closed=True,
            facecolor=POLYGON_FACE,
            edgecolor=POLYGON_EDGE,
            linewidth=1.2,
            alpha=0.70,
            zorder=1,
        )
    )
    ax.add_patch(
        Circle(
            (diameter_center.x, diameter_center.y),
            diameter_radius,
            fill=False,
            edgecolor=DIAMETER_CIRCLE_COLOR,
            linewidth=1.8,
            linestyle="--",
            zorder=2,
        )
    )
    ax.add_patch(
        Circle(
            (minimum_circle.center.x, minimum_circle.center.y),
            minimum_circle.radius,
            fill=False,
            edgecolor=MINIMUM_CIRCLE_COLOR,
            linewidth=2.0,
            zorder=2,
        )
    )
    ax.plot(
        [diameter.first.x, diameter.second.x],
        [diameter.first.y, diameter.second.y],
        color=DIAMETER_COLOR,
        linewidth=1.7,
        zorder=4,
    )

    vertex_offsets = [
        (0.9, 1.2),
        (1.1, 0.9),
        (1.1, 0.9),
        (1.0, 1.0),
        (0.8, 1.0),
        (0.8, 1.0),
    ]
    for index, (vertex, offset) in enumerate(zip(polygon, vertex_offsets)):
        is_outside = index in outside_indices
        color = DIAMETER_CIRCLE_COLOR if is_outside else "#111111"
        ax.scatter(
            [vertex.x],
            [vertex.y],
            s=34 if is_outside else 24,
            color=color,
            edgecolor="white" if is_outside else color,
            linewidth=0.4,
            zorder=5,
        )
        ax.text(
            vertex.x + offset[0],
            vertex.y + offset[1],
            rf"$V_{index + 1}$",
            color=color,
            fontsize=9,
            zorder=6,
        )

    ax.text(
        diameter.first.x - 2.0,
        diameter.first.y - 1.0,
        r"$A$",
        fontsize=10,
        fontweight="bold",
        ha="right",
        va="center",
        zorder=7,
    )
    ax.text(
        diameter.second.x + 0.9,
        diameter.second.y - 1.3,
        r"$B$",
        fontsize=10,
        fontweight="bold",
        ha="left",
        va="center",
        zorder=7,
    )
    ax.scatter(
        [diameter_center.x],
        [diameter_center.y],
        marker="+",
        s=85,
        linewidth=1.5,
        color=DIAMETER_CIRCLE_COLOR,
        zorder=4,
    )
    ax.scatter(
        [minimum_circle.center.x],
        [minimum_circle.center.y],
        marker="+",
        s=85,
        linewidth=1.5,
        color=MINIMUM_CIRCLE_COLOR,
        zorder=4,
    )

    legend_handles = [
        Line2D(
            [0],
            [0],
            color=DIAMETER_COLOR,
            linewidth=1.7,
            label=rf"区域直径：$D={diameter.distance:.2f}\,\mathrm{{m}}$",
        ),
        Line2D(
            [0],
            [0],
            color=MINIMUM_CIRCLE_COLOR,
            linewidth=2.0,
            label=rf"最小覆盖圆：$2R_{{\min}}={2.0 * minimum_circle.radius:.2f}\,\mathrm{{m}}>D$",
        ),
        Line2D(
            [0],
            [0],
            color=DIAMETER_CIRCLE_COLOR,
            linewidth=1.8,
            linestyle="--",
            label=r"直径圆（直径为 $AB$）",
        ),
    ]
    ax.legend(
        handles=legend_handles,
        loc="upper center",
        bbox_to_anchor=(0.5, -0.09),
        ncol=3,
        frameon=False,
        handlelength=2.6,
        columnspacing=1.2,
    )
    ax.set(xlim=(73.0, 127.0), ylim=(282.0, 340.0))
    ax.set_aspect("equal")
    ax.set_xlabel(r"$x$（m）")
    ax.set_ylabel(r"$y$（m）")
    ax.set_axisbelow(True)
    ax.grid(color="#D8DEE3", linewidth=0.55, alpha=0.46)

    figure_dir = Path(__file__).resolve().parents[1] / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(
        figure_dir / "fig4_hexagon_counterexample.png",
        dpi=600,
        bbox_inches="tight",
    )
    fig.savefig(
        figure_dir / "fig4_hexagon_counterexample.pdf",
        bbox_inches="tight",
    )
    fig.savefig(
        figure_dir / "fig4_hexagon_counterexample.svg",
        bbox_inches="tight",
    )
    plt.close(fig)
    maximum_excess = max(
        distance(vertex, diameter_center) - diameter_radius for vertex in polygon
    )
    print(
        f"D={diameter.distance:.10f} m, R_min={minimum_circle.radius:.10f} m, "
        f"support={minimum_circle.support_vertex_indices}, "
        f"outside_vertices={tuple(index + 1 for index in sorted(outside_indices))}, "
        f"maximum_excess={maximum_excess:.6f} m"
    )


if __name__ == "__main__":
    main()
