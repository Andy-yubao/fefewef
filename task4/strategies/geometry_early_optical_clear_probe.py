from __future__ import annotations

from .early_optical_clear_probe import EarlyOpticalClearProbeStrategy
from .geometry_aware_clear_probe import GeometryAwareClearProbeStrategy
from .integrated_route import RouteNode


class GeometryEarlyOpticalClearProbeStrategy(EarlyOpticalClearProbeStrategy):
    """Combine 30 m early optical clearing with near-equal geometry routing."""

    name = "geometry_early_optical_clear_probe"

    def __init__(self, *args, route_length_slack_m: float = 100.0, **kwargs):
        super().__init__(*args, **kwargs)
        if route_length_slack_m < 0:
            raise ValueError("route_length_slack_m must be nonnegative")
        self.route_length_slack_m = route_length_slack_m

    _active_geometry_value = GeometryAwareClearProbeStrategy._active_geometry_value

    def _plan_route(
        self, nodes: list[RouteNode], start: tuple[float, float]
    ) -> list[RouteNode]:
        return GeometryAwareClearProbeStrategy._plan_route(self, nodes, start)
