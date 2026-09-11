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

    def _measurement_point(
        self, state: ChannelState, leg: RouteLeg, radius_m: float
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
        # This tiny deterministic set searches the whole zero-detour feasible
        # interval, avoiding the false rejection caused by checking only entry.
        fractions = np.linspace(low, high, 9)
        delta = leg.end - leg.start
        candidates: list[tuple[float, float, np.ndarray]] = []
        for fraction in fractions:
            point = leg.start + float(fraction) * delta
            if state.already_measured(point):
                continue
            quality = self._measurement_quality(state, point)
            candidates.append((quality, -float(fraction), point))
        if not candidates:
            return None
        quality, negative_fraction, point = max(candidates, key=lambda item: (item[0], item[1]))
        if quality < self.planner.shared_min_sin_angle:
            return None
        return point, -negative_fraction

    def events(
        self,
        leg: RouteLeg,
        channels: dict[int, ChannelState],
        excluded: set[tuple[EmbeddedEventKind, int]] | None = None,
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
                    "certified_clear_region", fraction,
                ))
                # A channel that can be cleared on this leg never receives an
                # extra measurement merely for information gathering.
                continue

            measure_key = (EmbeddedEventKind.MEASURE, state.channel)
            if measure_key in excluded:
                continue
            measure_hit = self._measurement_point(
                state, leg, self.measurement_region_radius(state)
            )
            if measure_hit is None:
                continue
            point, fraction = measure_hit
            result.append(EmbeddedEvent(
                point, state.channel, EmbeddedEventKind.MEASURE,
                "guaranteed_reception_useful_geometry", fraction,
            ))
        return sorted(
            result,
            key=lambda event: (
                event.leg_fraction,
                event.kind != EmbeddedEventKind.CLEAR,
                event.channel,
            ),
        )
