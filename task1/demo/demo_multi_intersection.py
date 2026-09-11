from __future__ import annotations

import matplotlib.pyplot as plt
from matplotlib.patches import Polygon

from common import GREEN, LIGHT_BLUE, Point, draw_wedge, observation, save, setup
from src.q1 import clip_polygon_with_disk, clipped_region_diameter, locate_polygon


def main() -> None:
    setup()
    target = Point(100.0, 300.0)
    sensors = [Point(-600.0, -400.0), Point(700.0, -300.0), Point(700.0, 700.0)]
    observations = [observation(sensor, target) for sensor in sensors]
    polygon = locate_polygon(observations)
    result = clipped_region_diameter(clip_polygon_with_disk(polygon))

    fig, ax = plt.subplots(figsize=(7.0, 6.1))
    colors = ["#9EB9CE", "#B7C9B6", "#C8B8C9"]
    for obs, color in zip(observations, colors):
        draw_wedge(ax, obs, 1800.0, color=color, alpha=0.18)
    ax.add_patch(
        Polygon(
            [(point.x, point.y) for point in polygon],
            closed=True,
            facecolor=GREEN,
            edgecolor="#315F4A",
            linewidth=2.0,
            alpha=0.48,
            label=r"intersection $P$",
        )
    )
    ax.scatter([point.x for point in sensors], [point.y for point in sensors], color="#263746", s=35, zorder=5)
    for index, sensor in enumerate(sensors, 1):
        ax.text(sensor.x + 25, sensor.y + 25, rf"$S_{index}$")
    ax.plot(
        [result.first.x, result.second.x],
        [result.first.y, result.second.y],
        color="#A75D5D",
        linewidth=2.2,
        marker="o",
        markersize=4,
        label=rf"diameter $D={result.distance:.1f}$ m",
    )
    inset = ax.inset_axes([0.08, 0.62, 0.29, 0.29])
    inset.add_patch(
        Polygon(
            [(point.x, point.y) for point in polygon],
            closed=True,
            facecolor=GREEN,
            edgecolor="#315F4A",
            linewidth=1.5,
            alpha=0.52,
        )
    )
    inset.plot(
        [result.first.x, result.second.x],
        [result.first.y, result.second.y],
        color="#A75D5D",
        linewidth=1.7,
        marker="o",
        markersize=3,
    )
    inset.set(xlim=(65, 135), ylim=(260, 340), title="localization region")
    inset.set_aspect("equal")
    inset.grid(alpha=0.15)
    inset.tick_params(labelsize=7)
    ax.set(xlabel="x (m)", ylabel="y (m)", xlim=(-750, 850), ylim=(-520, 1050))
    ax.set_aspect("equal")
    ax.grid(alpha=0.14)
    ax.legend(loc="upper right", frameon=False)
    save(fig, "fig2_multi_station_intersection")


if __name__ == "__main__":
    main()
