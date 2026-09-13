from __future__ import annotations

from .certified_clear_probe import CertifiedClearProbeStrategy
from .geometry_aware_clear_probe import GeometryAwareClearProbeStrategy
from .integrated_route import RouteNode, _multistart_route_candidates, _route_length


class CertifiedGeometryClearProbeStrategy(CertifiedClearProbeStrategy):
    """Coverage-certified substitutions with near-equal active-geometry routing."""

    name = "certified_geometry_clear_probe"
    route_length_slack_m = 100.0

    def _plan_route(
        self, nodes: list[RouteNode], start: tuple[float, float]
    ) -> list[RouteNode]:
        candidates = _multistart_route_candidates(nodes, start)
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
                -GeometryAwareClearProbeStrategy._active_geometry_value(
                    self, item[0][0].point
                ),
                item[1],
                tuple((node.kind, node.key) for node in item[0]),
            ),
        )[0]
