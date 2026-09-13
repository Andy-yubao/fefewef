from __future__ import annotations

import math

from task4.geometry import Point, distance

from .clear_probe import ClearProbeStrategy


class CertifiedClearProbeStrategy(ClearProbeStrategy):
    """Replace lattice probes only with a local triangular coverage certificate."""

    name = "certified_clear_probe"
    coverage_radius_m = 1000.0

    def __init__(
        self,
        grid_spacing: float = 600.0,
        grid_half_extent: float = 1800.0,
        lattice_spacing: float = 735.0,
        replacement_distance_m: float = 400.0,
        max_replaced_waypoints: int = 2,
    ):
        super().__init__(
            grid_spacing,
            grid_half_extent,
            lattice_spacing,
            replacement_distance_m,
            max_replaced_waypoints,
        )
        self._original_points = set(self._search_waypoints())
        self._removed_points: set[Point] = set()
        self._protected_points: set[Point] = set()

    def _lattice_neighbors(self, point: Point) -> list[Point]:
        tolerance = max(1e-6, self.lattice_spacing * 1e-8)
        neighbors = [
            candidate
            for candidate in self._original_points
            if abs(distance(point, candidate) - self.lattice_spacing) <= tolerance
        ]
        return sorted(
            neighbors,
            key=lambda candidate: math.atan2(candidate[1] - point[1], candidate[0] - point[0]),
        )

    @staticmethod
    def _inside_convex(point: Point, polygon: list[Point]) -> bool:
        signs = []
        for first, second in zip(polygon, polygon[1:] + polygon[:1]):
            cross = (second[0] - first[0]) * (point[1] - first[1]) - (
                second[1] - first[1]
            ) * (point[0] - first[0])
            if abs(cross) > 1e-7:
                signs.append(cross > 0)
        return not signs or all(sign == signs[0] for sign in signs)

    def _certifies_replacement(self, clear_point: Point, candidate: Point) -> bool:
        if candidate in self._protected_points:
            return False
        neighbors = self._lattice_neighbors(candidate)
        if len(neighbors) != 6:
            return False
        if any(neighbor in self._removed_points for neighbor in neighbors):
            return False
        if not self._inside_convex(clear_point, neighbors):
            return False
        return all(
            distance(clear_point, neighbor) < self.coverage_radius_m - 1e-7
            for neighbor in neighbors
        )

    def _choose_replacements(self, point, remaining):
        selected: list[Point] = []
        for candidate in sorted(remaining, key=lambda item: distance(point, item)):
            if len(selected) >= self.max_replaced_waypoints:
                break
            if not self._certifies_replacement(point, candidate):
                continue
            selected.append(candidate)
            self._removed_points.add(candidate)
            self._protected_points.update(self._lattice_neighbors(candidate))
        return selected
