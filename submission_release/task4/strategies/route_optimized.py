from __future__ import annotations

from task4.search_patterns import open_path_two_opt, triangular_lattice

from .opportunistic import OpportunisticClearStrategy


class RouteOptimizedStrategy(OpportunisticClearStrategy):
    """Follow a 2-opt coverage tour and always rejoin it after clear detours."""

    name = "route_optimized"

    def _search_waypoints(self) -> list[tuple[float, float]]:
        points = triangular_lattice(self.grid_half_extent, self.lattice_spacing)
        return open_path_two_opt(points)

    def _select_waypoint(self, remaining: list[tuple[float, float]]) -> tuple[float, float]:
        return remaining[0]

    def _next_waypoint(self, remaining: list[tuple[float, float]]):
        return remaining[0] if remaining else None
