from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle, ConnectionPatch, Patch, Polygon

from common import Point, setup
from src.q1 import BearingObservation, clip_polygon_with_disk, clipped_region_diameter, locate_polygon


SENSORS = [Point(713.63, 1193.59), Point(-939.50, 362.10), Point(590.63, -611.06)]
MEASURED_BEARINGS_DEG = [235.05529, 356.78364, 117.85767]
STATION_COLOR = "#263B4D"
CENTERLINE_COLOR = "#527B9D"
BOUNDARY_COLOR = "#718392"
MAIN_REGION_FACE = "#B9D9EA"
MAIN_REGION_EDGE = "#2F648C"
DIAMETER_COLOR = "#A75D5D"


def observations() -> list[BearingObservation]:
    return [BearingObservation(sensor, bearing, error_deg=1.0)
            for sensor, bearing in zip(SENSORS, MEASURED_BEARINGS_DEG)]


def draw_direction_lines(ax: plt.Axes, observation: BearingObservation, reach: float = 2200.0) -> None:
    for offset, linestyle, color, linewidth in ((-1.0, "--", BOUNDARY_COLOR, 0.85),
                                                 (0.0, "-", CENTERLINE_COLOR, 1.05),
                                                 (1.0, "--", BOUNDARY_COLOR, 0.85)):
        angle = math.radians(observation.bearing_deg + offset)
        end = Point(observation.sensor.x + reach * math.cos(angle),
                    observation.sensor.y + reach * math.sin(angle))
        ax.plot([observation.sensor.x, end.x], [observation.sensor.y, end.y],
                color=color, linestyle=linestyle, linewidth=linewidth, alpha=0.82, zorder=1)


def style_axes(ax: plt.Axes) -> None:
    ax.set_aspect("equal")
    ax.set_axisbelow(True)
    ax.grid(color="#D8DEE3", linewidth=0.55, alpha=0.48)
    ax.set_xlabel(r"$x$（m）")
    ax.set_ylabel(r"$y$（m）")


def global_panel(ax: plt.Axes, observations_: list[BearingObservation], polygon: list[Point], center: Point, radius: float) -> None:
    for observation in observations_:
        draw_direction_lines(ax, observation)
    ax.scatter([sensor.x for sensor in SENSORS], [sensor.y for sensor in SENSORS], s=38,
               color=STATION_COLOR, edgecolor="white", linewidth=0.45, zorder=4)
    offsets = [(30.0, 34.0), (-30.0, -92.0), (32.0, 38.0)]
    for index, (sensor, offset) in enumerate(zip(SENSORS, offsets), 1):
        ax.text(sensor.x + offset[0], sensor.y + offset[1], rf"$S_{index}$",
                color=STATION_COLOR, fontsize=10, ha="center", va="center")
    ax.add_patch(Polygon([(p.x, p.y) for p in polygon], closed=True,
                         facecolor=MAIN_REGION_FACE, edgecolor=MAIN_REGION_EDGE,
                         linewidth=1.7, alpha=0.88, zorder=5))
    ax.add_patch(Circle((center.x, center.y), radius, fill=False, color="#5E6872",
                        linestyle=(0, (3, 2)), linewidth=1.15, zorder=7))
    ax.set(xlim=(-1100.0, 900.0), ylim=(-750.0, 1300.0), title="全局示意")
    style_axes(ax)


def local_panel(ax: plt.Axes, polygon: list[Point], diameter, center: Point, radius: float) -> None:
    ax.add_patch(Polygon([(p.x, p.y) for p in polygon], closed=True, facecolor="#AFCFE3",
                         edgecolor=MAIN_REGION_EDGE, linewidth=1.35, alpha=0.86, zorder=2))
    ax.plot([diameter.first.x, diameter.second.x], [diameter.first.y, diameter.second.y],
            color=DIAMETER_COLOR, linewidth=1.45, marker="o", markersize=3.5, zorder=4)
    ax.scatter([p.x for p in polygon], [p.y for p in polygon], s=13,
               color=MAIN_REGION_EDGE, zorder=5)
    ax.add_patch(Circle((center.x, center.y), radius, fill=False, color="#5E6872",
                        linestyle=(0, (3, 2)), linewidth=1.15, zorder=6))
    margin = radius * 1.35
    ax.set(xlim=(center.x - margin, center.x + margin), ylim=(center.y - margin, center.y + margin),
           title="局部放大")
    ax.text(center.x - margin * 0.82, center.y + margin * 0.86,
            rf"$D={diameter.distance:.2f}\,\mathrm{{m}}$", color=DIAMETER_COLOR, fontsize=9)
    style_axes(ax)


def legend_handles() -> list:
    return [Line2D([0], [0], marker="o", linestyle="none", markerfacecolor=STATION_COLOR,
                   markeredgecolor=STATION_COLOR, markersize=5, label="检测点"),
            Line2D([0], [0], color=CENTERLINE_COLOR, linewidth=1.2, label="示向中心线"),
            Line2D([0], [0], color=BOUNDARY_COLOR, linewidth=1.0, linestyle="--", label="±1°误差边界"),
            Patch(facecolor=MAIN_REGION_FACE, edgecolor=MAIN_REGION_EDGE, label="干扰源位置范围")]


def point_dict(point: Point) -> dict[str, float]:
    return {"x": point.x, "y": point.y}


def save_figure(fig: plt.Figure, path: Path, dpi: int = 360) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(path, dpi=dpi if path.suffix.lower() == ".png" else None, bbox_inches="tight")
    plt.close(fig)


def main() -> None:
    setup()
    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial", "DejaVu Sans"],
                         "axes.unicode_minus": False, "pdf.fonttype": 42, "svg.fonttype": "none",
                         "font.size": 9, "axes.labelsize": 10, "axes.titlesize": 12, "legend.fontsize": 8})
    fixed_observations = observations()
    polygon = locate_polygon(fixed_observations)
    region = clip_polygon_with_disk(polygon)
    diameter = clipped_region_diameter(region)
    center = Point(sum(p.x for p in polygon) / len(polygon), sum(p.y for p in polygon) / len(polygon))
    zoom_radius = 1.35 * max(math.hypot(p.x - center.x, p.y - center.y) for p in polygon)
    repo_root = Path(__file__).resolve().parents[2]
    original_dir = repo_root / "paper_assets" / "originals" / "section5" / "fig2_multi_station_intersection"
    final_dir = repo_root / "paper_assets" / "paper_figures" / "section5"

    fig, ax = plt.subplots(figsize=(6.0, 5.4))
    global_panel(ax, fixed_observations, polygon, center, zoom_radius)
    fig.legend(handles=legend_handles(), loc="lower center", ncol=4, frameon=True,
               bbox_to_anchor=(0.5, 0.01), fontsize=8)
    fig.tight_layout(rect=(0, 0.10, 1, 1))
    save_figure(fig, original_dir / "fig2_global_overview.png")
    fig, ax = plt.subplots(figsize=(5.4, 5.0))
    local_panel(ax, polygon, diameter, center, zoom_radius)
    fig.tight_layout()
    save_figure(fig, original_dir / "fig2_local_detail.png")

    fig, axes = plt.subplots(1, 2, figsize=(12.0, 5.5), gridspec_kw={"width_ratios": [1.0, 1.0]})
    global_panel(axes[0], fixed_observations, polygon, center, zoom_radius)
    local_panel(axes[1], polygon, diameter, center, zoom_radius)
    fig.legend(handles=legend_handles(), loc="lower center", ncol=4, frameon=True,
               bbox_to_anchor=(0.5, 0.015), fontsize=8)
    fig.subplots_adjust(wspace=0.16, bottom=0.14, left=0.055, right=0.985, top=0.91)
    fig.suptitle("多检测点示向交会定位区域", y=0.97, fontsize=13)
    for sign in (-1.0, 1.0):
        offset = zoom_radius * 0.72
        fig.add_artist(ConnectionPatch(
            xyA=(center.x + offset, center.y + sign * offset), coordsA=axes[0].transData,
            xyB=(center.x - offset, center.y + sign * offset), coordsB=axes[1].transData,
            color="#6B8798", linewidth=0.85, linestyle=(0, (3, 2)), alpha=0.88,
            arrowstyle="-", zorder=8,
        ))
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(final_dir / f"section5_fig2_multi_station_intersection.{suffix}",
                    dpi=360 if suffix == "png" else None, bbox_inches="tight")
    plt.close(fig)

    geometry = {"sensors": [point_dict(p) for p in SENSORS], "bearings_deg": MEASURED_BEARINGS_DEG,
                "error_deg": 1.0, "polygon_vertices": [point_dict(p) for p in polygon],
                "diameter": {"distance_m": diameter.distance, "first": point_dict(diameter.first), "second": point_dict(diameter.second)},
                "target_disk_radius_m": 1800.0, "target_disk_active": region.circle_active,
                "zoom_center": point_dict(center), "zoom_radius_m": zoom_radius}
    original_dir.mkdir(parents=True, exist_ok=True)
    (original_dir / "geometry.json").write_text(json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"vertex_count={len(polygon)}, D={diameter.distance:.10f} m, target_disk_active={region.circle_active}")


if __name__ == "__main__":
    main()
