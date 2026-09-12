from __future__ import annotations

from task4.client import RobotAPI
from task4.geometry import distance

from .integrated_route import IntegratedRouteStrategy


class ClearProbeStrategy(IntegratedRouteStrategy):
    """Measure unresolved channels at clear sites and replace nearby grid probes."""

    name = "clear_probe"

    def __init__(
        self,
        grid_spacing: float = 600.0,
        grid_half_extent: float = 1800.0,
        lattice_spacing: float = 735.0,
        replacement_distance_m: float = 400.0,
        max_replaced_waypoints: int = 2,
    ):
        super().__init__(grid_spacing, grid_half_extent, lattice_spacing)
        self.replacement_distance_m = replacement_distance_m
        self.max_replaced_waypoints = max_replaced_waypoints

    def _after_clear(self, api: RobotAPI, point, remaining) -> None:
        if not remaining:
            return
        replaceable = self._choose_replacements(point, remaining)
        if not replaceable:
            return
        for candidate in replaceable:
            remaining.remove(candidate)
        self._probe_channels_at_clear(
            api, point, self._channel_scan_order({"located", "cleared"})
        )

    def _probe_channels_at_clear(self, api: RobotAPI, point, channels) -> None:
        for channel in channels:
            belief = self.beliefs[channel]
            response = self._measure(api, point, channel)
            if response["measure_result"] == "near":
                belief.status = "located"
                belief.clear_target = point
            elif response["measure_result"] == "direction":
                self._try_located(belief)

    def _choose_replacements(self, point, remaining):
        replaceable = sorted(remaining, key=lambda candidate: distance(point, candidate))
        return [
            candidate
            for candidate in replaceable[: self.max_replaced_waypoints]
            if distance(point, candidate) <= self.replacement_distance_m
        ]
