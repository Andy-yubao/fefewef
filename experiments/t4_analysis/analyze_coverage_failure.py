from __future__ import annotations

import argparse
import json
import math
from pathlib import Path
from typing import Any

from task4.geometry import angle_delta_deg, distance
from task4.search_patterns import triangular_lattice


Point = tuple[float, float]


def _point(action: dict[str, Any]) -> Point:
    position = action["request"]["position"]
    return (float(position["x"]), float(position["y"]))


def _unique_points(points: list[Point], tolerance_m: float = 1e-6) -> list[Point]:
    unique: list[Point] = []
    for point in points:
        if all(distance(point, other) > tolerance_m for other in unique):
            unique.append(point)
    return unique


def _is_visible(emitter: dict[str, Any], point: Point) -> bool:
    source = (float(emitter["x"]), float(emitter["y"]))
    if distance(source, point) > float(emitter["receive_radius_m"]) + 1e-9:
        return False
    if not emitter["directional"]:
        return True
    from_source = math.degrees(
        math.atan2(point[1] - source[1], point[0] - source[0])
    ) % 360.0
    return abs(angle_delta_deg(from_source, float(emitter["direction_deg"]))) <= 90.0 + 1e-12


def analyze(payload: dict[str, Any], lattice_spacing: float) -> dict[str, Any]:
    truth = payload.get("local_truth") or payload.get("truth")
    if not truth:
        raise ValueError("input must contain post-run local_truth or truth")
    actions = payload.get("actions", [])
    measurement_points = _unique_points(
        [_point(action) for action in actions if action.get("path") == "/measure"]
    )
    original = triangular_lattice(spacing=lattice_spacing)
    skipped = [
        point
        for point in original
        if all(distance(point, measured) > 1e-6 for measured in measurement_points)
    ]
    missed = []
    for emitter in truth["emitters"]:
        if emitter["cleared"]:
            continue
        source = (float(emitter["x"]), float(emitter["y"]))
        nearest_measurements = sorted(
            (
                {
                    "point": [point[0], point[1]],
                    "distance_m": distance(source, point),
                    "visible": _is_visible(emitter, point),
                }
                for point in measurement_points
            ),
            key=lambda item: item["distance_m"],
        )
        nearest_skipped = sorted(
            (
                {
                    "point": [point[0], point[1]],
                    "distance_m": distance(source, point),
                    "visible": _is_visible(emitter, point),
                }
                for point in skipped
            ),
            key=lambda item: item["distance_m"],
        )
        channel_actions = [
            action
            for action in actions
            if action.get("path") == "/measure"
            and int(action["request"]["channel"]) == int(emitter["channel"])
        ]
        missed.append(
            {
                "channel": emitter["channel"],
                "position": [source[0], source[1]],
                "receive_radius_m": emitter["receive_radius_m"],
                "directional": emitter["directional"],
                "direction_deg": emitter["direction_deg"],
                "channel_measurement_count": len(channel_actions),
                "visible_measurement_points": sum(
                    _is_visible(emitter, _point(action)) for action in channel_actions
                ),
                "nearest_measurement_points": nearest_measurements[:6],
                "nearest_skipped_lattice_points": nearest_skipped[:6],
            }
        )
    return {
        "seed": truth["seed"],
        "lattice_spacing_m": lattice_spacing,
        "measurement_position_count": len(measurement_points),
        "original_lattice_point_count": len(original),
        "skipped_lattice_point_count": len(skipped),
        "skipped_lattice_points": [[point[0], point[1]] for point in skipped],
        "missed_emitters": missed,
    }


def _markdown(report: dict[str, Any]) -> str:
    lines = [
        f"# Coverage failure diagnosis: seed {report['seed']}",
        "",
        "This is post-run local-truth analysis. It is not available to a live strategy.",
        "",
        f"- Measurement positions: `{report['measurement_position_count']}`",
        f"- Original lattice points: `{report['original_lattice_point_count']}`",
        f"- Skipped lattice points: `{report['skipped_lattice_point_count']}`",
    ]
    for emitter in report["missed_emitters"]:
        lines.extend(
            [
                "",
                f"## Missed channel {emitter['channel']}",
                "",
                f"- Directional: `{emitter['directional']}`",
                f"- Receive radius: `{emitter['receive_radius_m']:.3f} m`",
                f"- Measurements on channel: `{emitter['channel_measurement_count']}`",
                f"- Actually visible measurement positions: `{emitter['visible_measurement_points']}`",
                "- Nearest measured distances: `"
                + ", ".join(
                    f"{item['distance_m']:.2f} ({'visible' if item['visible'] else 'hidden'})"
                    for item in emitter["nearest_measurement_points"]
                )
                + "`",
                "- Nearest skipped-lattice distances: `"
                + ", ".join(
                    f"{item['distance_m']:.2f} ({'visible' if item['visible'] else 'hidden'})"
                    for item in emitter["nearest_skipped_lattice_points"]
                )
                + "`",
            ]
        )
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Diagnose missed emitters from completed local T4 action logs"
    )
    parser.add_argument("inputs", nargs="+", type=Path)
    parser.add_argument("--lattice-spacing", type=float, default=735.0)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=True)
    for path in args.inputs:
        report = analyze(json.loads(path.read_text(encoding="utf-8")), args.lattice_spacing)
        stem = path.stem + "-coverage-failure"
        (args.output_dir / f"{stem}.json").write_text(
            json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8"
        )
        (args.output_dir / f"{stem}.md").write_text(_markdown(report), encoding="utf-8")
        print(json.dumps(report, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
