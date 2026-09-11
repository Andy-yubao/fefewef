from __future__ import annotations

import math

from .geometry import Point


def triangular_lattice(
    arena_radius: float = 1800.0,
    spacing: float = 900.0,
    offset: Point = (0.0, 0.0),
    rotation_deg: float = 0.0,
) -> list[Point]:
    """Vertices of every triangular cell that can intersect the target disk.

    Any point inside a triangular cell is within ``spacing`` of every cell vertex.
    Every half-plane through that point contains at least one of the three vertices.
    Keeping nodes through ``arena_radius + spacing`` therefore preserves the
    ideal-model directional discovery guarantee when spacing is below 1000 m.
    """
    if spacing <= 0:
        raise ValueError("spacing must be positive")
    row_height = spacing * math.sqrt(3.0) / 2.0
    outer_radius = arena_radius + spacing
    min_row = math.floor(-outer_radius / row_height) - 2
    max_row = math.ceil(outer_radius / row_height) + 2
    points: list[Point] = []
    rotation = math.radians(rotation_deg)
    for row in range(min_row, max_row + 1):
        y = row * row_height
        row_offset = (row & 1) * spacing / 2.0
        min_column = math.floor((-outer_radius - offset[0] - row_offset) / spacing) - 2
        max_column = math.ceil((outer_radius - offset[0] - row_offset) / spacing) + 2
        for column in range(min_column, max_column + 1):
            x = column * spacing + row_offset + offset[0]
            y_shifted = y + offset[1]
            if math.hypot(x, y_shifted) <= outer_radius + 1e-9:
                points.append(
                    (
                        x * math.cos(rotation) - y_shifted * math.sin(rotation),
                        x * math.sin(rotation) + y_shifted * math.cos(rotation),
                    )
                )
    return points


def open_path_two_opt(points: list[Point], start: Point = (0.0, 0.0)) -> list[Point]:
    """Deterministic nearest-neighbor path followed by open-path 2-opt.

    The start is fixed and the terminal point is free.  This is intentionally small
    and dependency-free; T4 has only a few dozen coverage vertices.
    """
    remaining = list(points)
    route: list[Point] = []
    position = start
    while remaining:
        point = min(remaining, key=lambda candidate: math.dist(position, candidate))
        remaining.remove(point)
        route.append(point)
        position = point

    while True:
        improved = False
        for first in range(len(route) - 1):
            before = start if first == 0 else route[first - 1]
            for last in range(first + 1, len(route)):
                old = math.dist(before, route[first])
                new = math.dist(before, route[last])
                if last + 1 < len(route):
                    old += math.dist(route[last], route[last + 1])
                    new += math.dist(route[first], route[last + 1])
                if new + 1e-9 < old:
                    route[first : last + 1] = reversed(route[first : last + 1])
                    improved = True
                    break
            if improved:
                break
        if not improved:
            return route
