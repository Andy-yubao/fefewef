from __future__ import annotations

import math

from task4.client import RobotAPI
from task4.geometry import distance
from task4.search_patterns import double_ring_cover

from .base import BaseStrategy
from .geometry_early_optical_clear_probe import GeometryEarlyOpticalClearProbeStrategy
from .reacquire import ReacquireStrategy


class _NearOpticalReacquireStrategy(ReacquireStrategy):
    """Use certified optical coverage after radio reacquisition fails."""

    near_optical_offsets_m = (20.0, 55.0, 90.0)
    optical_strip_step_m = 28.0
    optical_strip_half_width_m = 14.0
    maximum_positive_range_m = 1500.0

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self._near_prefix_attempted: set[int] = set()

    def _localize(self, api: RobotAPI, channel: int) -> None:
        super()._localize(api, channel)
        belief = self.beliefs[channel]
        if (
            belief.status != "active"
            or not belief.observations
            or channel in self._near_prefix_attempted
        ):
            return

        self._near_prefix_attempted.add(channel)
        station, measured_deg = belief.observations[0]
        angle = math.radians(measured_deg)
        if len(belief.observations) == 1:
            for offset in self.near_optical_offsets_m:
                point = (
                    station[0] + offset * math.cos(angle),
                    station[1] + offset * math.sin(angle),
                )
                if self._clear(api, point, channel):
                    return

        for point in self._optical_strip_points(station, angle):
            if self._clear(api, point, channel):
                return

    def _optical_strip_points(
        self, station: tuple[float, float], angle: float
    ) -> list[tuple[float, float]]:
        """Cover the full positive-bearing wedge by two rows of 20 m disks.

        In bearing-aligned coordinates a positive source lies in
        ``x in [0, 1500]`` and ``abs(y) < 26.5``.  Rows at y=+/-14 with
        longitudinal gaps no greater than 28 have covering radius
        ``sqrt(14**2 + 14**2) < 20``.
        """
        offsets = []
        longitudinal = 0.0
        while longitudinal < self.maximum_positive_range_m:
            offsets.append(longitudinal)
            longitudinal += self.optical_strip_step_m
        if offsets[-1] < self.maximum_positive_range_m:
            offsets.append(self.maximum_positive_range_m)

        forward = (math.cos(angle), math.sin(angle))
        lateral = (-forward[1], forward[0])

        def point(x_offset: float, y_offset: float) -> tuple[float, float]:
            return (
                station[0] + x_offset * forward[0] + y_offset * lateral[0],
                station[1] + x_offset * forward[1] + y_offset * lateral[1],
            )

        candidates = []
        for first_side in (-self.optical_strip_half_width_m, self.optical_strip_half_width_m):
            second_side = -first_side
            candidates.append(
                [point(x, first_side) for x in offsets]
                + [point(x, second_side) for x in reversed(offsets)]
            )
            candidates.append(
                [point(x, first_side) for x in reversed(offsets)]
                + [point(x, second_side) for x in offsets]
            )
        return min(candidates, key=lambda route: distance(self.position, route[0]))


class DoubleRingOpticalClearProbeStrategy(GeometryEarlyOpticalClearProbeStrategy):
    """25-point certified discovery cover with deterministic optical fallbacks."""

    name = "double_ring_optical_clear_probe"

    def __init__(
        self,
        grid_spacing: float = 600.0,
        grid_half_extent: float = 1800.0,
        lattice_spacing: float = 731.0,
        replacement_distance_m: float = 550.0,
        max_replaced_waypoints: int = 0,
        early_clear_radius_m: float = 35.0,
        route_length_slack_m: float = 100.0,
        inner_ring_radius_m: float = 980.0,
        outer_boundary_margin_m: float = 0.25,
        optical_fallback_radius_m: float = 22.0,
    ):
        super().__init__(
            grid_spacing=grid_spacing,
            grid_half_extent=grid_half_extent,
            lattice_spacing=lattice_spacing,
            replacement_distance_m=replacement_distance_m,
            max_replaced_waypoints=max_replaced_waypoints,
            early_clear_radius_m=early_clear_radius_m,
            route_length_slack_m=route_length_slack_m,
        )
        if early_clear_radius_m > 35.0:
            raise ValueError(
                "the seven-point optical certificate currently supports radii up to 35 m"
            )
        if optical_fallback_radius_m != 22.0:
            raise ValueError("the certified optical fallback radius must be 22 m")
        self.inner_ring_radius_m = inner_ring_radius_m
        self.outer_boundary_margin_m = outer_boundary_margin_m
        self.optical_fallback_radius_m = optical_fallback_radius_m

    def _search_waypoints(self) -> list[tuple[float, float]]:
        return double_ring_cover(
            arena_radius=self.grid_half_extent,
            inner_radius=self.inner_ring_radius_m,
            boundary_margin=self.outer_boundary_margin_m,
        )

    def _clear(self, api: RobotAPI, position, channel):
        belief = self.beliefs[channel]
        polygon = belief.polygon() if len(belief.observations) >= 2 else []
        certified = bool(polygon) and max(
            distance(position, vertex) for vertex in polygon
        ) <= self.early_clear_radius_m + 1e-7

        if super()._clear(api, position, channel):
            return True
        if not certified:
            return False

        for index in range(6):
            angle = index * math.pi / 3.0
            point = (
                position[0] + self.optical_fallback_radius_m * math.cos(angle),
                position[1] + self.optical_fallback_radius_m * math.sin(angle),
            )
            # The initial failure is already registered by EarlyOpticalClearProbeStrategy.
            # Use the base action wrapper for the six certified covering points.
            if BaseStrategy._clear(self, api, point, channel):
                return True
        return False

    def _after_clear(self, api: RobotAPI, point, remaining) -> None:
        # A certified optical fallback may have succeeded away from the original center.
        super()._after_clear(api, self.position, remaining)

    def _make_reacquisition_helper(self) -> ReacquireStrategy:
        helper = _NearOpticalReacquireStrategy(self.grid_spacing, self.grid_half_extent)
        helper.position = self.position
        helper.virtual_time_s = self.virtual_time_s
        helper.receiver_channel = self.receiver_channel
        helper.beliefs = self.beliefs
        return helper
