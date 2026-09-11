from __future__ import annotations

from task4.client import RobotAPI

from .opportunistic import OpportunisticClearStrategy


class EarlyStopStrategy(OpportunisticClearStrategy):
    """Risk-aware heuristic that stops after a long late discovery drought."""

    name = "early_stop"

    def __init__(
        self,
        *args,
        minimum_search_fraction: float = 0.75,
        discovery_patience: int = 7,
        minimum_known_sources: int = 10,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        self.minimum_search_fraction = minimum_search_fraction
        self.discovery_patience = discovery_patience
        self.minimum_known_sources = minimum_known_sources
        self._total_waypoints = 0
        self._visited_waypoints = 0
        self._last_discovery_waypoint = 0
        self._known_count = 0

    def _on_search_start(self, waypoint_count: int) -> None:
        self._total_waypoints = waypoint_count

    def _after_waypoint(self, api: RobotAPI, waypoint, remaining) -> None:
        super()._after_waypoint(api, waypoint, remaining)
        self._visited_waypoints += 1
        known = sum(belief.status != "unseen" for belief in self.beliefs.values())
        if known > self._known_count:
            self._known_count = known
            self._last_discovery_waypoint = self._visited_waypoints

    def _should_stop_search(self, remaining) -> bool:
        if super()._should_stop_search(remaining):
            return True
        progress = self._visited_waypoints / self._total_waypoints
        drought = self._visited_waypoints - self._last_discovery_waypoint
        unresolved = any(belief.status == "active" for belief in self.beliefs.values())
        return (
            self._known_count >= self.minimum_known_sources
            and not unresolved
            and progress >= self.minimum_search_fraction
            and drought >= self.discovery_patience
        )
