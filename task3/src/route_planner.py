"""Monotonic seven-point coverage routes for route-embedded control."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import PlannerConfig
from .coverage import choose_orientation, ordered_points


@dataclass(frozen=True)
class RouteLeg:
    """One immutable macro movement leg of the coverage backbone."""

    start: np.ndarray
    end: np.ndarray
    purpose: str
    coverage_target: int

    @property
    def length_m(self) -> float:
        return float(np.linalg.norm(self.end - self.start))


@dataclass(frozen=True)
class RoutePlan:
    coverage: np.ndarray
    rotation_deg: float
    reverse: bool

    @property
    def sweep_direction(self) -> str:
        return "CW" if self.reverse else "CCW"

    @property
    def first_vertex(self) -> np.ndarray:
        return self.coverage[1].copy()

    def legs(self) -> tuple[RouteLeg, ...]:
        return tuple(
            RouteLeg(
                self.coverage[index - 1].copy(),
                self.coverage[index].copy(),
                "coverage_sweep",
                index,
            )
            for index in range(1, len(self.coverage))
        )


class RoutePlanner:
    """Choose a first vertex and one direction, then never reverse it."""

    def __init__(self, planner: PlannerConfig = PlannerConfig()):
        self.planner = planner

    def plan(self, origin_bearings_deg: list[float]) -> RoutePlan:
        rotation, reverse = choose_orientation(
            origin_bearings_deg, self.planner.rotation_deg,
            self.planner.orientation_strategy,
        )
        if self.planner.coverage_ring_vertices != 6:
            # Generalized rings are experimental free-order covers. Choose a
            # bootstrap orientation using their actual radial rays, not a
            # hypothetical six-point geometry.
            import math
            count = self.planner.coverage_ring_vertices
            options = []
            for rotation_candidate in np.linspace(0., 360./count, 12, endpoint=False):
                angles = rotation_candidate + np.arange(count)*360./count
                separation = min((min(abs((b-a+180.)%360.-180.) for a in angles)
                                  for b in origin_bearings_deg), default=180.)
                for reverse_candidate in (False,True):
                    first = angles[-1] if reverse_candidate else angles[0]
                    quality = sum(abs(math.sin(math.radians(b-first))) for b in origin_bearings_deg)
                    options.append(((separation,quality,-rotation_candidate,-int(reverse_candidate)),
                                    float(rotation_candidate),reverse_candidate))
            _,rotation,reverse=max(options,key=lambda item:item[0])
        coverage = ordered_points(
            rotation, reverse, self.planner.ring_radius_m, self.planner.coverage_ring_vertices
        )
        return RoutePlan(coverage, rotation, reverse)
