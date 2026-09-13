from __future__ import annotations

from task4.geometry import distance

from .opportunistic import OpportunisticClearStrategy


class RejoinClearStrategy(OpportunisticClearStrategy):
    """Price a clear detour against its best post-clear coverage re-entry."""

    name = "rejoin_clear"

    def _clear_insertion_penalty(self, target, remaining, next_waypoint) -> float:
        if not remaining:
            return 0.0
        current_to_search = min(distance(self.position, point) for point in remaining)
        target_to_search = min(distance(target, point) for point in remaining)
        return distance(self.position, target) + target_to_search - current_to_search
