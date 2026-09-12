from __future__ import annotations

import math

from task4.geometry import angle_delta_deg, bearing_deg, distance, enclosing_center_radius

from .integrated_route import (
    RouteNode,
    _multistart_route_candidates,
    _route_length,
)
from .replacement_aware_clear_probe import ReplacementAwareClearProbeStrategy


class GeometryAwareClearProbeStrategy(ReplacementAwareClearProbeStrategy):
    """Break near-equal route ties with active-bearing crossing geometry."""

    name = "geometry_aware_clear_probe"

    def __init__(self, *args, route_length_slack_m: float = 100.0, **kwargs):
        super().__init__(*args, **kwargs)
        if route_length_slack_m < 0:
            raise ValueError("route_length_slack_m must be nonnegative")
        self.route_length_slack_m = route_length_slack_m

    def _active_geometry_value(self, point: tuple[float, float]) -> float:
        value = 0.0
        for belief in self.beliefs.values():
            if belief.status != "active" or not belief.observations:
                continue
            polygon = belief.polygon()
            if not polygon:
                continue
            center, _ = enclosing_center_radius(polygon)
            if distance(point, center) > 1500.0:
                continue
            proposed = bearing_deg(point, center)
            value += max(
                abs(
                    math.sin(
                        math.radians(
                            angle_delta_deg(proposed, bearing_deg(station, center))
                        )
                    )
                )
                for station, _ in belief.observations
            )
        return value

    def _plan_route(
        self, nodes: list[RouteNode], start: tuple[float, float]
    ) -> list[RouteNode]:
        effective = self._effective_route_nodes(nodes, start)
        candidates = _multistart_route_candidates(effective, start)
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
