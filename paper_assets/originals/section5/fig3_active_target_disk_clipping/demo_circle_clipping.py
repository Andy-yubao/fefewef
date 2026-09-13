from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Circle, Polygon
import numpy as np

from common import Point, setup
from src.q1 import BearingObservation, clip_polygon_with_disk, clipped_region_diameter


TARGET_RADIUS = 1800.0
SENSOR = Point(800.0, 0.0)
THETA_DEG = 0.0
ERROR_DEG = 1.0
R_NEAR = 300.0
R_FAR = 1400.0


def parameterized_wedge() -> tuple[list[Point], Point, Point, Point, Point]:
    theta = math.radians(THETA_DEG)
    error = math.radians(ERROR_DEG)
    lower = Point(math.cos(theta - error), math.sin(theta - error))
    upper = Point(math.cos(theta + error), math.sin(theta + error))
    near_lower = SENSOR + lower * R_NEAR
    far_lower = SENSOR + lower * R_FAR
    far_upper = SENSOR + upper * R_FAR
    near_upper = SENSOR + upper * R_NEAR
    return [near_lower, far_lower, far_upper, near_upper], near_lower, near_upper, far_lower, far_upper


def point_dict(point: Point) -> dict[str, float]:
    return {"x": point.x, "y": point.y}


def main() -> None:
    setup()
    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial", "DejaVu Sans"],
                         "axes.unicode_minus": False, "pdf.fonttype": 42, "svg.fonttype": "none"})
    polygon, near_lower, near_upper, far_lower, far_upper = parameterized_wedge()
    region = clip_polygon_with_disk(polygon, TARGET_RADIUS)
    result = clipped_region_diameter(region)
    near_width = math.hypot(near_upper.x - near_lower.x, near_upper.y - near_lower.y)
    far_width = math.hypot(far_upper.x - far_lower.x, far_upper.y - far_lower.y)
    assert far_width > near_width

    repo_root = Path(__file__).resolve().parents[2]
    original_dir = repo_root / "paper_assets" / "originals" / "section5" / "fig3_active_target_disk_clipping"
    final_dir = repo_root / "paper_assets" / "paper_figures" / "section5"
    original_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8.6, 4.8))
    theta = np.linspace(0.0, 2.0 * math.pi, 500)
    ax.plot(TARGET_RADIUS * np.cos(theta), TARGET_RADIUS * np.sin(theta), color="#697783", linewidth=1.5, label="目标圆域")
    ax.add_patch(Polygon([(p.x, p.y) for p in polygon], closed=True, facecolor="#AFC6D8",
                         edgecolor="#527B9D", linewidth=1.5, linestyle="--", alpha=0.28,
                         label="参数化未裁剪扇形"))
    grid = np.linspace(-200.0, 2300.0, 500)
    xx, yy = np.meshgrid(grid, grid)
    mask = xx * xx + yy * yy <= TARGET_RADIUS ** 2
    constraints = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        edge_x, edge_y = end.x - start.x, end.y - start.y
        constraints.append(edge_x * (yy - start.y) - edge_y * (xx - start.x) >= 0.0)
    for constraint in constraints:
        mask &= constraint
    ax.contourf(xx, yy, mask.astype(float), levels=[0.5, 1.5], colors=["#4F8A70"], alpha=0.38)
    for segment in region.segments:
        ax.plot([segment.start.x, segment.end.x], [segment.start.y, segment.end.y], color="#4F8A70", linewidth=2.0)
    for arc in region.arcs:
        angles = np.linspace(arc.start_angle, arc.end_angle, 260)
        ax.plot(arc.radius * np.cos(angles), arc.radius * np.sin(angles), color="#4F8A70", linewidth=2.0)
    ax.plot([near_lower.x, near_upper.x], [near_lower.y, near_upper.y], color="#A75D5D", linewidth=1.7, marker="o", markersize=3.5, label=rf"近端宽度 $w_n={near_width:.1f}$ m")
    ax.plot([far_lower.x, far_upper.x], [far_lower.y, far_upper.y], color="#C27B3A", linewidth=1.7, marker="o", markersize=3.5, label=rf"远端宽度 $w_f={far_width:.1f}$ m")
    ax.plot([result.first.x, result.second.x], [result.first.y, result.second.y], color="#7E3F45", linewidth=2.1,
            marker="o", markersize=4, label=rf"直径 $D={result.distance:.1f}$ m")
    ax.scatter([SENSOR.x], [SENSOR.y], color="#263B4D", s=38, zorder=6, label="检测点 S")
    ax.annotate("有效圆弧", xy=(math.cos(0.28) * TARGET_RADIUS, math.sin(0.28) * TARGET_RADIUS),
                xytext=(1200.0, 1450.0), arrowprops={"arrowstyle": "->", "color": "#5E6872"})
    ax.set(xlabel="x / m", ylabel="y / m", xlim=(-250.0, 2350.0), ylim=(-900.0, 950.0))
    ax.set_aspect("equal")
    ax.grid(alpha=0.14)
    ax.legend(loc="upper left", frameon=False, fontsize=8)
    fig.tight_layout()
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(final_dir / f"section5_fig3_active_target_disk_clipping.{suffix}", dpi=360 if suffix == "png" else None)
        fig.savefig(original_dir / f"fig3_parameterized_source.{suffix}", dpi=360 if suffix == "png" else None)
    plt.close(fig)

    geometry = {
        "sensor": point_dict(SENSOR), "theta_deg": THETA_DEG, "error_deg": ERROR_DEG,
        "r_near_m": R_NEAR, "r_far_m": R_FAR, "target_radius_m": TARGET_RADIUS,
        "unclipped_polygon": [point_dict(p) for p in polygon],
        "near_width_m": near_width, "far_width_m": far_width,
        "clipped_segments": [{"start": point_dict(s.start), "end": point_dict(s.end)} for s in region.segments],
        "clipped_arcs": [{"start_angle_rad": a.start_angle, "end_angle_rad": a.end_angle, "radius_m": a.radius, "full_circle": a.full_circle} for a in region.arcs],
        "diameter": {"distance_m": result.distance, "first": point_dict(result.first), "second": point_dict(result.second)},
        "circle_active": region.circle_active,
    }
    (original_dir / "geometry.json").write_text(json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"near_width={near_width:.6f} m, far_width={far_width:.6f} m, far_wider={far_width > near_width}, circle_active={region.circle_active}, arcs={len(region.arcs)}")


if __name__ == "__main__":
    main()
