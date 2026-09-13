from __future__ import annotations

from task4.client import RobotAPI

from .active_clear_probe import ActiveClearProbeStrategy
from .endgame_clear_probe import EndgameClearProbeStrategy
from .integrated_route import RouteNode, _plan_nodes_multistart


class OptimizedClearProbeStrategy(ActiveClearProbeStrategy):
    """Combined rolling-route and directional-tail improvements."""

    name = "optimized_clear_probe"

    def _plan_route(
        self, nodes: list[RouteNode], start: tuple[float, float]
    ) -> list[RouteNode]:
        return _plan_nodes_multistart(nodes, start)

    def _resolve_active_channels(self, api: RobotAPI) -> None:
        EndgameClearProbeStrategy._resolve_active_channels(self, api)
