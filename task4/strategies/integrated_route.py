from __future__ import annotations

from dataclasses import dataclass
import time

from task4.client import RobotAPI
from task4.geometry import distance, enclosing_center_radius

from .base import StrategyResult
from .lattice import LatticeDeferredStrategy


@dataclass(frozen=True)
class RouteNode:
    kind: str
    key: int
    point: tuple[float, float]


def _plan_nodes(nodes: list[RouteNode], start: tuple[float, float]) -> list[RouteNode]:
    remaining = list(nodes)
    route = []
    position = start
    while remaining:
        node = min(remaining, key=lambda item: distance(position, item.point))
        remaining.remove(node)
        route.append(node)
        position = node.point
    while True:
        improved = False
        for first in range(len(route) - 1):
            before = start if first == 0 else route[first - 1].point
            for last in range(first + 1, len(route)):
                old = distance(before, route[first].point)
                new = distance(before, route[last].point)
                if last + 1 < len(route):
                    old += distance(route[last].point, route[last + 1].point)
                    new += distance(route[first].point, route[last + 1].point)
                if new + 1e-9 < old:
                    route[first : last + 1] = reversed(route[first : last + 1])
                    improved = True
                    break
            if improved:
                break
        if not improved:
            return route


class IntegratedRouteStrategy(LatticeDeferredStrategy):
    """Joint rolling route over coverage vertices and located clear targets."""

    name = "integrated_route"

    def _after_clear(self, api: RobotAPI, point, remaining) -> None:
        """Extension point for strategies that reuse a visited clear position."""

    def run(self, api: RobotAPI) -> StrategyResult:
        started = time.perf_counter()
        api.enter()
        remaining = self._search_waypoints()
        waypoint_ids = {point: index for index, point in enumerate(remaining)}
        while remaining:
            nodes = [RouteNode("measure", waypoint_ids[point], point) for point in remaining]
            nodes.extend(
                RouteNode("clear", belief.channel, belief.clear_target)
                for belief in self.beliefs.values()
                if belief.status == "located" and belief.clear_target is not None
            )
            node = _plan_nodes(nodes, self.position)[0]
            if node.kind == "clear":
                belief = self.beliefs[node.key]
                if self._clear(api, node.point, node.key):
                    self._after_clear(api, node.point, remaining)
                else:
                    belief.status = "active"
                continue

            remaining.remove(node.point)
            for channel in self._channel_scan_order({"located", "cleared"}):
                belief = self.beliefs[channel]
                response = self._measure(api, node.point, channel)
                if response["measure_result"] == "near":
                    belief.status = "located"
                    belief.clear_target = node.point
                elif response["measure_result"] == "direction":
                    self._try_located(belief)
            if sum(b.status in {"located", "cleared"} for b in self.beliefs.values()) == 16:
                remaining.clear()

        for belief in self.beliefs.values():
            if belief.status == "active" and len(belief.observations) >= 2:
                polygon = belief.polygon()
                if polygon:
                    belief.clear_target, radius = enclosing_center_radius(polygon)
                    if radius <= 19.5:
                        belief.status = "located"

        helper = self._make_reacquisition_helper()
        for belief in self.beliefs.values():
            if belief.status == "active":
                helper._localize(api, belief.channel)
        self.position, self.virtual_time_s = helper.position, helper.virtual_time_s

        pending = [
            RouteNode("clear", belief.channel, belief.clear_target)
            for belief in self.beliefs.values()
            if belief.status == "located" and belief.clear_target is not None
        ]
        while pending:
            node = _plan_nodes(pending, self.position)[0]
            pending.remove(node)
            if not self._clear(api, node.point, node.key):
                belief = self.beliefs[node.key]
                belief.status = "active"
                helper.position, helper.virtual_time_s = self.position, self.virtual_time_s
                helper._localize(api, node.key)
                self.position, self.virtual_time_s = helper.position, helper.virtual_time_s
        return self._finish(api, started)
