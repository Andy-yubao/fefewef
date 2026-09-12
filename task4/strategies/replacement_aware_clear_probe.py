from __future__ import annotations

from task4.geometry import distance

from .clear_probe import ClearProbeStrategy
from .integrated_route import RouteNode, _plan_nodes_multistart


class ReplacementAwareClearProbeStrategy(ClearProbeStrategy):
    """Plan over the route expected after successful clear-site substitutions."""

    name = "replacement_aware_clear_probe"

    def __init__(
        self,
        grid_spacing: float = 600.0,
        grid_half_extent: float = 1800.0,
        lattice_spacing: float = 731.0,
        replacement_distance_m: float = 400.0,
        max_replaced_waypoints: int = 2,
    ):
        super().__init__(
            grid_spacing,
            grid_half_extent,
            lattice_spacing,
            replacement_distance_m,
            max_replaced_waypoints,
        )

    def _plan_route(
        self, nodes: list[RouteNode], start: tuple[float, float]
    ) -> list[RouteNode]:
        return _plan_nodes_multistart(self._effective_route_nodes(nodes, start), start)

    def _effective_route_nodes(
        self, nodes: list[RouteNode], start: tuple[float, float]
    ) -> list[RouteNode]:
        effective = list(nodes)
        measure_nodes = [node for node in nodes if node.kind == "measure"]
        for clear_node in sorted(
            (node for node in nodes if node.kind == "clear"),
            key=lambda node: (distance(start, node.point), node.key),
        ):
            replaceable = sorted(
                (
                    node
                    for node in measure_nodes
                    if node in effective
                    and distance(clear_node.point, node.point) <= self.replacement_distance_m
                ),
                key=lambda node: (distance(clear_node.point, node.point), node.key),
            )[: self.max_replaced_waypoints]
            for node in replaceable:
                effective.remove(node)
        return effective
