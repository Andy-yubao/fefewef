from __future__ import annotations

from task4.geometry import distance

from .early_optical_clear_probe import EarlyOpticalClearProbeStrategy
from .geometry_aware_clear_probe import GeometryAwareClearProbeStrategy
from .integrated_route import RouteNode, _multistart_route_candidates, _route_length


class IDAHeuristicClearProbeStrategy(EarlyOpticalClearProbeStrategy):
    """Use an IDA*-inspired bounded f-score over near-shortest rolling routes."""

    name = "ida_heuristic_clear_probe"

    def __init__(
        self,
        *args,
        route_length_slack_m: float = 60.0,
        heuristic_depth: int = 3,
        geometry_credit_s: float = 12.0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if route_length_slack_m < 0:
            raise ValueError("route_length_slack_m must be nonnegative")
        if heuristic_depth < 1:
            raise ValueError("heuristic_depth must be positive")
        if geometry_credit_s < 0:
            raise ValueError("geometry_credit_s must be nonnegative")
        self.route_length_slack_m = route_length_slack_m
        self.heuristic_depth = heuristic_depth
        self.geometry_credit_s = geometry_credit_s

    def _will_measure(self, node: RouteNode, original_nodes: list[RouteNode]) -> bool:
        if node.kind == "measure":
            return True
        return any(
            candidate.kind == "measure"
            and distance(node.point, candidate.point) <= self.replacement_distance_m
            for candidate in original_nodes
        )

    def _f_score(
        self,
        route: list[RouteNode],
        start: tuple[float, float],
        depth: int,
        original_nodes: list[RouteNode],
        geometry_cache: dict[tuple[float, float], float],
    ) -> tuple[float, float, tuple[tuple[str, int], ...]]:
        # g + h is the current deterministic open-route estimate. The only
        # speculative term is a bounded, discounted credit for crossing active
        # bearing geometry at nodes that will actually measure channels.
        travel_time = _route_length(route, start) / 5.0
        geometry_credit = 0.0
        discount = 1.0
        for node in route[:depth]:
            if self._will_measure(node, original_nodes):
                if node.point not in geometry_cache:
                    geometry_cache[node.point] = (
                        GeometryAwareClearProbeStrategy._active_geometry_value(
                            self, node.point
                        )
                    )
                geometry_credit += discount * geometry_cache[node.point]
            discount *= 0.5
        score = travel_time - self.geometry_credit_s * geometry_credit
        return score, travel_time, tuple((node.kind, node.key) for node in route)

    def _plan_route(
        self, nodes: list[RouteNode], start: tuple[float, float]
    ) -> list[RouteNode]:
        effective = self._effective_route_nodes(nodes, start)
        candidates = _multistart_route_candidates(effective, start)
        shortest = min(_route_length(route, start) for route in candidates)
        eligible = [
            route
            for route in candidates
            if _route_length(route, start) <= shortest + self.route_length_slack_m
        ]
        geometry_cache: dict[tuple[float, float], float] = {}
        incumbent = min(
            eligible,
            key=lambda route: self._f_score(route, start, 1, nodes, geometry_cache),
        )
        for depth in range(2, self.heuristic_depth + 1):
            incumbent = min(
                eligible,
                key=lambda route: self._f_score(
                    route, start, depth, nodes, geometry_cache
                ),
            )
        return incumbent
