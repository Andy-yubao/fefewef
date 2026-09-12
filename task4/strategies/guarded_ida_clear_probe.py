from __future__ import annotations

from .geometry_aware_clear_probe import GeometryAwareClearProbeStrategy
from .ida_heuristic_clear_probe import IDAHeuristicClearProbeStrategy
from .integrated_route import RouteNode, _multistart_route_candidates, _route_length


class GuardedIDAClearProbeStrategy(IDAHeuristicClearProbeStrategy):
    """Apply bounded g+h search only after a first-step geometry gate."""

    name = "guarded_ida_clear_probe"

    def __init__(
        self,
        *args,
        early_clear_radius_m: float = 35.0,
        route_length_slack_m: float = 100.0,
        heuristic_depth: int = 3,
        geometry_credit_s: float = 12.0,
        geometry_floor_ratio: float = 1.0,
        **kwargs,
    ):
        super().__init__(
            *args,
            early_clear_radius_m=early_clear_radius_m,
            route_length_slack_m=route_length_slack_m,
            heuristic_depth=heuristic_depth,
            geometry_credit_s=geometry_credit_s,
            **kwargs,
        )
        if not 0.0 <= geometry_floor_ratio <= 1.0:
            raise ValueError("geometry_floor_ratio must be in [0, 1]")
        self.geometry_floor_ratio = geometry_floor_ratio

    _active_geometry_value = GeometryAwareClearProbeStrategy._active_geometry_value

    def _plan_route(
        self, nodes: list[RouteNode], start: tuple[float, float]
    ) -> list[RouteNode]:
        effective = self._effective_route_nodes(nodes, start)
        candidates = _multistart_route_candidates(effective, start)
        lengths = [_route_length(route, start) for route in candidates]
        shortest = min(lengths)
        eligible = [
            route
            for route, length in zip(candidates, lengths)
            if length <= shortest + self.route_length_slack_m
        ]

        geometry_cache: dict[tuple[float, float], float] = {}
        first_values = []
        for route in eligible:
            point = route[0].point
            if point not in geometry_cache:
                geometry_cache[point] = self._active_geometry_value(point)
            first_values.append(geometry_cache[point])
        best_first_value = max(first_values)
        gated = [
            route
            for route, value in zip(eligible, first_values)
            if value + 1e-12 >= best_first_value * self.geometry_floor_ratio
        ]

        incumbent = min(
            gated,
            key=lambda route: self._f_score(
                route, start, 1, nodes, geometry_cache
            ),
        )
        for depth in range(2, self.heuristic_depth + 1):
            incumbent = min(
                gated,
                key=lambda route: self._f_score(
                    route, start, depth, nodes, geometry_cache
                ),
            )
        return incumbent
