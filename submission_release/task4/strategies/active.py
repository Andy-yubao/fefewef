from __future__ import annotations

import math
import time

from task4.client import RobotAPI
from task4.geometry import (
    Point,
    angle_delta_deg,
    bearing_deg,
    distance,
    enclosing_center_radius,
    serpentine_grid,
)

from .base import BaseStrategy, ChannelBelief, StrategyResult


class ActiveStrategy(BaseStrategy):
    """Immediately leave the coverage route to improve bearing geometry."""

    name = "active"
    max_local_measurements = 6
    continue_after_loss = False

    def _candidate_points(self, belief: ChannelBelief) -> list[Point]:
        candidates: list[Point] = []
        if len(belief.observations) == 1:
            station, theta = belief.observations[0]
            angle = math.radians(theta)
            line_of_sight = (math.cos(angle), math.sin(angle))
            lateral_axis = (-line_of_sight[1], line_of_sight[0])
            for lateral in (320.0, -320.0, 520.0, -520.0):
                candidates.append(
                    (
                        station[0] + 300.0 * line_of_sight[0] + lateral * lateral_axis[0],
                        station[1] + 300.0 * line_of_sight[1] + lateral * lateral_axis[1],
                    )
                )
            candidates.append(
                (station[0] + 500.0 * line_of_sight[0], station[1] + 500.0 * line_of_sight[1])
            )
        else:
            polygon = belief.polygon()
            if polygon:
                center, radius = enclosing_center_radius(polygon)
                ring = min(500.0, max(180.0, radius * 0.35))
                for index in range(12):
                    angle = 2 * math.pi * index / 12
                    candidates.append(
                        (center[0] + ring * math.cos(angle), center[1] + ring * math.sin(angle))
                    )

                station, theta = belief.observations[-1]
                angle = math.radians(theta)
                candidates.append(
                    (station[0] + 300 * math.cos(angle), station[1] + 300 * math.sin(angle))
                )

        def score(point: Point) -> float:
            if any(distance(point, attempted) < 20.0 for attempted in belief.attempted_positions):
                return -1e12
            if len(belief.observations) == 1:
                station, theta = belief.observations[0]
                angle = math.radians(theta)
                proxy_target = (station[0] + 800 * math.cos(angle), station[1] + 800 * math.sin(angle))
                predicted = bearing_deg(point, proxy_target)
                geometry = abs(math.sin(math.radians(angle_delta_deg(predicted, theta))))
            else:
                polygon = belief.polygon()
                if not polygon:
                    return -1e12
                center, _ = enclosing_center_radius(polygon)
                new_bearing = bearing_deg(point, center)
                geometry = sum(
                    math.sin(
                        math.radians(
                            angle_delta_deg(new_bearing, bearing_deg(station, center))
                        )
                    )
                    ** 2
                    for station, _ in belief.observations
                )
            return 1000.0 * geometry - distance(self.position, point)

        return sorted(candidates, key=score, reverse=True)

    def _localize(self, api: RobotAPI, channel: int) -> None:
        belief = self.beliefs[channel]
        measurements = 0
        while belief.status == "active" and measurements < self.max_local_measurements:
            polygon = belief.polygon() if belief.observations else []
            if polygon and len(belief.observations) >= 2:
                center, radius = enclosing_center_radius(polygon)
                if radius <= 19.5 and self._clear(api, center, channel):
                    return

            candidates = self._candidate_points(belief)
            candidate = next(
                (
                    point
                    for point in candidates
                    if all(distance(point, attempted) >= 20 for attempted in belief.attempted_positions)
                ),
                None,
            )
            if candidate is None:
                break
            belief.attempted_positions.append(candidate)
            response = self._measure(api, candidate, channel)
            measurements += 1
            if response["measure_result"] == "near":
                self._clear(api, candidate, channel)
                return
            if response["measure_result"] == "no_signal" and not self.continue_after_loss:
                break

        if belief.status == "active" and len(belief.observations) >= 2:
            polygon = belief.polygon()
            if polygon:
                center, radius = enclosing_center_radius(polygon)
                if radius <= 45.0:
                    self._clear(api, center, channel)

    def run(self, api: RobotAPI) -> StrategyResult:
        started = time.perf_counter()
        api.enter()
        remaining = serpentine_grid(self.grid_half_extent, self.grid_spacing)
        while remaining:
            waypoint = min(remaining, key=lambda point: distance(self.position, point))
            remaining.remove(waypoint)
            for channel in range(1, 21):
                belief = self.beliefs[channel]
                if belief.status == "cleared":
                    continue
                response = self._measure(api, waypoint, channel)
                if response["measure_result"] == "near":
                    self._clear(api, waypoint, channel)
                elif response["measure_result"] == "direction":
                    self._localize(api, channel)
            if sum(belief.status == "cleared" for belief in self.beliefs.values()) == 16:
                break

        for channel, belief in self.beliefs.items():
            if belief.status == "active":
                self._localize(api, channel)
        return self._finish(api, started)
