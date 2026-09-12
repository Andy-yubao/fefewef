from __future__ import annotations

from .clear_probe import ClearProbeStrategy
from .integrated_route import RouteNode, _plan_nodes_multistart


class ClearProbeMultistartStrategy(ClearProbeStrategy):
    """Clear-site probes with rolling multi-start open-route optimization."""

    name = "clear_probe_multistart"

    def _plan_route(
        self, nodes: list[RouteNode], start: tuple[float, float]
    ) -> list[RouteNode]:
        return _plan_nodes_multistart(nodes, start)
