from __future__ import annotations

import json
import math
from pathlib import Path

import matplotlib as mpl
mpl.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Polygon
import numpy as np

from common import Point, setup
from src.q1 import clip_polygon_with_disk, clipped_region_diameter, polygon_diameter


TARGET_RADIUS = 1000.0
# Counter-clockwise, outer end wider than inner end.  This construction is
# deliberately placed above the disk so a cropped view shows only its top arc.
TRAPEZOID = [
    Point(-650.0, 1200.0),  # A: unconstrained upper-left extreme
    Point(-400.0, 650.0),
    Point(600.0, 650.0),    # C: constrained lower-right extreme
    Point(650.0, 1250.0),
]


def point_dict(point: Point) -> dict[str, float]:
    return {"x": point.x, "y": point.y}


def main() -> None:
    setup()
    mpl.rcParams.update({"font.family": "sans-serif", "font.sans-serif": ["Microsoft YaHei", "SimHei", "Noto Sans CJK SC", "Arial", "DejaVu Sans"],
                         "axes.unicode_minus": False, "pdf.fonttype": 42, "svg.fonttype": "none"})
    region = clip_polygon_with_disk(TRAPEZOID, TARGET_RADIUS)
    unconstrained = polygon_diameter(TRAPEZOID)
    constrained = clipped_region_diameter(region)
    assert region.circle_active and region.arcs

    # The active endpoint is the disk/side intersection, not the unavailable A.
    arc_endpoint = constrained.first if abs(math.hypot(constrained.first.x, constrained.first.y) - TARGET_RADIUS) < 1e-6 else constrained.second
    attainable_vertex = constrained.second if arc_endpoint == constrained.first else constrained.first
    assert attainable_vertex == TRAPEZOID[2]

    repo_root = Path(__file__).resolve().parents[2]
    original_dir = repo_root / "paper_assets" / "originals" / "section5" / "fig3_active_target_disk_clipping"
    final_dir = repo_root / "paper_assets" / "paper_figures" / "section5"
    original_dir.mkdir(parents=True, exist_ok=True)
    final_dir.mkdir(parents=True, exist_ok=True)

    fig, ax = plt.subplots(figsize=(8.4, 4.5))
    theta = np.linspace(0.0, 2.0 * math.pi, 600)
    ax.plot(TARGET_RADIUS * np.cos(theta), TARGET_RADIUS * np.sin(theta), color="#697783", linewidth=1.8, label="目标圆域")
    ax.add_patch(Polygon([(p.x, p.y) for p in TRAPEZOID], closed=True, facecolor="#AFC6D8",
                         edgecolor="#527B9D", linewidth=1.6, linestyle="--", alpha=0.30,
                         label="未受圆约束的梯形区域"))

    grid_x = np.linspace(-850.0, 800.0, 700)
    grid_y = np.linspace(550.0, 1320.0, 500)
    xx, yy = np.meshgrid(grid_x, grid_y)
    mask = xx * xx + yy * yy <= TARGET_RADIUS ** 2
    for start, end in zip(TRAPEZOID, TRAPEZOID[1:] + TRAPEZOID[:1]):
        edge_x, edge_y = end.x - start.x, end.y - start.y
        mask &= edge_x * (yy - start.y) - edge_y * (xx - start.x) >= 0.0
    ax.contourf(xx, yy, mask.astype(float), levels=[0.5, 1.5], colors=["#4F8A70"], alpha=0.42)

    for segment in region.segments:
        ax.plot([segment.start.x, segment.end.x], [segment.start.y, segment.end.y], color="#4F8A70", linewidth=2.2)
    for arc in region.arcs:
        angles = np.linspace(arc.start_angle, arc.end_angle, 280)
        ax.plot(arc.radius * np.cos(angles), arc.radius * np.sin(angles), color="#4F8A70", linewidth=2.8, label="有效圆弧")

    ax.plot([unconstrained.first.x, unconstrained.second.x], [unconstrained.first.y, unconstrained.second.y],
            color="#8D9398", linewidth=1.35, linestyle=(0, (4, 3)), label="未受圆约束直径")
    ax.plot([arc_endpoint.x, attainable_vertex.x], [arc_endpoint.y, attainable_vertex.y],
            color="#9B4F55", linewidth=2.45, label=rf"受圆约束直径 $D={constrained.distance:.1f}$ m")
    ax.scatter([arc_endpoint.x], [arc_endpoint.y], s=32, color="#9B4F55", zorder=6)
    ax.annotate("圆弧与侧边交点 $P$", xy=(arc_endpoint.x, arc_endpoint.y), xytext=(-670.0, 1040.0),
                arrowprops={"arrowstyle": "->", "color": "#59646D"}, color="#46515B")
    midpoint = ((arc_endpoint.x + attainable_vertex.x) / 2.0, (arc_endpoint.y + attainable_vertex.y) / 2.0)
    ax.annotate(rf"受圆约束直径 $D={constrained.distance:.1f}$ m", xy=midpoint, xytext=(-90.0, 1060.0),
                arrowprops={"arrowstyle": "-", "color": "#9B4F55"}, color="#8B474D")
    ax.text(-705.0, 1120.0, "未受圆约束直径", color="#737C84", fontsize=9)
    ax.set(xlim=(-850.0, 800.0), ylim=(550.0, 1320.0))
    ax.set_aspect("equal")
    ax.set_axis_off()
    ax.legend(loc="lower right", frameon=True, fontsize=8)
    fig.tight_layout()
    for suffix in ("png", "pdf", "svg"):
        fig.savefig(final_dir / f"section5_fig3_active_target_disk_clipping.{suffix}", dpi=360 if suffix == "png" else None)
        fig.savefig(original_dir / f"fig3_parameterized_source.{suffix}", dpi=360 if suffix == "png" else None)
    plt.close(fig)

    geometry = {
        "target_radius_m": TARGET_RADIUS,
        "unclipped_trapezoid": [point_dict(p) for p in TRAPEZOID],
        "unconstrained_diameter": {"distance_m": unconstrained.distance, "first": point_dict(unconstrained.first), "second": point_dict(unconstrained.second)},
        "constrained_diameter": {"distance_m": constrained.distance, "first": point_dict(constrained.first), "second": point_dict(constrained.second)},
        "active_arc_endpoint": point_dict(arc_endpoint),
        "clipped_segments": [{"start": point_dict(s.start), "end": point_dict(s.end)} for s in region.segments],
        "clipped_arcs": [{"start_angle_rad": a.start_angle, "end_angle_rad": a.end_angle, "radius_m": a.radius, "full_circle": a.full_circle} for a in region.arcs],
        "circle_active": region.circle_active,
    }
    (original_dir / "geometry.json").write_text(json.dumps(geometry, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"unconstrained_D={unconstrained.distance:.6f} m, constrained_D={constrained.distance:.6f} m, arc_endpoint=({arc_endpoint.x:.6f}, {arc_endpoint.y:.6f}), arcs={len(region.arcs)}")


if __name__ == "__main__":
    main()
