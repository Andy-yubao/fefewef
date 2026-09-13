"""Conservative sensing and clearing events embedded on a route leg."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

import numpy as np

from .channel_state import ChannelState, ChannelStatus
from .config import PhysicalConfig, PlannerConfig
from .route_planner import RouteLeg


class EmbeddedEventKind(str, Enum):
    MEASURE = "MEASURE"
    CLEAR = "CLEAR"


@dataclass(frozen=True)
class EmbeddedEvent:
    position: np.ndarray
    channel: int
    kind: EmbeddedEventKind
    reason: str
    leg_fraction: float
    reception_class: str = "guaranteed"
    baseline_m: float = 0.0
    view_angle_gain_deg: float = 0.0


def segment_disk_entry(
    start: np.ndarray,
    end: np.ndarray,
    center: np.ndarray,
    radius_m: float,
    tolerance_m: float = 1e-7,
) -> tuple[np.ndarray, float] | None:
    """Return the first point where a directed segment enters a closed disk."""
    if radius_m < -tolerance_m:
        return None
    a = np.asarray(start, float)
    b = np.asarray(end, float)
    c = np.asarray(center, float)
    radius = max(0.0, float(radius_m))
    delta = b - a
    length2 = float(np.dot(delta, delta))
    if length2 <= tolerance_m * tolerance_m:
        if float(np.linalg.norm(a - c)) <= radius + tolerance_m:
            return a.copy(), 0.0
        return None
    offset = a - c
    qa = length2
    qb = 2.0 * float(np.dot(offset, delta))
    qc = float(np.dot(offset, offset)) - radius * radius
    if qc <= tolerance_m:
        return a.copy(), 0.0
    discriminant = qb * qb - 4.0 * qa * qc
    if discriminant < -tolerance_m:
        return None
    root = math.sqrt(max(0.0, discriminant))
    enter = (-qb - root) / (2.0 * qa)
    leave = (-qb + root) / (2.0 * qa)
    if leave < -tolerance_m or enter > 1.0 + tolerance_m:
        return None
    fraction = min(1.0, max(0.0, enter))
    return a + fraction * delta, fraction


def segment_disk_interval(
    start: np.ndarray,
    end: np.ndarray,
    center: np.ndarray,
    radius_m: float,
    tolerance_m: float = 1e-7,
) -> tuple[float, float] | None:
    """Return the directed parameter interval lying inside a closed disk."""
    if radius_m < -tolerance_m:
        return None
    a = np.asarray(start, float)
    b = np.asarray(end, float)
    c = np.asarray(center, float)
    radius = max(0.0, float(radius_m))
    delta = b - a
    length2 = float(np.dot(delta, delta))
    if length2 <= tolerance_m * tolerance_m:
        return (0.0, 0.0) if float(np.linalg.norm(a - c)) <= radius + tolerance_m else None
    offset = a - c
    qb = 2.0 * float(np.dot(offset, delta))
    qc = float(np.dot(offset, offset)) - radius * radius
    discriminant = qb * qb - 4.0 * length2 * qc
    if discriminant < -tolerance_m:
        return None
    root = math.sqrt(max(0.0, discriminant))
    enter = (-qb - root) / (2.0 * length2)
    leave = (-qb + root) / (2.0 * length2)
    low = max(0.0, enter)
    high = min(1.0, leave)
    if low > high + tolerance_m:
        return None
    return min(1.0, max(0.0, low)), min(1.0, max(0.0, high))


class OpportunityPlanner:
    """Attach zero-detour conservative events to the current macro route."""

    def __init__(
        self,
        physical: PhysicalConfig = PhysicalConfig(),
        planner: PlannerConfig = PlannerConfig(),
    ):
        self.physical = physical
        self.planner = planner

    def measurement_region_radius(self, state: ChannelState) -> float:
        return max(0.0, self.physical.reception_min_m - state.certificate().radius_m)

    def reception_class(self, state: ChannelState, point: np.ndarray) -> str:
        """Classify a candidate using conservative certificate/reception geometry."""
        distance = float(np.linalg.norm(np.asarray(point, float) - state.certificate().center))
        radius = float(state.certificate().radius_m)
        if distance + radius <= self.physical.reception_min_m + self.planner.numeric_distance_tol_m:
            return "guaranteed"
        if distance - radius > self.physical.reception_max_m + self.planner.numeric_distance_tol_m:
            return "impossible"
        return "possible"

    def clear_region_radius(self, state: ChannelState) -> float:
        return max(
            0.0,
            self.physical.clear_radius_m
            - self.planner.clear_margin_m
            - state.certificate().radius_m,
        )

    def _measurement_quality(self, state: ChannelState, point: np.ndarray) -> float:
        center = state.certificate().center
        candidate_ray = np.asarray(point, float) - center
        candidate_norm = float(np.linalg.norm(candidate_ray))
        if candidate_norm <= self.planner.numeric_distance_tol_m:
            return 0.0
        sensors = [
            np.asarray(observation.position, float)
            for observation in state.history
            if observation.result == "direction"
        ]
        if not sensors:
            return 1.0
        best_sine = 0.0
        for sensor in sensors:
            prior_ray = sensor - center
            denominator = float(np.linalg.norm(prior_ray)) * candidate_norm
            if denominator <= self.planner.numeric_distance_tol_m:
                continue
            cross = float(
                prior_ray[0] * candidate_ray[1]
                - prior_ray[1] * candidate_ray[0]
            )
            best_sine = max(best_sine, abs(cross) / denominator)
        return best_sine

    def measurement_geometry(self, state: ChannelState, point: np.ndarray) -> tuple[float, float]:
        """Return baseline to the nearest bearing and maximum angular gain."""
        center = state.certificate().center
        candidate = np.asarray(point, float)
        sensors = [np.asarray(o.position, float) for o in state.history if o.result == "direction"]
        if not sensors:
            return float("inf"), 180.0
        baseline = min(float(np.linalg.norm(candidate - sensor)) for sensor in sensors)
        gain = math.degrees(math.asin(min(1.0, max(0.0, self._measurement_quality(state, candidate)))))
        return baseline, gain

    def _measurement_point(
        self, state: ChannelState, leg: RouteLeg, radius_m: float,
        *, possible: bool = False,
    ) -> tuple[np.ndarray, float] | None:
        interval = segment_disk_interval(
            leg.start,
            leg.end,
            state.certificate().center,
            radius_m,
            self.planner.numeric_distance_tol_m,
        )
        if interval is None:
            return None
        low, high = interval
        # Search from the start of the leg and accept the first sufficiently
        # informative viewpoint.  An opportunity is a zero-detour measurement,
        # not a reason to keep travelling toward a nearly perpendicular view.
        fractions = np.linspace(low, high, 9)
        delta = leg.end - leg.start
        required_gain = max(
            self.planner.opportunity_target_angle_deg,
            self.planner.minimum_view_angle_gain_deg,
        )
        required_quality = max(
            self.planner.shared_min_sin_angle,
            math.sin(math.radians(required_gain)),
        )
        for fraction in fractions:
            point = leg.start + float(fraction) * delta
            if state.already_measured(point):
                continue
            quality = self._measurement_quality(state, point)
            baseline, gain = self.measurement_geometry(state, point)
            if quality + 1e-12 < required_quality:
                continue
            if baseline < self.planner.minimum_view_baseline_m:
                continue
            return point, float(fraction)
        return None

    def events(
        self,
        leg: RouteLeg,
        channels: dict[int, ChannelState],
        excluded: set[tuple[EmbeddedEventKind, int]] | None = None,
        *,
        allow_possible: bool = False,
    ) -> list[EmbeddedEvent]:
        excluded = excluded or set()
        result: list[EmbeddedEvent] = []
        for state in channels.values():
            if state.status != ChannelStatus.FOUND:
                continue
            certificate = state.certificate()
            clear_key = (EmbeddedEventKind.CLEAR, state.channel)
            clear_radius = self.clear_region_radius(state)
            clear_hit = None
            if (
                certificate.radius_m
                <= self.physical.clear_radius_m - self.planner.clear_margin_m
                and clear_key not in excluded
            ):
                clear_hit = segment_disk_entry(
                    leg.start, leg.end, certificate.center, clear_radius,
                    self.planner.numeric_distance_tol_m,
                )
            if clear_hit is not None:
                point, fraction = clear_hit
                result.append(EmbeddedEvent(
                    point, state.channel, EmbeddedEventKind.CLEAR,
                    "certified_clear_region", fraction, "guaranteed",
                ))
                # A channel that can be cleared on this leg never receives an
                # extra measurement merely for information gathering.
                continue

            measure_key = (EmbeddedEventKind.MEASURE, state.channel)
            if measure_key in excluded:
                continue
            measure_hit = self._measurement_point(state, leg, self.measurement_region_radius(state))
            reception = "guaranteed"
            reason = "guaranteed_reception_useful_geometry"
            # Possible-reception opportunities are primarily a BROAD-stage
            # localization tool.  Once the certificate is ROUGH, guaranteed
            # geometry remains sufficient and avoids repeated low-value hits.
            broad = 2.0 * certificate.radius_m > self.planner.rough_localization_diameter_m
            if measure_hit is None and allow_possible and broad:
                possible_radius = self.physical.reception_max_m + certificate.radius_m
                measure_hit = self._measurement_point(state, leg, possible_radius, possible=True)
                reception = "possible"
                reason = "possible_reception_useful_geometry"
            if measure_hit is None:
                continue
            point, fraction = measure_hit
            baseline, gain = self.measurement_geometry(state, point)
            result.append(EmbeddedEvent(
                point, state.channel, EmbeddedEventKind.MEASURE,
                reason, fraction, reception, baseline, gain,
            ))
        return sorted(
            result,
            key=lambda event: (
                event.leg_fraction,
                event.kind != EmbeddedEventKind.CLEAR,
                event.channel,
            ),
        )
