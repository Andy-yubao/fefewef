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


def source_points(sources: Iterable[dict[str, Any]]) -> tuple[np.ndarray, list[Any]]:
    points: list[tuple[float, float]] = []
    channels: list[Any] = []
    for source in sources:
        point = _position(source.get("position"))
        if point is not None:
            points.append(point)
            channels.append(source.get("channel", "?"))
    return np.asarray(points, dtype=float).reshape((-1, 2)), channels


def plot_record(row: dict[str, Any], output: Path) -> None:
    actions = row.get("actions")
    if not isinstance(actions, list) or not actions:
        raise ValueError(
            "selected record has no actions; use a run_offline.py result generated without --no-actions"
        )

    route = extract_route(actions)
    clears = successful_clear_points(actions)
    sources, channels = source_points(row.get("sources", []))

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
    ax.plot(route[:, 0], route[:, 1], color="#1769aa", linewidth=1.5, label="Robot route", zorder=2)
    ax.scatter(route[:, 0], route[:, 1], s=8, color="#1769aa", alpha=0.45, zorder=2)
    ax.scatter([0.0], [0.0], marker="s", s=70, color="#222222", label="Start", zorder=5)

    if len(sources):
        ax.scatter(
            sources[:, 0],
            sources[:, 1],
            marker="X",
            s=70,
            color="#d1495b",
            label="True source",
            zorder=4,
        )
        for point, channel in zip(sources, channels):
            ax.annotate(
                str(channel),
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
