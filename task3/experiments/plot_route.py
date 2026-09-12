"""Plot one robot route from a compressed Q3 offline-result file."""

from __future__ import annotations

import argparse
import gzip
import json
from pathlib import Path
from typing import Any, Iterable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Circle
import numpy as np

from task3.src.config import PhysicalConfig, PlannerConfig
from task3.src.coverage import seven_points


def parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("input", type=Path, help=".jsonl.gz file produced by run_offline.py")
    p.add_argument("--policy", help="select records with this policy ID")
    p.add_argument(
        "--first",
        type=int,
        default=1,
        help="plot the Nth matching record (1-based; default: 1)",
    )
    p.add_argument("--output", type=Path, required=True, help="output PNG path")
    return p


def load_record(path: Path, policy: str | None, first: int) -> dict[str, Any]:
    if first <= 0:
        raise ValueError("--first must be a positive, 1-based index")

    matches = 0
    try:
        with gzip.open(path, "rt", encoding="utf-8") as handle:
            for line_number, line in enumerate(handle, start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError as exc:
                    raise ValueError(f"invalid JSON on line {line_number}: {exc}") from exc
                if row.get("record_type") == "metadata":
                    continue
                if policy is not None and row.get("policy") != policy:
                    continue
                matches += 1
                if matches == first:
                    return row
    except (OSError, EOFError) as exc:
        raise ValueError(f"could not read gzip result file {path}: {exc}") from exc

    selection = f"policy {policy!r}" if policy is not None else "any policy"
    raise ValueError(f"no matching record #{first} for {selection} in {path}")


def _position(value: Any) -> tuple[float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        return None
    try:
        point = (float(value[0]), float(value[1]))
    except (TypeError, ValueError):
        return None
    return point if np.all(np.isfinite(point)) else None


def extract_route(actions: Iterable[dict[str, Any]]) -> np.ndarray:
    route = [(0.0, 0.0)]
    for action in actions:
        point = _position(action.get("position"))
        if point is not None and point != route[-1]:
            route.append(point)
    return np.asarray(route, dtype=float)


def successful_clear_points(actions: Iterable[dict[str, Any]]) -> np.ndarray:
    points = []
    for action in actions:
        if action.get("path") != "/clear":
            continue
        if action.get("response", {}).get("clear_result") != "success":
            continue
        point = _position(action.get("position"))
        if point is not None:
            points.append(point)
    return np.asarray(points, dtype=float).reshape((-1, 2))


def resolution_order(row: dict[str, Any]) -> dict[Any, int]:
    """Return channel -> successful-clear rank, independent of channel ID."""
    ranks: dict[Any, int] = {}
    actions = row.get("actions")
    if isinstance(actions, list):
        for action in actions:
            if action.get("path") != "/clear":
                continue
            if action.get("response", {}).get("clear_result") != "success":
                continue
            channel = action.get("channel")
            if channel not in ranks:
                ranks[channel] = len(ranks) + 1
    diagnostics = row.get("result", {}).get("diagnostics", [])
    if isinstance(diagnostics, list):
        for item in diagnostics:
            if item.get("type") != "dynamic_action" or item.get("action_kind") != "CLEAR":
                continue
            channel = item.get("channel")
            rank = item.get("resolution_order")
            if channel not in ranks and isinstance(rank, int):
                ranks[channel] = rank
    return ranks


def source_points(
    sources: Iterable[dict[str, Any]], ranks: dict[Any, int] | None = None
) -> tuple[np.ndarray, list[str]]:
    ranks = ranks or {}
    points: list[tuple[float, float]] = []
    labels: list[str] = []
    for source in sources:
        point = _position(source.get("position"))
        if point is not None:
            points.append(point)
            channel = source.get("channel", "?")
            labels.append(f"#{ranks[channel]}" if channel in ranks else f"ch{channel}")
    return np.asarray(points, dtype=float).reshape((-1, 2)), labels


def task_actions(diagnostics: Any) -> list[dict[str, Any]]:
    if not isinstance(diagnostics, list):
        return []
    return [
        item for item in diagnostics
        if item.get("type") in {"task_action", "dynamic_action"}
    ]


def plot_record(row: dict[str, Any], output: Path) -> None:
    actions = row.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError(
            "selected record has no actions; use a run_offline.py result generated without --no-actions"
        )

    route = extract_route(actions)
    clears = successful_clear_points(actions)
    sources, source_labels = source_points(row.get("sources", []), resolution_order(row))
    diagnostics = row.get("result", {}).get("diagnostics", [])
    semantic_actions = task_actions(diagnostics)

    physical = PhysicalConfig()
    planner_values = row.get("planner") if isinstance(row.get("planner"), dict) else {}
    ring_radius = float(planner_values.get("ring_radius_m", PlannerConfig().ring_radius_m))
    base_rotation = float(planner_values.get("rotation_deg", PlannerConfig().rotation_deg))
    coverage = seven_points(base_rotation, ring_radius)

    fig, ax = plt.subplots(figsize=(8, 8), constrained_layout=True)
    boundary = Circle(
        (0.0, 0.0),
        physical.target_radius_m,
        facecolor="#e8f1f8",
        edgecolor="#6f8797",
        linewidth=1.2,
        alpha=0.45,
        label="Search boundary (1800 m)",
        zorder=0,
    )
    ax.add_patch(boundary)
    if semantic_actions:
        for item in semantic_actions:
            start = _position(item.get("start"))
            end = _position(item.get("end"))
            if start is None or end is None or start == end:
                continue
            if item.get("guard"):
                color, style, width = "#7c3aed", "-.", 2.0
            elif item.get("reason") == "coverage_found_revisit":
                color, style, width = "#0f766e", ":", 1.8
            elif item.get("opportunistic"):
                color, style, width = "#d97706", ":", 1.8
            elif (
                item.get("active_task_type") == "ResolveSource"
                or str(item.get("reason", "")).startswith(
                    ("service_", "certified_", "conservative_")
                )
            ):
                color, style, width = "#c2415d", "-", 1.8
            else:
                color, style, width = "#1769aa", "--", 1.6
            ax.plot(
                [start[0], end[0]], [start[1], end[1]],
                color=color, linestyle=style, linewidth=width, zorder=2,
            )
        starts = [
            _position(item.get("task_start_position")) for item in diagnostics
            if item.get("type") == "task_started"
        ]
        starts.extend(
            _position(item.get("robot_position")) for item in diagnostics
            if item.get("type") == "dynamic_replan"
        )
        starts = [point for point in starts if point is not None]
        if starts:
            start_array = np.asarray(starts, float)
            ax.scatter(start_array[:, 0], start_array[:, 1], marker="D", s=22,
                       facecolors="white", edgecolors="#333333", linewidth=0.7,
                       zorder=5)
        for item in semantic_actions:
            if not item.get("opportunistic"):
                continue
            point = _position(item.get("end"))
            if point is None:
                continue
            if item.get("guard"):
                marker, color = "P", "#7c3aed"
            elif item.get("reason") == "coverage_found_revisit":
                marker, color = "s", "#0f766e"
            else:
                marker = "*" if item.get("action_kind") == "CLEAR" else "^"
                color = "#d97706"
            ax.scatter([point[0]], [point[1]], marker=marker, s=38,
                       color=color, zorder=6)
    else:
        ax.plot(route[:, 0], route[:, 1], color="#1769aa", linewidth=1.5,
                label="Robot route", zorder=2)
        ax.scatter(route[:, 0], route[:, 1], s=8, color="#1769aa", alpha=0.45, zorder=2)
    ax.scatter([0.0], [0.0], marker="s", s=70, color="#222222", label="Start", zorder=5)

    if len(sources):
        ax.scatter(
            sources[:, 0],
            sources[:, 1],
            marker="X",
            s=70,
            color="#d1495b",
            label="True source (resolution order)",
            zorder=4,
        )
        for point, label in zip(sources, source_labels):
            ax.annotate(
                label,
                xy=point,
                xytext=(5, 5),
                textcoords="offset points",
                fontsize=8,
                color="#8c2637",
            )

    if len(clears):
        ax.scatter(
            clears[:, 0],
            clears[:, 1],
            marker="P",
            s=55,
            facecolor="#2a9d55",
            edgecolor="white",
            linewidth=0.5,
            label="Successful clear",
            zorder=5,
        )

    ax.scatter(
        coverage[:, 0],
        coverage[:, 1],
        marker="o",
        s=50,
        facecolors="none",
        edgecolors="#8056a5",
        linewidth=1.1,
        alpha=0.65,
        label="Theoretical coverage skeleton",
        zorder=1,
    )

    if semantic_actions:
        milestone_items = [
            item for item in diagnostics
            if item.get("type") in {"coverage_unknown_scan", "coverage_completed"}
            and item.get("coverage_index", 0) > 0
        ]
        milestone_points = [
            _position(item.get("position")) for item in milestone_items
        ]
        milestone_points = [point for point in milestone_points if point is not None]
        if milestone_points:
            values = np.asarray(milestone_points, float)
            ax.scatter(values[:, 0], values[:, 1], marker="o", s=65,
                       facecolors="none", edgecolors="#8056a5", linewidth=1.5,
                       zorder=5)
            for item, point in zip(milestone_items, milestone_points):
                ax.annotate(f"V{item['coverage_index']}", point, xytext=(5, -12),
                            textcoords="offset points", fontsize=8, color="#603b82")
        selection = next(
            (
                item for item in diagnostics
                if item.get("type") in {"sweep_selected", "dynamic_sweep_selected"}
            ),
            {},
        )
        direction = selection.get("sweep_direction", "?")
        ax.text(0.02, 0.98, f"Sweep: {direction}", transform=ax.transAxes,
                ha="left", va="top", fontsize=9,
                bbox={"facecolor": "white", "edgecolor": "#777777", "alpha": 0.85})
        semantic_legend = [
            Line2D([0], [0], color="#c2415d", lw=1.8, label="Resolve source"),
            Line2D([0], [0], color="#1769aa", lw=1.6, ls="--", label="Advance coverage"),
            Line2D([0], [0], color="#d97706", lw=1.8, ls=":", label="Opportunistic movement"),
            Line2D([0], [0], marker="^", color="none", markerfacecolor="#d97706",
                   markeredgecolor="#d97706", label="Opportunistic measure"),
            Line2D([0], [0], marker="s", color="none", markerfacecolor="#0f766e",
                   markeredgecolor="#0f766e", label="Coverage revisit"),
            Line2D([0], [0], marker="P", color="none", markerfacecolor="#7c3aed",
                   markeredgecolor="#7c3aed", label="Guard measure"),
            Line2D([0], [0], marker="*", color="none", markerfacecolor="#d97706",
                   markeredgecolor="#d97706", label="Opportunistic clear"),
            Line2D([0], [0], marker="D", color="none", markerfacecolor="white",
                   markeredgecolor="#333333", label="Replan position"),
            Line2D([0], [0], color="#7c3aed", lw=2.0, ls="-.", label="Guard measurement"),
        ]
        handles, labels = ax.get_legend_handles_labels()
        ax.legend(handles + semantic_legend, labels + [item.get_label() for item in semantic_legend],
                  loc="upper right", fontsize=7)

    scenario = row.get("scenario_id", "unknown scenario")
    policy = row.get("policy", "unknown policy")
    ax.set_title(f"Q3 route: {scenario} | {policy}")
    ax.set_xlabel("x (m)")
    ax.set_ylabel("y (m)")
    ax.set_aspect("equal", adjustable="box")
    plotted_points = [route, sources, clears]
    max_coordinate = max(
        (float(np.max(np.abs(points))) for points in plotted_points if len(points)),
        default=0.0,
    )
    limit = max(physical.target_radius_m * 1.08, max_coordinate * 1.08)
    ax.set_xlim(-limit, limit)
    ax.set_ylim(-limit, limit)
    ax.grid(True, linewidth=0.5, alpha=0.3)
    if not semantic_actions:
        ax.legend(loc="upper right", fontsize=8)

    output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(output, dpi=180)
    plt.close(fig)


def main() -> None:
    args = parser().parse_args()
    try:
        record = load_record(args.input, args.policy, args.first)
        plot_record(record, args.output)
    except (FileNotFoundError, ValueError) as exc:
        raise SystemExit(f"error: {exc}") from exc
    print(args.output)


if __name__ == "__main__":
    main()
