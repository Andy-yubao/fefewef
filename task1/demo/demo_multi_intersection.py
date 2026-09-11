from __future__ import annotations

import math
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import ConnectionPatch, Patch, Polygon

from common import Point, setup
from src.q1 import (
    BearingObservation,
    clip_polygon_with_disk,
    clipped_region_diameter,
    locate_polygon,
)


SENSORS = [
    Point(713.63, 1193.59),
    Point(-939.50, 362.10),
    Point(590.63, -611.06),
]
MEASURED_BEARINGS_DEG = [235.05529, 356.78364, 117.85767]

STATION_COLOR = "#263B4D"
CENTERLINE_COLOR = "#527B9D"
BOUNDARY_COLOR = "#718392"
MAIN_REGION_FACE = "#C7DFC9"
MAIN_REGION_EDGE = "#6F9E82"
INSET_REGION_FACE = "#AFCFE3"
INSET_REGION_EDGE = "#527B9D"
DIAMETER_COLOR = "#A75D5D"


def observations() -> list[BearingObservation]:
    return [
        BearingObservation(sensor, bearing, error_deg=1.0)
        for sensor, bearing in zip(SENSORS, MEASURED_BEARINGS_DEG)
    ]


def draw_direction_lines(
    ax: plt.Axes,
    observation: BearingObservation,
    reach: float = 2200.0,
) -> None:
    for angle_offset, linestyle, color, linewidth in (
        (-observation.error_deg, "--", BOUNDARY_COLOR, 0.85),
        (0.0, "-", CENTERLINE_COLOR, 1.05),
        (observation.error_deg, "--", BOUNDARY_COLOR, 0.85),
    ):
        angle = math.radians(observation.bearing_deg + angle_offset)
        end = Point(
            observation.sensor.x + reach * math.cos(angle),
            observation.sensor.y + reach * math.sin(angle),
        )
        ax.plot(
            [observation.sensor.x, end.x],
            [observation.sensor.y, end.y],
            color=color,
            linestyle=linestyle,
            linewidth=linewidth,
            alpha=0.82,
            zorder=1,
        )


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
            "axes.labelsize": 10,
            "axes.titlesize": 12,
            "legend.fontsize": 8,
        }
    )

    fixed_observations = observations()
    polygon = locate_polygon(fixed_observations)
    region = clip_polygon_with_disk(polygon)
    diameter = clipped_region_diameter(region)

    fig, ax = plt.subplots(figsize=(7.0, 6.1))
    for observation in fixed_observations:
        draw_direction_lines(ax, observation)

    ax.scatter(
        [sensor.x for sensor in SENSORS],
        [sensor.y for sensor in SENSORS],
        s=38,
        color=STATION_COLOR,
        edgecolor="white",
        linewidth=0.45,
        zorder=4,
    )
    station_label_offsets = [(30.0, 34.0), (-30.0, -92.0), (32.0, 38.0)]
    for index, (sensor, offset) in enumerate(zip(SENSORS, station_label_offsets), 1):
        ax.text(
            sensor.x + offset[0],
            sensor.y + offset[1],
            rf"$S_{index}$",
            color=STATION_COLOR,
            fontsize=10,
            ha="center",
            va="center",
        )

    polygon_xy = [(point.x, point.y) for point in polygon]
    ax.add_patch(
        Polygon(
            polygon_xy,
            closed=True,
            facecolor=MAIN_REGION_FACE,
            edgecolor=MAIN_REGION_EDGE,
            linewidth=1.1,
            alpha=0.82,
            zorder=5,
        )
    )

    ax.set(
        xlabel=r"$x$（m）",
        ylabel=r"$y$（m）",
        xlim=(-1100.0, 900.0),
        ylim=(-750.0, 1300.0),
    )
    ax.set_title("检测点示向交会示意图", loc="center", pad=10)
    ax.set_aspect("equal")
    ax.set_axisbelow(True)
    ax.grid(color="#D8DEE3", linewidth=0.55, alpha=0.48)

    legend_handles = [
        Line2D(
            [0],
            [0],
            marker="o",
            linestyle="none",
            markerfacecolor=STATION_COLOR,
            markeredgecolor=STATION_COLOR,
            markersize=5,
            label="检测点",
        ),
        Line2D([0], [0], color=CENTERLINE_COLOR, linewidth=1.2, label="示向中心线"),
        Line2D(
            [0],
            [0],
            color=BOUNDARY_COLOR,
            linewidth=1.0,
            linestyle="--",
            label="±1°误差边界",
        ),
        Patch(
            facecolor=MAIN_REGION_FACE,
            edgecolor=MAIN_REGION_EDGE,
            label="干扰源位置范围",
        ),
    ]
    ax.legend(
        handles=legend_handles,
        loc="lower left",
        ncol=2,
        frameon=True,
        framealpha=0.94,
        facecolor="white",
        edgecolor="#D8DEE3",
        handlelength=2.4,
        columnspacing=1.15,
        borderpad=0.65,
    )

    inset = ax.inset_axes([0.105, 0.695, 0.315, 0.225])
    inset.add_patch(
        Polygon(
            polygon_xy,
            closed=True,
            facecolor=INSET_REGION_FACE,
            edgecolor=INSET_REGION_EDGE,
            linewidth=1.0,
            alpha=0.82,
            zorder=2,
        )
    )
    inset.plot(
        [diameter.first.x, diameter.second.x],
        [diameter.first.y, diameter.second.y],
        color=DIAMETER_COLOR,
        linewidth=1.35,
        marker="o",
        markersize=3.2,
        zorder=3,
    )
    inset.scatter(
        [point.x for point in polygon],
        [point.y for point in polygon],
        s=10,
        color=INSET_REGION_EDGE,
        zorder=4,
    )
    inset.text(
        75.0,
        283.0,
        rf"$D={diameter.distance:.2f}\,\mathrm{{m}}$",
        color=DIAMETER_COLOR,
        fontsize=7,
    )
    inset.set(xlim=(72.0, 128.0), ylim=(280.0, 330.0))
    inset.set_aspect("equal")
    inset.set_axisbelow(True)
    inset.grid(color="#D8DEE3", linewidth=0.45, alpha=0.48)
    inset.tick_params(labelsize=6, width=0.6, length=2.5)
    inset.spines["top"].set_visible(False)
    inset.spines["right"].set_visible(False)

    region_center = Point(
        sum(point.x for point in polygon) / len(polygon),
        sum(point.y for point in polygon) / len(polygon),
    )
    fig.add_artist(
        ConnectionPatch(
            xyA=(126.0, 282.0),
            coordsA=inset.transData,
            xyB=(region_center.x, region_center.y),
            coordsB=ax.transData,
            color="#AAB8C1",
            linewidth=0.75,
            alpha=0.78,
            zorder=2,
        )
    )

    figure_dir = Path(__file__).resolve().parents[1] / "figures"
    figure_dir.mkdir(parents=True, exist_ok=True)
    fig.tight_layout()
    fig.savefig(
        figure_dir / "fig2_multi_station_intersection.png",
        dpi=600,
        bbox_inches="tight",
    )
    fig.savefig(
        figure_dir / "fig2_multi_station_intersection.pdf",
        bbox_inches="tight",
    )
    plt.close(fig)
    print(
        f"vertex_count={len(polygon)}, D={diameter.distance:.10f} m, "
        f"target_disk_active={region.circle_active}"
    )


if __name__ == "__main__":
    main()
