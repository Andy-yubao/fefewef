from __future__ import annotations

import math

from .geometry import Point


def double_ring_cover(
    arena_radius: float = 1800.0,
    inner_radius: float = 980.0,
    boundary_margin: float = 0.25,
    minimum_receive_radius: float = 1000.0,
) -> list[Point]:
    """A 25-point triangulation with a directional discovery certificate.

    The outer regular dodecagon contains the arena disk.  Twelve inner-ring
    vertices, rotated by 15 degrees, and the origin triangulate that polygon.
    Every triangulation edge is shorter than ``minimum_receive_radius``; hence
    every emitter is within range of all vertices of one containing triangle,
    and every closed half-plane through it contains at least one such vertex.
    """
    if arena_radius <= 0:
        raise ValueError("arena_radius must be positive")
    if inner_radius <= 0:
        raise ValueError("inner_radius must be positive")
    if boundary_margin < 0:
        raise ValueError("boundary_margin must be nonnegative")
    if minimum_receive_radius <= 0:
        raise ValueError("minimum_receive_radius must be positive")

    half_step = math.pi / 12.0
    step = math.pi / 6.0
    outer_radius = arena_radius / math.cos(half_step) + boundary_margin
    edge_lengths = (
        inner_radius,
        2.0 * inner_radius * math.sin(half_step),
        2.0 * outer_radius * math.sin(half_step),
        math.sqrt(
            outer_radius**2
            + inner_radius**2
            - 2.0 * outer_radius * inner_radius * math.cos(half_step)
        ),
    )
    if max(edge_lengths) >= minimum_receive_radius:
        raise ValueError(
            "double-ring triangulation edges must be shorter than the minimum receive radius"
        )

    inner = [
        (
            inner_radius * math.cos(half_step + index * step),
            inner_radius * math.sin(half_step + index * step),
        )
        for index in range(12)
    ]
    outer = [
        (
            outer_radius * math.cos(index * step),
            outer_radius * math.sin(index * step),
        )
        for index in range(12)
    ]
    return [(0.0, 0.0), *inner, *outer]


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
