"""Render local T4 action logs as dependency-free SVG path maps.

This is offline-only analysis code. It reads persisted action logs after a run and
never participates in strategy decisions. Local truth is shown only when it is
already present in the saved artifact.
"""

from __future__ import annotations

import argparse
import csv
from html import escape
import json
import math
from pathlib import Path
from typing import Any


def _position(action: dict[str, Any]) -> tuple[float, float] | None:
    value = action.get("request", {}).get("position")
    if not isinstance(value, dict):
        return None
    return float(value["x"]), float(value["y"])


def _same(a: tuple[float, float], b: tuple[float, float]) -> bool:
    return abs(a[0] - b[0]) < 1e-8 and abs(a[1] - b[1]) < 1e-8


def summarize(payload: dict[str, Any]) -> dict[str, Any]:
    actions = payload["actions"]
    route: list[tuple[float, float]] = [(0.0, 0.0)]
    measurements: dict[tuple[float, float], dict[str, int]] = {}
    clears = []
    result_counts = {"no_signal": 0, "direction": 0, "near": 0}
    for action_index, action in enumerate(actions, start=1):
        point = _position(action)
        if point is not None and not _same(route[-1], point):
            route.append(point)
        if action.get("path") == "/measure" and point is not None:
            result = action.get("response", {}).get("measure_result")
            if result in result_counts:
                result_counts[result] += 1
            bucket = measurements.setdefault(point, {"no_signal": 0, "direction": 0, "near": 0})
            if result in bucket:
                bucket[result] += 1
        elif action.get("path") == "/clear" and point is not None:
            clears.append(
                {
                    "point": point,
                    "channel": int(action["request"]["channel"]),
                    "success": action.get("response", {}).get("clear_result") == "success",
                    "action_index": action_index,
                }
            )

    truth = payload.get("local_truth", {})
    stats = truth.get("stats", {})
    strategy_result = payload.get("strategy_result", {})
    successful_clears = sum(clear["success"] for clear in clears)
    movement_distance = sum(
        math.hypot(second[0] - first[0], second[1] - first[1])
        for first, second in zip(route, route[1:])
    )
    response_times = [
        action.get("response", {}).get("virtual_time_s") for action in actions
    ]
    response_times = [value for value in response_times if value is not None]
    successful_clear_times = [
        action.get("response", {}).get("virtual_time_s")
        for action in actions
        if action.get("path") == "/clear"
        and action.get("response", {}).get("clear_result") == "success"
    ]
    return {
        "seed": truth.get("seed"),
        "strategy": strategy_result.get("strategy"),
        "route": route,
        "measurements": measurements,
        "clears": clears,
        "emitters": truth.get("emitters", []),
        "emitter_count": truth.get("emitter_count"),
        "directional_count": truth.get("directional_count"),
        "cleared_count": truth.get("cleared_count", successful_clears),
        "all_cleared": truth.get("all_cleared"),
        "virtual_time_s": truth.get(
            "virtual_time_s",
            strategy_result.get(
                "final_virtual_time_s", max(response_times, default=0.0)
            ),
        ),
        "movement_distance_m": stats.get("movement_distance_m", movement_distance),
        "measure_count": stats.get("measure_count", sum(result_counts.values())),
        "no_signal_count": stats.get("no_signal_count", result_counts["no_signal"]),
        "direction_count": stats.get("direction_count", result_counts["direction"]),
        "near_count": stats.get("near_count", result_counts["near"]),
        "first_clear_time_s": truth.get(
            "first_clear_time_s", min(successful_clear_times, default=None)
        ),
        "distinct_measure_positions": len(measurements),
    }


def render_svg(summary: dict[str, Any], path: Path) -> None:
    width = height = 900
    margin = 72
    points = list(summary["route"])
    points.extend((float(e["x"]), float(e["y"])) for e in summary["emitters"])
    extent = max([2100.0] + [abs(value) for point in points for value in point]) + 180.0
    scale = (width - 2 * margin) / (2 * extent)

    def screen(point: tuple[float, float]) -> tuple[float, float]:
        return width / 2 + point[0] * scale, height / 2 - point[1] * scale

    def circle(point, radius, fill, stroke="none", stroke_width=1, opacity=1.0):
        x, y = screen(point)
        return (
            f'<circle cx="{x:.2f}" cy="{y:.2f}" r="{radius:.2f}" fill="{fill}" '
            f'stroke="{stroke}" stroke-width="{stroke_width}" opacity="{opacity}"/>'
        )

    case_label = (
        f'Seed {summary["seed"]}' if summary["seed"] is not None else "Official log"
    )
    clear_label = (
        f'{summary["cleared_count"]}/{summary["emitter_count"]} cleared'
        if summary["emitter_count"] is not None
        else f'{summary["cleared_count"]} successful clears; total unknown'
    )
    title = (
        f'{case_label} | {summary["strategy"]} | {clear_label} | '
        f'{summary["virtual_time_s"]:.1f} s'
    )
    svg = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{width}" height="{height}" viewBox="0 0 {width} {height}">',
        '<rect width="100%" height="100%" fill="#fbfcfe"/>',
        f'<text x="{width/2}" y="29" text-anchor="middle" font-family="sans-serif" font-size="18" font-weight="600">{escape(title)}</text>',
    ]

    center = screen((0.0, 0.0))
    svg.append(
        f'<circle cx="{center[0]:.2f}" cy="{center[1]:.2f}" r="{1800*scale:.2f}" fill="#eef4ff" stroke="#6b7280" stroke-width="1.5" stroke-dasharray="6 5"/>'
    )
    # Axes and coarse 600 m grid aid distance reading.
    for coordinate in range(-1800, 1801, 600):
        x1, y1 = screen((coordinate, -1800))
        x2, y2 = screen((coordinate, 1800))
        svg.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#dce3ec" stroke-width="0.7"/>')
        x1, y1 = screen((-1800, coordinate))
        x2, y2 = screen((1800, coordinate))
        svg.append(f'<line x1="{x1:.2f}" y1="{y1:.2f}" x2="{x2:.2f}" y2="{y2:.2f}" stroke="#dce3ec" stroke-width="0.7"/>')

    route_data = " ".join(f"{screen(point)[0]:.2f},{screen(point)[1]:.2f}" for point in summary["route"])
    svg.append(f'<polyline points="{route_data}" fill="none" stroke="#2563eb" stroke-width="2.0" stroke-linejoin="round" stroke-linecap="round" opacity="0.72"/>')

    # Measurement sites with at least one positive observation are highlighted.
    for point, counts in summary["measurements"].items():
        positive = counts["direction"] + counts["near"]
        if positive:
            svg.append(circle(point, 4.4, "#f59e0b", "#7c2d12", 0.8, 0.95))
        else:
            svg.append(circle(point, 2.8, "#94a3b8", "#ffffff", 0.5, 0.75))

    # Local hidden truth is display-only and never fed back to the strategy.
    for emitter in summary["emitters"]:
        point = (float(emitter["x"]), float(emitter["y"]))
        x, y = screen(point)
        channel = int(emitter["channel"])
        if emitter["directional"]:
            angle = math.radians(float(emitter["direction_deg"]))
            tip = screen((point[0] + 170 * math.cos(angle), point[1] + 170 * math.sin(angle)))
            svg.append(f'<line x1="{x:.2f}" y1="{y:.2f}" x2="{tip[0]:.2f}" y2="{tip[1]:.2f}" stroke="#dc2626" stroke-width="2.2"/>')
            svg.append(f'<polygon points="{x:.2f},{y-6:.2f} {x-5.5:.2f},{y+5:.2f} {x+5.5:.2f},{y+5:.2f}" fill="#dc2626" stroke="#7f1d1d" stroke-width="0.8"/>')
        else:
            svg.append(circle(point, 5.5, "#7c3aed", "#4c1d95", 1.0, 0.95))
        svg.append(f'<text x="{x+7:.2f}" y="{y-7:.2f}" font-family="sans-serif" font-size="10" fill="#111827">{channel}</text>')

    for order, clear in enumerate(summary["clears"], start=1):
        x, y = screen(clear["point"])
        color = "#059669" if clear["success"] else "#dc2626"
        svg.extend(
            [
                f'<line x1="{x-5:.2f}" y1="{y-5:.2f}" x2="{x+5:.2f}" y2="{y+5:.2f}" stroke="{color}" stroke-width="2.4"/>',
                f'<line x1="{x-5:.2f}" y1="{y+5:.2f}" x2="{x+5:.2f}" y2="{y-5:.2f}" stroke="{color}" stroke-width="2.4"/>',
                f'<text x="{x+7:.2f}" y="{y+12:.2f}" font-family="sans-serif" font-size="9" fill="#065f46">C{order}:{clear["channel"]}</text>',
            ]
        )

    sx, sy = screen(summary["route"][0])
    ex, ey = screen(summary["route"][-1])
    svg.append(circle(summary["route"][0], 6.0, "#16a34a", "#14532d", 1.2))
    svg.append(f'<text x="{sx+8:.2f}" y="{sy+16:.2f}" font-family="sans-serif" font-size="10">START</text>')
    svg.append(f'<rect x="{ex-5:.2f}" y="{ey-5:.2f}" width="10" height="10" fill="#111827"/>')
    svg.append(f'<text x="{ex+8:.2f}" y="{ey-8:.2f}" font-family="sans-serif" font-size="10">END</text>')

    legend = [
        ("#2563eb", "route"),
        ("#94a3b8", "no-signal-only measurement site"),
        ("#f59e0b", "site with >=1 signal"),
        ("#059669", "successful clear; Corder:channel"),
    ]
    if summary["emitters"]:
        legend.extend(
            [
                ("#7c3aed", "omnidirectional source (local truth)"),
                ("#dc2626", "directional source + emission direction"),
            ]
        )
    lx, ly = 78, height - 122
    svg.append(f'<rect x="{lx-12}" y="{ly-20}" width="320" height="115" rx="6" fill="#ffffff" stroke="#cbd5e1" opacity="0.94"/>')
    for index, (color, label) in enumerate(legend):
        y = ly + index * 17
        svg.append(f'<circle cx="{lx}" cy="{y}" r="4" fill="{color}"/>')
        svg.append(f'<text x="{lx+11}" y="{y+4}" font-family="sans-serif" font-size="11" fill="#1f2937">{escape(label)}</text>')

    footer = (
        f'{summary["measure_count"]} measurements at {summary["distinct_measure_positions"]} sites; '
        f'{summary["no_signal_count"]} no-signal; {summary["direction_count"] + summary["near_count"]} signal; '
        f'{summary["movement_distance_m"]:.0f} m movement'
    )
    svg.append(f'<text x="{width/2}" y="{height-16}" text-anchor="middle" font-family="sans-serif" font-size="12" fill="#374151">{escape(footer)}</text>')
    svg.append("</svg>")
    path.write_text("\n".join(svg), encoding="utf-8")


def main() -> None:
    parser = argparse.ArgumentParser(description="Plot saved local T4 action logs as SVG")
    parser.add_argument("logs", nargs="+", type=Path)
    parser.add_argument("--output-dir", required=True, type=Path)
    parser.add_argument("--selection-seed", type=int)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)

    summaries = []
    for source in args.logs:
        payload = json.loads(source.read_text(encoding="utf-8"))
        summary = summarize(payload)
        label = f'seed_{summary["seed"]}' if summary["seed"] is not None else source.stem
        output = args.output_dir / f"{label}_path.svg"
        render_svg(summary, output)
        summary["source_log"] = str(source)
        summary["figure"] = output.name
        summaries.append(summary)

    fields = [
        "seed", "strategy", "emitter_count", "directional_count", "cleared_count",
        "all_cleared", "virtual_time_s", "movement_distance_m", "measure_count",
        "no_signal_count", "direction_count", "near_count", "first_clear_time_s",
        "distinct_measure_positions", "source_log", "figure",
    ]
    with (args.output_dir / "summary.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: item.get(field) for field in fields} for item in summaries)

    manifest = {
        "selection_seed": args.selection_seed,
        "case_seeds": [item["seed"] for item in summaries],
        "strategy": summaries[0]["strategy"] if summaries else None,
        "figures": [item["figure"] for item in summaries],
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    lines = ["# T4 路径图", ""]
    if args.selection_seed is not None:
        lines.append(f"案例由固定随机选择种子 `{args.selection_seed}` 抽取，便于复现。")
        lines.append("")
    for item in summaries:
        case_label = (
            f'Seed {item["seed"]}' if item["seed"] is not None else "在线日志"
        )
        clear_text = (
            f'{item["cleared_count"]}/{item["emitter_count"]}'
            if item["emitter_count"] is not None
            else f'{item["cleared_count"]} 次成功（总数未知）'
        )
        lines.extend([f"## {case_label}", ""])
        if item["emitter_count"] is not None:
            lines.append(
                f'- 干扰源：{item["emitter_count"]}（定向 {item["directional_count"]}）'
            )
        lines.extend(
            [
                f"- 清除：{clear_text}",
                f'- 总虚拟时间：{item["virtual_time_s"]:.2f} s',
                f'- 移动距离：{item["movement_distance_m"]:.2f} m',
                f'- 测量：{item["measure_count"]}，无信号：{item["no_signal_count"]}，不同测量位置：{item["distinct_measure_positions"]}',
                f'- 首次清除：{item["first_clear_time_s"]:.2f} s',
                "",
                f'![{case_label} path]({item["figure"]})',
                "",
            ]
        )
    (args.output_dir / "README.md").write_text("\n".join(lines), encoding="utf-8")


if __name__ == "__main__":
    main()
