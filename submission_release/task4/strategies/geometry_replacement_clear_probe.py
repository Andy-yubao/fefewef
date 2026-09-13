from __future__ import annotations

from task4.geometry import Point, distance

from .geometry_early_optical_clear_probe import GeometryEarlyOpticalClearProbeStrategy
from .integrated_route import RouteNode


class GeometryReplacementClearProbeStrategy(GeometryEarlyOpticalClearProbeStrategy):
    """Protect replacement candidates that offer useful active-bearing geometry."""

    name = "geometry_replacement_clear_probe"

    def __init__(
        self,
        *args,
        replacement_distance_m: float = 550.0,
        **kwargs,
    ):
        super().__init__(
            *args,
            replacement_distance_m=replacement_distance_m,
            **kwargs,
        )

    def _replacement_key(self, clear_point: Point, candidate: Point) -> tuple:
        return (
            self._active_geometry_value(candidate),
            distance(clear_point, candidate),
            candidate,
        )

    def _choose_replacements(self, point: Point, remaining: list[Point]) -> list[Point]:
        eligible = [
            candidate
            for candidate in remaining
            if distance(point, candidate) <= self.replacement_distance_m
        ]
        return sorted(
            eligible,
            key=lambda candidate: self._replacement_key(point, candidate),
        )[: self.max_replaced_waypoints]

    def _effective_route_nodes(
        self, nodes: list[RouteNode], start: Point
    ) -> list[RouteNode]:
        effective = list(nodes)
        measure_nodes = [node for node in nodes if node.kind == "measure"]
        for clear_node in sorted(
            (node for node in nodes if node.kind == "clear"),
            key=lambda node: (distance(start, node.point), node.key),
        ):
            eligible = [
                node
                for node in measure_nodes
                if node in effective
                and distance(clear_node.point, node.point)
                <= self.replacement_distance_m
            ]
            replaceable = sorted(
                eligible,
                key=lambda node: (
                    self._active_geometry_value(node.point),
                    distance(clear_node.point, node.point),
                    node.key,
                ),
            )[: self.max_replaced_waypoints]
            for node in replaceable:
                effective.remove(node)
        return effective
