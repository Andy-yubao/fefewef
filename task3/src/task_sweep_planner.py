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
    relative_sector: int
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
        point = np.asarray(point, float)
        if float(np.linalg.norm(point)) <= self.planner.numeric_distance_tol_m:
            return 1
        angle = math.atan2(float(point[1]), float(point[0]))
        vertex_angles = np.arctan2(self.coverage[1:, 1], self.coverage[1:, 0])
        delta = np.abs((vertex_angles - angle + math.pi) % (2.0 * math.pi) - math.pi)
        return int(np.argmin(delta)) + 1

    def service_window(self, state: ChannelState, next_vertex: int | None) -> ServiceWindow:
        certificate = state.certificate()
        sector = self.sector_for_point(certificate.center)
        if next_vertex is None:
            return ServiceWindow(sector, 0, True, True)
        # Conservatively include sectors touched by the certificate disk.  A
        # small fixed angular stencil is sufficient for the six broad wedges
        # and avoids treating a boundary-straddling source as safely future.
        angles = np.linspace(0.0, 2.0 * math.pi, 24, endpoint=False)
        boundary = certificate.center + certificate.radius_m * np.column_stack(
            (np.cos(angles), np.sin(angles))
        )
        sectors = {sector, *(self.sector_for_point(point) for point in boundary)}
        relative_values = [value - next_vertex for value in sectors]
        relative = min(relative_values)
        return ServiceWindow(
            sector=sector,
            relative_sector=relative,
            deadline=relative <= 0,
            current_sector=next_vertex in sectors,
        )

    def is_forward_compatible(self, point: np.ndarray, completed_sectors: set[int]) -> bool:
        point = np.asarray(point, float)
        if float(np.linalg.norm(point)) <= self.planner.numeric_distance_tol_m:
            return True
        return self.sector_for_point(point) not in completed_sectors

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
        return (
            self.clip_to_arena(certificate.center + rho * normal),
            self.clip_to_arena(certificate.center - rho * normal),
        )

    def choose_forward_transverse(
        self,
        state: ChannelState,
        current_position: np.ndarray,
        next_vertex: int | None,
        completed_sectors: set[int],
    ) -> np.ndarray | None:
        candidates = [
            point for point in self.forward_transverse_points(state)
            if self.is_forward_compatible(point, completed_sectors)
            and not state.already_measured(point)
        ]
        if not candidates:
            return None
        expected = next_vertex if next_vertex is not None else self.sector_count
        return min(
            candidates,
            key=lambda point: (
                abs(self.sector_for_point(point) - expected),
                float(np.linalg.norm(point - np.asarray(current_position, float))),
                float(point[0]),
                float(point[1]),
            ),
        ).copy()
