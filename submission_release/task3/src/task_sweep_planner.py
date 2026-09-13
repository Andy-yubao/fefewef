"""Discrete sector, deadline, and forward-transverse rules for task sweep."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np

from .channel_state import ChannelState
from .config import PhysicalConfig, PlannerConfig


@dataclass(frozen=True)
class ServiceWindow:
    sector: int
    source_rank: int
    relative_rank: int
    deadline: bool
    current_sector: bool


class TaskSweepPlanner:
    def __init__(
        self,
        coverage: np.ndarray,
        sweep_direction: str,
        physical: PhysicalConfig = PhysicalConfig(),
        planner: PlannerConfig = PlannerConfig(),
    ) -> None:
        self.coverage = np.asarray(coverage, float)
        self.sweep_direction = sweep_direction
        self.physical = physical
        self.planner = planner

    @property
    def sector_count(self) -> int:
        return len(self.coverage) - 1

    def sector_for_point(self, point: np.ndarray) -> int:
        """Return the geometric sector label in canonical CCW order."""
        point = np.asarray(point, float)
        if float(np.linalg.norm(point)) <= self.planner.numeric_distance_tol_m:
            return 1
        angle = math.atan2(float(point[1]), float(point[0]))
        vertices = self.coverage[1:]
        if self.sweep_direction == "CW":
            vertices = vertices[::-1]
        vertex_angles = np.arctan2(vertices[:, 1], vertices[:, 0])
        delta = np.abs((vertex_angles - angle + math.pi) % (2.0 * math.pi) - math.pi)
        return int(np.argmin(delta)) + 1

    def sector_rank(self, sector: int) -> int:
        if not 1 <= sector <= self.sector_count:
            raise ValueError(f"sector must be in 1..{self.sector_count}")
        if self.sweep_direction == "CCW":
            return sector - 1
        return self.sector_count - sector

    def rank_for_point(self, point: np.ndarray) -> int:
        return self.sector_rank(self.sector_for_point(point))

    def service_window(self, state: ChannelState, frontier_rank: int) -> ServiceWindow:
        certificate = state.certificate()
        sector = self.sector_for_point(certificate.center)
        source_rank = self.sector_rank(sector)
        relative = source_rank - frontier_rank
        current = source_rank == frontier_rank
        return ServiceWindow(
            sector=sector,
            source_rank=source_rank,
            relative_rank=relative,
            deadline=current,
            current_sector=current,
        )

    def is_forward_compatible(self, point: np.ndarray, frontier_rank: int) -> bool:
        point = np.asarray(point, float)
        if float(np.linalg.norm(point)) <= self.planner.numeric_distance_tol_m:
            return frontier_rank < 0
        rank = self.rank_for_point(point)
        if frontier_rank < 0:
            return rank == 0
        forward_delta = (rank - frontier_rank) % self.sector_count
        return forward_delta in {0, 1}

    def completion_stage(self, state: ChannelState) -> int:
        if state.safe_clear_point() is not None:
            return 0  # CLEARABLE
        if state.bearing_count >= 2:
            return 1  # ALMOST_LOCALIZED
        if state.bearing_count == 1:
            return 2  # ROUGHLY_LOCALIZED
        return 3  # NEWLY_FOUND

    def clip_to_arena(self, point: np.ndarray) -> np.ndarray:
        point = np.asarray(point, float)
        norm = float(np.linalg.norm(point))
        if norm <= self.physical.target_radius_m:
            return point.copy()
        return point * (self.physical.target_radius_m / norm)

    def forward_transverse_points(self, state: ChannelState) -> tuple[np.ndarray, ...]:
        certificate = state.certificate()
        rho = max(0.0, self.physical.reception_min_m - certificate.radius_m)
        if rho <= self.planner.numeric_distance_tol_m:
            return ()
        bearings = [obs for obs in state.history if obs.result == "direction"]
        if not bearings:
            return ()
        sensor = np.asarray(bearings[-1].position, float)
        direction = certificate.center - sensor
        norm = float(np.linalg.norm(direction))
        if norm <= self.planner.numeric_distance_tol_m:
            return ()
        normal = np.array([-direction[1], direction[0]], dtype=float) / norm
        # The full guaranteed transverse radius can cross into an adjacent
        # sector even though nearer points on the same transverse ray remain
        # both informative and forward-compatible.  Check a tiny fixed set
        # from near to far; this is a feasibility test, not a global score.
        return tuple(
            self.clip_to_arena(certificate.center + sign * fraction * rho * normal)
            for fraction in (0.05, 0.25, 0.5, 0.75, 1.0)
            for sign in (1.0, -1.0)
        )

    def choose_forward_transverse(
        self,
        state: ChannelState,
        current_position: np.ndarray,
        frontier_rank: int,
    ) -> np.ndarray | None:
        candidates = [
            point for point in self.forward_transverse_points(state)
            if self.is_forward_compatible(point, frontier_rank)
            and not state.already_measured(point)
        ]
        if not candidates:
            return None
        return candidates[0].copy()
