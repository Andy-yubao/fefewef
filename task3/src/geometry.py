"""Conservative cell geometry, safe enclosing circles, and fallback covers.

The hard feasible set is represented by a union of closed axis-aligned cells.
A cell is discarded only when an analytic bound proves that every point in it
violates an observation.  Thus discretization enlarges, rather than erodes, the
continuous feasible set.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable

import numpy as np
from scipy.spatial import ConvexHull, QhullError


TAU = 2.0 * math.pi


def angle_diff_rad(a: np.ndarray | float, b: float) -> np.ndarray:
    return (np.asarray(a) - b + math.pi) % TAU - math.pi


def bearing_deg(source: np.ndarray, target: np.ndarray) -> float:
    delta = np.asarray(target, float) - np.asarray(source, float)
    return float(math.degrees(math.atan2(float(delta[1]), float(delta[0]))) % 360.0)


def min_distance_to_cells(point: np.ndarray, centers: np.ndarray, half: float) -> np.ndarray:
    d = np.maximum(np.abs(centers - np.asarray(point, float)) - half, 0.0)
    return np.hypot(d[:, 0], d[:, 1])


def max_distance_to_cells(point: np.ndarray, centers: np.ndarray, half: float) -> np.ndarray:
    d = np.abs(centers - np.asarray(point, float)) + half
    return np.hypot(d[:, 0], d[:, 1])


@dataclass(frozen=True)
class CellGrid:
    centers: np.ndarray
    step_m: float
    target_radius_m: float

    @property
    def half_m(self) -> float:
        return self.step_m / 2.0

    @property
    def cell_radius_m(self) -> float:
        return self.step_m / math.sqrt(2.0)

    @classmethod
    def target_disk(cls, radius_m: float = 1800.0, step_m: float = 10.0) -> "CellGrid":
        # Centers tile the entire target bounding square. Boundary-intersecting
        # cells are retained using exact point-to-square distance.
        n = int(math.ceil(2.0 * radius_m / step_m))
        low = -n * step_m / 2.0
        vals = low + (np.arange(n) + 0.5) * step_m
        xx, yy = np.meshgrid(vals, vals, indexing="xy")
        all_centers = np.column_stack((xx.ravel(), yy.ravel()))
        half = step_m / 2.0
        min_d = min_distance_to_cells(np.zeros(2), all_centers, half)
        return cls(all_centers[min_d <= radius_m + 1e-9], step_m, radius_m)

    def all_mask(self) -> np.ndarray:
        return np.ones(len(self.centers), dtype=bool)

    def containing_cell_indices(self, point: np.ndarray, tol: float = 1e-9) -> np.ndarray:
        p = np.asarray(point, float)
        return np.flatnonzero(np.all(np.abs(self.centers - p) <= self.half_m + tol, axis=1))

    def direction_keep_mask(
        self,
        sensor: np.ndarray,
        measured_deg: float,
        bearing_error_deg: float = 1.0,
        max_range_m: float = 1500.0,
        min_range_m: float = 5.0,
        angle_tol_deg: float = 1e-6,
        distance_tol_m: float = 1e-7,
    ) -> np.ndarray:
        """Cells that may intersect the bounded annular bearing sector."""
        sensor = np.asarray(sensor, float)
        centers = self.centers
        min_d = min_distance_to_cells(sensor, centers, self.half_m)
        max_d = max_distance_to_cells(sensor, centers, self.half_m)
        delta = centers - sensor
        d_center = np.hypot(delta[:, 0], delta[:, 1])
        cell_r = self.cell_radius_m
        angular_pad = np.full(len(centers), math.pi)
        outside = d_center > cell_r
        angular_pad[outside] = np.arcsin(np.minimum(1.0, cell_r / d_center[outside]))
        center_angle = np.arctan2(delta[:, 1], delta[:, 0])
        measured = math.radians(measured_deg % 360.0)
        angular_ok = np.abs(angle_diff_rad(center_angle, measured)) <= (
            math.radians(bearing_error_deg + angle_tol_deg) + angular_pad
        )
        range_ok = (min_d <= max_range_m + distance_tol_m) & (max_d > min_range_m - distance_tol_m)
        return angular_ok & range_ok

    def no_signal_keep_mask(self, sensor: np.ndarray, guaranteed_radius_m: float,
                            distance_tol_m: float = 1e-7) -> np.ndarray:
        """Delete only cells proved wholly inside the closed must-receive disk."""
        max_d = max_distance_to_cells(np.asarray(sensor, float), self.centers, self.half_m)
        return max_d > guaranteed_radius_m + distance_tol_m

    def failed_clear_keep_mask(self, point: np.ndarray, clear_radius_m: float,
                               distance_tol_m: float = 1e-7) -> np.ndarray:
        max_d = max_distance_to_cells(np.asarray(point, float), self.centers, self.half_m)
        return max_d > clear_radius_m + distance_tol_m

    def cell_corners(self, mask: np.ndarray) -> np.ndarray:
        c = self.centers[np.asarray(mask, bool)]
        if len(c) == 0:
            return np.empty((0, 2), float)
        h = self.half_m
        offsets = np.array([[-h, -h], [-h, h], [h, -h], [h, h]])
        return (c[:, None, :] + offsets[None, :, :]).reshape(-1, 2)

    def representative_points(self, mask: np.ndarray, max_points: int = 200,
                              seed: int = 0) -> np.ndarray:
        points = self.centers[np.asarray(mask, bool)]
        if len(points) <= max_points:
            return points.copy()
        rng = np.random.default_rng(seed)
        idx = np.sort(rng.choice(len(points), max_points, replace=False))
        return points[idx]


@dataclass(frozen=True)
class EnclosingCircle:
    center: np.ndarray
    radius_m: float
    max_validation_error_m: float = 0.0


def _circle_two(a: np.ndarray, b: np.ndarray) -> tuple[np.ndarray, float]:
    center = (a + b) / 2.0
    return center, float(np.linalg.norm(a - center))


def _circle_three(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> tuple[np.ndarray, float] | None:
    ax, ay = a
    bx, by = b
    cx, cy = c
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = ax * ax + ay * ay, bx * bx + by * by, cx * cx + cy * cy
    ux = (a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d
    uy = (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d
    center = np.array([ux, uy], float)
    return center, float(np.linalg.norm(center - a))


def minimum_enclosing_circle(points: np.ndarray, seed: int = 0) -> EnclosingCircle:
    """Expected-linear exact finite-point MEC with an explicit validation bump."""
    pts = np.unique(np.asarray(points, float), axis=0)
    if len(pts) == 0:
        return EnclosingCircle(np.array([math.nan, math.nan]), math.inf)
    if len(pts) > 3:
        try:
            pts = pts[ConvexHull(pts).vertices]
        except QhullError:
            pass
    rng = np.random.default_rng(seed)
    pts = pts[rng.permutation(len(pts))]
    center = pts[0].copy()
    radius = 0.0
    eps = 1e-9
    for i, p in enumerate(pts):
        if np.linalg.norm(p - center) <= radius + eps:
            continue
        center, radius = p.copy(), 0.0
        for j in range(i):
            q = pts[j]
            if np.linalg.norm(q - center) <= radius + eps:
                continue
            center, radius = _circle_two(p, q)
            for k in range(j):
                r = pts[k]
                if np.linalg.norm(r - center) <= radius + eps:
                    continue
                candidate = _circle_three(p, q, r)
                if candidate is None:
                    pairs = [_circle_two(p, q), _circle_two(p, r), _circle_two(q, r)]
                    center, radius = min(
                        (x for x in pairs if all(np.linalg.norm(z - x[0]) <= x[1] + eps for z in (p, q, r))),
                        key=lambda x: x[1],
                    )
                else:
                    center, radius = candidate
    distances = np.linalg.norm(pts - center, axis=1)
    observed = float(np.max(distances))
    bump = max(0.0, observed - radius) + 1e-8
    return EnclosingCircle(center, radius + bump, max(0.0, observed - radius))


def safe_mec_for_cells(grid: CellGrid, mask: np.ndarray, seed: int = 0) -> EnclosingCircle:
    """MEC of the union's convex hull; all cell corners are included and checked."""
    corners = grid.cell_corners(mask)
    return minimum_enclosing_circle(corners, seed=seed)


def fallback_cover_centers(grid: CellGrid, mask: np.ndarray, clear_radius_m: float = 20.0) -> np.ndarray:
    """Finite seamless cover: every retained cell is covered by its own center."""
    if grid.cell_radius_m > clear_radius_m:
        raise ValueError("grid cells are too large for a cell-center clear cover")
    return grid.centers[np.asarray(mask, bool)].copy()


def nearest_neighbor_order(points: np.ndarray, start: np.ndarray) -> np.ndarray:
    remaining = np.asarray(points, float).copy()
    if len(remaining) <= 1:
        return remaining
    order: list[np.ndarray] = []
    current = np.asarray(start, float)
    while len(remaining):
        idx = int(np.argmin(np.linalg.norm(remaining - current, axis=1)))
        current = remaining[idx]
        order.append(current.copy())
        remaining = np.delete(remaining, idx, axis=0)
    return np.asarray(order)
