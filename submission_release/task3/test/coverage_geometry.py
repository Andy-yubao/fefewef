"""Geometry and verification utilities for the seven-point coverage design."""

from __future__ import annotations

import math

import numpy as np


TARGET_RADIUS_M = 1800.0
GUARANTEED_RECEPTION_RADIUS_M = 1000.0
RING_RADIUS_M = 1200.0
OUTER_POINT_COUNT = 6


def coverage_centers(rotation_rad: float = 0.0) -> np.ndarray:
    """Return the origin followed by six equally spaced ring points."""
    angles = rotation_rad + np.arange(OUTER_POINT_COUNT) * math.pi / 3.0
    ring = np.column_stack(
        (RING_RADIUS_M * np.cos(angles), RING_RADIUS_M * np.sin(angles))
    )
    return np.vstack((np.zeros((1, 2)), ring))


def nearest_center_distance(
    x: np.ndarray,
    y: np.ndarray,
    centers: np.ndarray | None = None,
) -> np.ndarray:
    """Distance from every supplied point to its nearest coverage center."""
    centers = coverage_centers() if centers is None else np.asarray(centers, float)
    result = np.full(np.broadcast(x, y).shape, np.inf, dtype=float)
    for cx, cy in centers:
        result = np.minimum(result, np.hypot(x - cx, y - cy))
    return result


def analytic_coverage_bound() -> dict[str, float]:
    """Return exact worst-distance candidates after sixfold symmetry reduction.

    In a representative 60-degree sector, the nearest center is either the
    origin or the ring center on the sector bisector. The maximum is attained
    at a center/ring Voronoi vertex or at a target-boundary sector corner.
    """
    half_sector = math.pi / 6.0
    inner_voronoi_m = RING_RADIUS_M / (2.0 * math.cos(half_sector))
    boundary_midpoint_m = math.sqrt(
        TARGET_RADIUS_M**2
        + RING_RADIUS_M**2
        - 2.0
        * TARGET_RADIUS_M
        * RING_RADIUS_M
        * math.cos(half_sector)
    )
    worst_distance_m = max(inner_voronoi_m, boundary_midpoint_m)
    return {
        "inner_voronoi_m": inner_voronoi_m,
        "boundary_midpoint_m": boundary_midpoint_m,
        "worst_distance_m": worst_distance_m,
        "minimum_margin_m": GUARANTEED_RECEPTION_RADIUS_M - worst_distance_m,
    }


def worst_boundary_points(rotation_rad: float = 0.0) -> np.ndarray:
    """Return the six target-boundary points farthest from the centers."""
    angles = rotation_rad + math.pi / 6.0 + np.arange(6) * math.pi / 3.0
    return np.column_stack(
        (TARGET_RADIUS_M * np.cos(angles), TARGET_RADIUS_M * np.sin(angles))
    )


def dense_polar_verification(
    radial_step_m: float = 2.0,
    angular_step_deg: float = 0.25,
) -> dict[str, float]:
    """Numerically search the target disk for the largest nearest-center distance."""
    radii = np.arange(0.0, TARGET_RADIUS_M + radial_step_m / 2.0, radial_step_m)
    angles = np.deg2rad(
        np.arange(0.0, 360.0 + angular_step_deg / 2.0, angular_step_deg)
    )
    rr, tt = np.meshgrid(radii, angles, indexing="ij")
    xx = rr * np.cos(tt)
    yy = rr * np.sin(tt)
    distances = nearest_center_distance(xx, yy)
    flat_index = int(np.argmax(distances))
    ir, it = np.unravel_index(flat_index, distances.shape)
    return {
        "sampled_worst_distance_m": float(distances[ir, it]),
        "sampled_margin_m": float(
            GUARANTEED_RECEPTION_RADIUS_M - distances[ir, it]
        ),
        "sampled_radius_m": float(radii[ir]),
        "sampled_angle_deg": float(np.rad2deg(angles[it]) % 360.0),
        "sample_count": int(distances.size),
    }
