from __future__ import annotations

from task4.client import RobotAPI
from task4.geometry import distance

from .lattice import LatticeDeferredStrategy


class OpportunisticClearStrategy(LatticeDeferredStrategy):
    """Clear certified targets during search when route insertion is inexpensive."""

    name = "opportunistic"

    def __init__(
        self,
        grid_spacing: float = 600.0,
        grid_half_extent: float = 1800.0,
        lattice_spacing: float = 760.0,
        clear_detour_threshold_m: float = 1500.0,
    ):
        super().__init__(grid_spacing, grid_half_extent, lattice_spacing)
        self.clear_detour_threshold_m = clear_detour_threshold_m

    def _after_waypoint(
        self,
        api: RobotAPI,
        waypoint: tuple[float, float],
        remaining: list[tuple[float, float]],
    ) -> None:
        while True:
            pending = [
                belief
                for belief in self.beliefs.values()
                if belief.status == "located" and belief.clear_target is not None
            ]
            if not pending:
                return
            next_waypoint = self._next_waypoint(remaining)

            belief = min(
                pending,
                key=lambda item: self._clear_insertion_penalty(item.clear_target, remaining, next_waypoint),
            )
            if self._clear_insertion_penalty(belief.clear_target, remaining, next_waypoint) > self.clear_detour_threshold_m:
                return
            if not self._clear(api, belief.clear_target, belief.channel):
                belief.status = "active"
                return

    def _next_waypoint(self, remaining: list[tuple[float, float]]):
        return min(remaining, key=lambda point: distance(self.position, point)) if remaining else None

    def _clear_insertion_penalty(self, target, remaining, next_waypoint) -> float:
        if next_waypoint is None:
            return 0.0
        return (
            distance(self.position, target)
            + distance(target, next_waypoint)
            - distance(self.position, next_waypoint)
        )
