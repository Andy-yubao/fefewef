from __future__ import annotations

from task4.search_patterns import triangular_lattice

from .deferred import DeferredCoverageStrategy


class LatticeDeferredStrategy(DeferredCoverageStrategy):
    """Deferred clearing over a sparser guarantee-preserving triangular lattice."""

    name = "lattice"

    def __init__(
        self,
        grid_spacing: float = 600.0,
        grid_half_extent: float = 1800.0,
        lattice_spacing: float = 760.0,
    ):
        super().__init__(grid_spacing, grid_half_extent)
        if not 0 < lattice_spacing < 1000:
            raise ValueError("lattice_spacing must be in (0, 1000) for the discovery guarantee")
        self.lattice_spacing = lattice_spacing

    def _search_waypoints(self) -> list[tuple[float, float]]:
        return triangular_lattice(self.grid_half_extent, self.lattice_spacing)
