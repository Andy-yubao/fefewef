from __future__ import annotations

import time

from task4.client import RobotAPI
from task4.geometry import distance, enclosing_center_radius, serpentine_grid

from .base import BaseStrategy, ChannelBelief, StrategyResult
from .reacquire import ReacquireStrategy


class DeferredCoverageStrategy(BaseStrategy):
    """Retire located channels and clear them in one final nearest-neighbor tour."""

    name = "deferred"

    @staticmethod
    def _try_located(belief: ChannelBelief) -> bool:
        if len(belief.observations) < 2:
            return False
        polygon = belief.polygon()
        if not polygon:
            return False
        center, radius = enclosing_center_radius(polygon)
        if radius <= 19.5:
            belief.status = "located"
            belief.clear_target = center
            return True
        return False

    def _make_reacquisition_helper(self) -> ReacquireStrategy:
        helper = ReacquireStrategy(self.grid_spacing, self.grid_half_extent)
        helper.position = self.position
        helper.virtual_time_s = self.virtual_time_s
        helper.beliefs = self.beliefs
        return helper

    def _search_waypoints(self) -> list[tuple[float, float]]:
        return serpentine_grid(self.grid_half_extent, self.grid_spacing)

    def _select_waypoint(self, remaining: list[tuple[float, float]]) -> tuple[float, float]:
        return min(remaining, key=lambda point: distance(self.position, point))

    def _after_waypoint(
        self,
        api: RobotAPI,
        waypoint: tuple[float, float],
        remaining: list[tuple[float, float]],
    ) -> None:
        """Strategy extension point; the base keeps all clears deferred."""

    def _on_search_start(self, waypoint_count: int) -> None:
        """Strategy extension point for progress-aware search policies."""

    def _should_stop_search(self, remaining: list[tuple[float, float]]) -> bool:
        return sum(
            belief.status in {"located", "cleared"} for belief in self.beliefs.values()
        ) == 16

    def run(self, api: RobotAPI) -> StrategyResult:
        started = time.perf_counter()
        api.enter()
        remaining = self._search_waypoints()
        self._on_search_start(len(remaining))
        while remaining:
            waypoint = self._select_waypoint(remaining)
            remaining.remove(waypoint)
            for channel in range(1, 21):
                belief = self.beliefs[channel]
                if belief.status in {"located", "cleared"}:
                    continue
                response = self._measure(api, waypoint, channel)
                if response["measure_result"] == "near":
                    belief.status = "located"
                    belief.clear_target = waypoint
                elif response["measure_result"] == "direction":
                    self._try_located(belief)

            self._after_waypoint(api, waypoint, remaining)

            if self._should_stop_search(remaining):
                break

        for belief in self.beliefs.values():
            if belief.status == "active" and len(belief.observations) >= 2:
                polygon = belief.polygon()
                if polygon:
                    belief.clear_target, radius = enclosing_center_radius(polygon)
                    if radius <= 19.5:
                        belief.status = "located"

        # Only residual wide regions pay for active directional reacquisition.
        helper = self._make_reacquisition_helper()
        for belief in self.beliefs.values():
            if belief.status == "active":
                helper._localize(api, belief.channel)
        self.position, self.virtual_time_s = helper.position, helper.virtual_time_s

        pending = [
            belief
            for belief in self.beliefs.values()
            if belief.status == "located" and belief.clear_target is not None
        ]
        while pending:
            belief = min(pending, key=lambda item: distance(self.position, item.clear_target))
            pending.remove(belief)
            if not self._clear(api, belief.clear_target, belief.channel):
                belief.status = "active"
                helper.position, helper.virtual_time_s = self.position, self.virtual_time_s
                helper._localize(api, belief.channel)
                self.position, self.virtual_time_s = helper.position, helper.virtual_time_s
        return self._finish(api, started)
