from __future__ import annotations

import math
import time

from task4.client import RobotAPI
from task4.geometry import (
    Point, angle_delta_deg, bearing_deg, clip_bearing_wedge, distance,
    enclosing_center_radius,
)

from .base import BaseStrategy, ChannelBelief, StrategyResult
from .double_ring_optical_clear_probe import DoubleRingOpticalClearProbeStrategy
from .early_optical_clear_probe import EarlyOpticalClearProbeStrategy
from .integrated_route import RouteNode


class AdaptiveDoubleRingClearProbeStrategy(DoubleRingOpticalClearProbeStrategy):
    """Certified double-ring discovery with optical and known-source scheduling.

    Coverage vertices are never replaced. Once all 16 possible channels have
    been observed, discovery ends and the inherited complete optical-strip
    fallback remains available for every unresolved source. No environment
    count, type, radius, position, or direction is supplied to the policy.
    """

    name = "adaptive_double_ring_clear_probe"

    def __init__(
        self,
        *args,
        early_clear_radius_m: float = 50.0,
        max_replaced_waypoints: int = 0,
        clear_probe_limit: int = 2,
        finish_when_all_seen: bool = True,
        **kwargs,
    ):
        if not math.isfinite(early_clear_radius_m) or not 19.5 <= early_clear_radius_m <= 50.0:
            raise ValueError("certified early_clear_radius_m must be in [19.5, 50]")
        if max_replaced_waypoints != 0:
            raise ValueError("adaptive double-ring discovery requires no waypoint replacement")
        if isinstance(clear_probe_limit, bool) or not isinstance(clear_probe_limit, int) or clear_probe_limit < 0:
            raise ValueError("clear_probe_limit must be a nonnegative integer")
        # The parent validates its original seven-disk, 35 m certificate.
        # This strategy independently implements the larger certificates below.
        super().__init__(
            *args, early_clear_radius_m=min(35.0, early_clear_radius_m),
            max_replaced_waypoints=0, **kwargs,
        )
        self.early_clear_radius_m = early_clear_radius_m
        self.clear_probe_limit = clear_probe_limit
        self.finish_when_all_seen = finish_when_all_seen
        self._stats: dict[str, int | float | None] = {
            "coverage_points_visited": 0,
            "coverage_points_omitted_after_seen16": 0,
            "seen16_time_s": None,
            "endgame_start_s": None,
            "clear_site_probe_count": 0,
            "clear_site_probe_positive_count": 0,
            "clear_site_probe_located_count": 0,
            "optical_cover_events": 0,
            "optical_cover_attempts": 0,
            "endgame_reacquisitions": 0,
        }

    def _all_seen(self) -> bool:
        return sum(belief.status != "unseen" for belief in self.beliefs.values()) == 16

    def _measure(self, api: RobotAPI, position: Point, channel: int) -> dict:
        response = super()._measure(api, position, channel)
        if self._stats["seen16_time_s"] is None and self._all_seen():
            self._stats["seen16_time_s"] = self.virtual_time_s
        return response

    def _channel_scan_order(self, excluded_statuses: set[str]) -> list[int]:
        if self._all_seen():
            excluded_statuses = excluded_statuses | {"unseen"}
        return super()._channel_scan_order(excluded_statuses)

    def _optical_ring(self) -> tuple[int, float]:
        """Center + ring covers the complete configured feasible disk.

        For r in [20, R], distance to the closest ring point has square at
        most r*r + a*a - 2*r*a*cos(pi/n). This convex quadratic is below
        400 at both endpoints for (R,n,a)=(35,6,22),(45,8,33),(50,10,36).
        The initial center covers r <= 20; intermediate thresholds inherit
        the certificate of the next larger disk.
        """
        if self.early_clear_radius_m <= 35.0:
            return 6, 22.0
        if self.early_clear_radius_m <= 45.0:
            return 8, 33.0
        return 10, 36.0

    def _clear(self, api: RobotAPI, position: Point, channel: int) -> bool:
        belief = self.beliefs[channel]
        polygon = belief.polygon() if len(belief.observations) >= 2 else []
        certified = bool(polygon) and all(
            distance(position, vertex) <= self.early_clear_radius_m + 1e-7
            for vertex in polygon
        )
        if EarlyOpticalClearProbeStrategy._clear(self, api, position, channel):
            return True
        if not certified:
            return False
        self._stats["optical_cover_events"] += 1
        count, radius = self._optical_ring()
        for index in range(count):
            angle = 2.0 * math.pi * index / count
            point = (
                position[0] + radius * math.cos(angle),
                position[1] + radius * math.sin(angle),
            )
            self._stats["optical_cover_attempts"] += 1
            if BaseStrategy._clear(self, api, point, channel):
                return True
        return False

    def _clear_probe_value(self, point: Point, belief: ChannelBelief) -> float:
        if not belief.observations:
            return 0.0
        polygon = belief.polygon()
        if not polygon:
            return 0.0
        center, radius = enclosing_center_radius(polygon)
        if distance(point, center) > 1350.0:
            return 0.0
        if any(distance(point, station) < 20.0 for station, _ in belief.observations):
            return 0.0
        proposed = bearing_deg(point, center)
        angles = [
            abs(angle_delta_deg(proposed, bearing_deg(station, center)))
            for station, _ in belief.observations
        ]
        crossing = max(abs(math.sin(math.radians(angle))) for angle in angles)
        if crossing < 0.25:
            return 0.0
        predicted = clip_bearing_wedge(polygon, point, proposed)
        if not predicted:
            return 0.0
        _, after_radius = enclosing_center_radius(predicted)
        if after_radius > self.early_clear_radius_m and after_radius > 0.75 * radius:
            return 0.0
        # Ranking heuristic, not an absence or visibility certificate.
        visibility = max(0.25, 1.0 - min(angles) / 180.0)
        return visibility * math.log(max(1.0, radius / max(1.0, after_radius)))

    def _after_clear(self, api: RobotAPI, point: Point, remaining: list[Point]) -> None:
        if not remaining or not self.clear_probe_limit:
            return
        point = self.position  # A successful optical ring step may shift the center.
        order = self._channel_scan_order({"unseen", "located", "cleared"})
        values = {channel: self._clear_probe_value(point, self.beliefs[channel]) for channel in order}
        selected = set(sorted(
            (channel for channel in order if values[channel] > 0.0),
            key=lambda channel: (-values[channel], channel),
        )[:self.clear_probe_limit])
        for channel in order:
            if channel not in selected:
                continue
            self._stats["clear_site_probe_count"] += 1
            response = self._measure(api, point, channel)
            belief = self.beliefs[channel]
            if response["measure_result"] in {"direction", "near"}:
                self._stats["clear_site_probe_positive_count"] += 1
            if response["measure_result"] == "near":
                belief.status, belief.clear_target = "located", point
            elif response["measure_result"] == "direction":
                self._try_located(belief)
            if belief.status == "located":
                self._stats["clear_site_probe_located_count"] += 1

    def _endgame_target(self, belief: ChannelBelief) -> Point:
        if belief.status == "located" and belief.clear_target is not None:
            return belief.clear_target
        polygon = belief.polygon()
        if polygon:
            return enclosing_center_radius(polygon)[0]
        # Normally only reachable for a near observation, which is immediately
        # assigned its observed position in the main loop.
        if belief.clear_target is not None:
            return belief.clear_target
        raise RuntimeError(f"observed channel {belief.channel} has no localization evidence")

    def _finish_known_sources(self, api: RobotAPI) -> None:
        self._stats["endgame_start_s"] = self.virtual_time_s
        helper = self._make_reacquisition_helper()
        pending = [b for b in self.beliefs.values() if b.status not in {"unseen", "cleared"}]
        while pending:
            belief = min(pending, key=lambda b: (distance(self.position, self._endgame_target(b)), b.channel))
            pending.remove(belief)
            if belief.status == "located" and self._clear(api, belief.clear_target, belief.channel):
                continue
            belief.status = "active"
            self._stats["endgame_reacquisitions"] += 1
            helper.position = self.position
            helper.virtual_time_s = self.virtual_time_s
            helper.receiver_channel = self.receiver_channel
            helper._localize(api, belief.channel)
            self.position = helper.position
            self.virtual_time_s = helper.virtual_time_s
            self.receiver_channel = helper.receiver_channel

    def run(self, api: RobotAPI) -> StrategyResult:
        started = time.perf_counter()
        api.enter()
        remaining = self._search_waypoints()
        waypoint_ids = {point: index for index, point in enumerate(remaining)}
        while remaining:
            if self.finish_when_all_seen and self._all_seen():
                self._stats["coverage_points_omitted_after_seen16"] = len(remaining)
                break
            nodes = [RouteNode("measure", waypoint_ids[p], p) for p in remaining]
            nodes.extend(
                RouteNode("clear", b.channel, b.clear_target)
                for b in self.beliefs.values()
                if b.status == "located" and b.clear_target is not None
            )
            node = self._plan_route(nodes, self.position)[0]
            if node.kind == "clear":
                if self._clear(api, node.point, node.key):
                    self._after_clear(api, self.position, remaining)
                else:
                    self.beliefs[node.key].status = "active"
                continue
            remaining.remove(node.point)
            self._stats["coverage_points_visited"] += 1
            for channel in self._channel_scan_order({"located", "cleared"}):
                belief = self.beliefs[channel]
                if belief.status == "unseen" and self._all_seen():
                    continue  # The 16th source may have appeared during this scan.
                response = self._measure(api, node.point, channel)
                if response["measure_result"] == "near":
                    belief.status, belief.clear_target = "located", node.point
                elif response["measure_result"] == "direction":
                    self._try_located(belief)
            if sum(b.status in {"located", "cleared"} for b in self.beliefs.values()) == 16:
                self._stats["coverage_points_omitted_after_seen16"] = len(remaining)
                break
        self._finish_known_sources(api)
        result = self._finish(api, started)
        result.diagnostics = dict(self._stats)
        return result
