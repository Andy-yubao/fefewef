from __future__ import annotations

import time

from task4.client import RobotAPI
from task4.geometry import enclosing_center_radius, serpentine_grid

from .base import BaseStrategy, StrategyResult


class CoverageStrategy(BaseStrategy):
    """Fixed scan baseline using only naturally accumulated intersections."""

    name = "coverage"

    def run(self, api: RobotAPI) -> StrategyResult:
        started = time.perf_counter()
        api.enter()
        for waypoint in serpentine_grid(self.grid_half_extent, self.grid_spacing):
            for channel in range(1, 21):
                belief = self.beliefs[channel]
                if belief.status == "cleared":
                    continue
                response = self._measure(api, waypoint, channel)
                if response["measure_result"] == "near":
                    self._clear(api, waypoint, channel)
                elif len(belief.observations) >= 2:
                    polygon = belief.polygon()
                    if polygon:
                        center, radius = enclosing_center_radius(polygon)
                        if radius <= 19.5:
                            self._clear(api, center, channel)

        # The baseline takes one final optical attempt without extra RF probing.
        for channel, belief in self.beliefs.items():
            if belief.status == "active" and len(belief.observations) >= 2:
                polygon = belief.polygon()
                if polygon:
                    center, _ = enclosing_center_radius(polygon)
                    self._clear(api, center, channel)
        return self._finish(api, started)
