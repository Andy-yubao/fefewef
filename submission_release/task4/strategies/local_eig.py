from __future__ import annotations

from task4.geometry import distance

from .belief import BeliefSearchStrategy


class LocalEIGStrategy(BeliefSearchStrategy):
    """Use EIG only among waypoints close to the nearest unvisited point."""

    name = "local_eig"

    def __init__(self, *args, eig_distance_slack_m: float = 250.0, **kwargs):
        super().__init__(*args, **kwargs)
        self.eig_distance_slack_m = eig_distance_slack_m

    def _select_waypoint(self, remaining: list[tuple[float, float]]) -> tuple[float, float]:
        unseen_count = sum(belief.status == "unseen" for belief in self.beliefs.values())
        alive_count = self._alive_mask.bit_count()
        if unseen_count == 0 or alive_count == 0:
            return super(BeliefSearchStrategy, self)._select_waypoint(remaining)
        nearest = min(distance(self.position, point) for point in remaining)
        candidates = [
            point
            for point in remaining
            if distance(self.position, point) <= nearest + self.eig_distance_slack_m
        ]
        active_context = self._active_geometry_context()
        return max(
            candidates,
            key=lambda point: self._score_waypoint(point, unseen_count, alive_count, active_context),
        )
