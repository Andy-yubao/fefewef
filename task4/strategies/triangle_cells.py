from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Sequence, TypeVar

from task4.geometry import Point, distance


TRIANGLE_SPACING_M = 900.0

_AXIAL_POINTS: tuple[tuple[int, int], ...] = (
    (0, 0),
    (1, 0),
    (0, 1),
    (-1, 1),
    (-1, 0),
    (0, -1),
    (1, -1),
    (2, -1),
    (2, 0),
    (1, 1),
    (0, 2),
    (-1, 2),
    (-2, 2),
    (-2, 1),
    (-2, 0),
    (-1, -1),
    (0, -2),
    (1, -2),
    (2, -2),
)

CELL_VERTEX_IDS: tuple[tuple[int, int, int], ...] = (
    (1, 2, 3),
    (1, 2, 7),
    (1, 3, 4),
    (1, 4, 5),
    (1, 5, 6),
    (1, 6, 7),
    (2, 3, 10),
    (2, 7, 8),
    (2, 8, 9),
    (2, 9, 10),
    (3, 4, 12),
    (3, 10, 11),
    (3, 11, 12),
    (4, 5, 14),
    (4, 12, 13),
    (4, 13, 14),
    (5, 6, 16),
    (5, 14, 15),
    (5, 15, 16),
    (6, 7, 18),
    (6, 16, 17),
    (6, 17, 18),
    (7, 8, 19),
    (7, 18, 19),
)


def main_points(spacing: float = TRIANGLE_SPACING_M) -> tuple[Point, ...]:
    """Return the immutable P1..P19 axial-lattice search skeleton."""
    height = spacing * math.sqrt(3.0) / 2.0
    return tuple((spacing * q + spacing * r / 2.0, height * r) for q, r in _AXIAL_POINTS)


def _signed_area2(poly: Sequence[Point]) -> float:
    return sum(
        a[0] * b[1] - b[0] * a[1]
        for a, b in zip(poly, tuple(poly[1:]) + (poly[0],))
    )


@dataclass(frozen=True)
class TriangleCell:
    cell_id: int
    vertex_ids: tuple[int, int, int]
    polygon: tuple[Point, Point, Point]
    closed_at: int


def triangle_cells(spacing: float = TRIANGLE_SPACING_M) -> tuple[TriangleCell, ...]:
    points = main_points(spacing)
    cells: list[TriangleCell] = []
    for cell_id, vertex_ids in enumerate(CELL_VERTEX_IDS, start=1):
        polygon = tuple(points[index - 1] for index in vertex_ids)
        if _signed_area2(polygon) < 0:
            polygon = (polygon[0], polygon[2], polygon[1])
        cells.append(TriangleCell(cell_id, vertex_ids, polygon, max(vertex_ids)))
    return tuple(cells)


def cells_closed_at(point_id: int, spacing: float = TRIANGLE_SPACING_M) -> tuple[TriangleCell, ...]:
    return tuple(cell for cell in triangle_cells(spacing) if cell.closed_at == point_id)


T = TypeVar("T")


def fixed_start_end_route(
    tasks: Sequence[T],
    start: Point,
    end: Point,
    *,
    point=lambda task: task.point,
    tie_key=lambda task: repr(task),
) -> list[T]:
    """Exact shortest Hamiltonian path with fixed start and fixed end.

    The returned list contains only the intermediate tasks.  Held--Karp states keep
    the lexicographically smallest route on equal-length ties, making rolling plans
    reproducible.
    """
    items = list(tasks)
    count = len(items)
    if count == 0:
        return []
    coords = [point(item) for item in items]
    keys = [tie_key(item) for item in items]
    # (visited mask, last index) -> (length, route indices, route tie keys)
    dp: dict[tuple[int, int], tuple[float, tuple[int, ...], tuple[object, ...]]] = {}
    for index in range(count):
        dp[(1 << index, index)] = (
            distance(start, coords[index]),
            (index,),
            (keys[index],),
        )
    for mask in range(1, 1 << count):
        for last in range(count):
            state = dp.get((mask, last))
            if state is None:
                continue
            length, route, route_keys = state
            for nxt in range(count):
                bit = 1 << nxt
                if mask & bit:
                    continue
                candidate = (
                    length + distance(coords[last], coords[nxt]),
                    route + (nxt,),
                    route_keys + (keys[nxt],),
                )
                state_key = (mask | bit, nxt)
                previous = dp.get(state_key)
                if previous is None or (candidate[0], candidate[2]) < (
                    previous[0],
                    previous[2],
                ):
                    dp[state_key] = candidate
    full = (1 << count) - 1
    best = min(
        (
            length + distance(coords[last], end),
            route_keys,
            route,
        )
        for (mask, last), (length, route, route_keys) in dp.items()
        if mask == full
    )
    return [items[index] for index in best[2]]


def route_length(tasks: Sequence[T], start: Point, end: Point, *, point=lambda task: task.point) -> float:
    positions = [start, *(point(task) for task in tasks), end]
    return sum(distance(a, b) for a, b in zip(positions, positions[1:]))
