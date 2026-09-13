"""Per-channel state machine and conservative observation updates."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math

import numpy as np

from .config import PhysicalConfig, PlannerConfig
from .geometry import CellGrid, EnclosingCircle, fallback_cover_centers, safe_mec_for_cells


class ChannelStatus(str, Enum):
    UNKNOWN = "unknown"
    FOUND = "found"
    CLEARED = "cleared"
    ABSENT = "absent"


@dataclass(frozen=True)
class Observation:
    position: tuple[float, float]
    result: str
    bearing_deg: float | None = None
    coverage_index: int | None = None


@dataclass
class ChannelState:
    channel: int
    grid: CellGrid
    physical: PhysicalConfig = field(default_factory=PhysicalConfig)
    planner: PlannerConfig = field(default_factory=PlannerConfig)
    status: ChannelStatus = ChannelStatus.UNKNOWN
    possible: np.ndarray = field(init=False)
    history: list[Observation] = field(default_factory=list)
    coverage_seen: set[int] = field(default_factory=set)
    bearing_count: int = 0
    diagnostic_count: int = 0
    clear_failures: int = 0
    bearing_tolerance_extra_deg: float = 0.0
    fallback_queue: list[tuple[float, float]] = field(default_factory=list)
    first_found_virtual_time_s: float | None = None
    cleared_virtual_time_s: float | None = None
    # Once a source enters directed localizing it remains service debt until
    # its certificate becomes ROUGH/CLEARABLE.  This prevents a second bearing
    # from dropping the source back into the generic BROAD state.
    localization_debt: bool = False
    localization_debt_direction: str | None = None
    # Angular TSP/guard admission is latched.  A source must first have a
    # reliable angular support intersect the directed search window.
    tsp_window_armed: bool = False
    tsp_window_entry_progress: float | None = None
    # Optional one-shot observation scheduled on the edge immediately before
    # a coverage vertex that is nearly radial with the origin bearing.
    cross_view_point: tuple[float, float] | None = None
    cross_view_edge: int | None = None
    cross_view_armed: bool = False
    _certificate_cache: EnclosingCircle | None = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        self.possible = self.grid.all_mask()

    @property
    def possible_count(self) -> int:
        return int(np.count_nonzero(self.possible))

    def already_measured(self, position: np.ndarray, atol: float = 1e-7) -> bool:
        p = np.asarray(position, float)
        return any(np.linalg.norm(p - np.asarray(o.position)) <= atol for o in self.history)

    def _mask_for(self, obs: Observation) -> np.ndarray:
        p = np.asarray(obs.position, float)
        if obs.result == "direction":
            if obs.bearing_deg is None or not math.isfinite(obs.bearing_deg):
                raise ValueError("direction observation requires a finite bearing")
            return self.grid.direction_keep_mask(
                p,
                obs.bearing_deg,
                self.physical.bearing_error_deg + self.bearing_tolerance_extra_deg,
                self.physical.reception_max_m,
                self.physical.near_radius_m,
                self.planner.numeric_angle_tol_deg,
                self.planner.numeric_distance_tol_m,
            )
        if obs.result == "no_signal":
            return self.grid.no_signal_keep_mask(
                p, self.physical.reception_min_m, self.planner.numeric_distance_tol_m
            )
        if obs.result == "near":
            # A near result is followed immediately by clear. Retain all cells
            # that may meet the analytic <=5 m statement for diagnostics.
            from .geometry import min_distance_to_cells
            return min_distance_to_cells(p, self.grid.centers, self.grid.half_m) <= self.physical.near_radius_m
        raise ValueError(f"unknown observation result: {obs.result}")

    def apply_observation(self, obs: Observation) -> bool:
        """Apply an observation. Return True when caller must clear immediately."""
        if self.status in (ChannelStatus.CLEARED, ChannelStatus.ABSENT):
            raise ValueError(f"cannot measure channel in state {self.status}")
        if self.already_measured(np.asarray(obs.position)):
            raise ValueError("same channel and position must not be measured twice")
        old = self.possible.copy()
        proposed = old & self._mask_for(obs)
        self.history.append(obs)
        if obs.coverage_index is not None:
            self.coverage_seen.add(obs.coverage_index)
        if not np.any(proposed) and not (
            self.status == ChannelStatus.UNKNOWN and obs.result == "no_signal"
        ):
            self.diagnostic_count += 1
            # Do not silently replace the hard set with an estimate; preserve
            # the last nonempty superset and let the controller log the fault.
            return obs.result == "near"
        self.possible = proposed
        self._certificate_cache = None
        if obs.result in ("direction", "near"):
            if self.status == ChannelStatus.UNKNOWN:
                self.status = ChannelStatus.FOUND
            if obs.result == "direction":
                self.bearing_count += 1
        return obs.result == "near"

    def mark_absent_if_covered(self, coverage_point_count: int = 7) -> bool:
        if self.status == ChannelStatus.UNKNOWN and len(self.coverage_seen) == coverage_point_count:
            self.status = ChannelStatus.ABSENT
            return True
        return False

    def mark_cleared(self, virtual_time_s: float | None = None) -> None:
        if self.status != ChannelStatus.FOUND:
            raise ValueError("only a found channel can be cleared")
        self.status = ChannelStatus.CLEARED
        self.cleared_virtual_time_s = virtual_time_s
        self.fallback_queue.clear()

    def certificate(self) -> EnclosingCircle:
        if self._certificate_cache is None:
            self._certificate_cache = safe_mec_for_cells(
                self.grid, self.possible, seed=self.planner.seed + self.channel
            )
        return self._certificate_cache

    def safe_clear_point(self) -> np.ndarray | None:
        circle = self.certificate()
        if circle.radius_m <= self.physical.clear_radius_m - self.planner.clear_margin_m:
            return circle.center.copy()
        return None

    def activate_fallback(self, current_position: np.ndarray) -> None:
        if self.fallback_queue:
            return
        centers = fallback_cover_centers(self.grid, self.possible, self.physical.clear_radius_m)
        # Greedy order is computed incrementally by the controller to avoid an
        # unnecessary O(n^2) precomputation for large first-bearing sets.
        self.fallback_queue = [tuple(map(float, p)) for p in centers]

    def next_fallback_point(self, current_position: np.ndarray) -> np.ndarray | None:
        if not self.fallback_queue:
            return None
        p = np.asarray(current_position, float)
        arr = np.asarray(self.fallback_queue, float)
        idx = int(np.argmin(np.linalg.norm(arr - p, axis=1)))
        return np.asarray(self.fallback_queue.pop(idx), float)

    def handle_failed_clear(self, point: np.ndarray, certified: bool) -> None:
        self.clear_failures += 1
        if certified:
            # Rebuild from complete history with a wider angular tolerance.
            self.bearing_tolerance_extra_deg += max(1e-5, 10.0 * self.planner.numeric_angle_tol_deg)
            observations = list(self.history)
            self.possible = self.grid.all_mask()
            for obs in observations:
                self.possible &= self._mask_for(obs)
            self._certificate_cache = None
            self.fallback_queue.clear()
        else:
            keep = self.grid.failed_clear_keep_mask(
                point, self.physical.clear_radius_m, self.planner.numeric_distance_tol_m
            )
            proposed = self.possible & keep
            if np.any(proposed):
                self.possible = proposed
                self._certificate_cache = None


def initialize_channels(grid: CellGrid, physical: PhysicalConfig, planner: PlannerConfig) -> dict[int, ChannelState]:
    return {c: ChannelState(c, grid, physical, planner) for c in range(1, physical.channels + 1)}


def termination_status(channels: dict[int, ChannelState], coverage_complete: bool,
                       physical: PhysicalConfig = PhysicalConfig()) -> tuple[bool, str]:
    cleared = sum(s.status == ChannelStatus.CLEARED for s in channels.values())
    if cleared == physical.max_sources:
        return True, "upper_bound_reached"
    unresolved_found = any(s.status == ChannelStatus.FOUND for s in channels.values())
    unresolved_unknown = any(s.status == ChannelStatus.UNKNOWN for s in channels.values())
    if coverage_complete and not unresolved_unknown and not unresolved_found:
        if cleared < physical.min_sources:
            return False, "invalid_below_problem_lower_bound"
        return True, "coverage_certificate_and_all_found_cleared"
    return False, "incomplete"
