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
        coverage = ordered_points(
            rotation, reverse, self.planner.ring_radius_m
        )
        return RoutePlan(coverage, rotation, reverse)
