from __future__ import annotations

from task4.geometry import distance

from .geometry_early_optical_clear_probe import GeometryEarlyOpticalClearProbeStrategy
from .integrated_route import RouteNode, _multistart_route_candidates, _route_length


def _improve_open_route_relocate(
    route: list[RouteNode], start: tuple[float, float]
) -> list[RouteNode]:
    """Deterministically apply best improving one-node relocations."""

    route = list(route)
    while len(route) >= 2:
        best_gain = 1e-9
        best_move: tuple[int, int] | None = None
        for source_index, node in enumerate(route):
            source_before = start if source_index == 0 else route[source_index - 1].point
            source_after = (
                route[source_index + 1].point
                if source_index + 1 < len(route)
                else None
            )
            removed = distance(source_before, node.point)
            if source_after is not None:
                removed += distance(node.point, source_after)
                removed -= distance(source_before, source_after)

            shortened = route[:source_index] + route[source_index + 1 :]
            for insertion_index in range(len(shortened) + 1):
                before = (
                    start
                    if insertion_index == 0
                    else shortened[insertion_index - 1].point
                )
                after = (
                    shortened[insertion_index].point
                    if insertion_index < len(shortened)
                    else None
                )
                added = distance(before, node.point)
                if after is not None:
                    added += distance(node.point, after)
                    added -= distance(before, after)
                gain = removed - added
                move = (source_index, insertion_index)
                if gain > best_gain + 1e-12 or (
                    abs(gain - best_gain) <= 1e-12
                    and best_move is not None
                    and move < best_move
                ):
                    best_gain = gain
                    best_move = move
        if best_move is None:
            return route
        source_index, insertion_index = best_move
        node = route.pop(source_index)
        route.insert(insertion_index, node)
    return route


class RelocateGeometryClearProbeStrategy(GeometryEarlyOpticalClearProbeStrategy):
    """Add Or-opt-1 relocation to each rolling open-route candidate."""

    name = "relocate_geometry_clear_probe"

    def __init__(self, *args, replacement_distance_m: float = 400.0, **kwargs):
        super().__init__(
            *args, replacement_distance_m=replacement_distance_m, **kwargs
        )

    def _plan_route(
        self, nodes: list[RouteNode], start: tuple[float, float]
    ) -> list[RouteNode]:
        effective = self._effective_route_nodes(nodes, start)
        candidates = [
            _improve_open_route_relocate(route, start)
            for route in _multistart_route_candidates(effective, start)
        ]
        lengths = [_route_length(route, start) for route in candidates]
        best_length = min(lengths)
        eligible = [
            (route, length)
            for route, length in zip(candidates, lengths)
            if length <= best_length + self.route_length_slack_m
        ]
        return min(
            eligible,
            key=lambda item: (
                -self._active_geometry_value(item[0][0].point),
                item[1],
                tuple((node.kind, node.key) for node in item[0]),
            ),
        )[0]
