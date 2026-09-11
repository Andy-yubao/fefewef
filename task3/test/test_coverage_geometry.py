"""Regression tests for the seven-point deterministic coverage certificate."""

import math

import numpy as np

from coverage_geometry import (
    GUARANTEED_RECEPTION_RADIUS_M,
    RING_RADIUS_M,
    TARGET_RADIUS_M,
    analytic_coverage_bound,
    coverage_centers,
    dense_polar_verification,
    nearest_center_distance,
    worst_boundary_points,
)


def test_center_layout() -> None:
    points = coverage_centers()
    assert points.shape == (7, 2)
    assert np.allclose(points[0], (0.0, 0.0))
    assert np.allclose(np.linalg.norm(points[1:], axis=1), RING_RADIUS_M)


def test_analytic_bound_is_below_guaranteed_radius() -> None:
    result = analytic_coverage_bound()
    assert math.isclose(result["worst_distance_m"], 968.9015717043836)
    assert result["worst_distance_m"] < GUARANTEED_RECEPTION_RADIUS_M
    assert result["minimum_margin_m"] > 31.0


def test_boundary_midpoints_attain_analytic_worst_case() -> None:
    worst_points = worst_boundary_points()
    distances = nearest_center_distance(worst_points[:, 0], worst_points[:, 1])
    assert np.allclose(distances, analytic_coverage_bound()["worst_distance_m"])


def test_dense_polar_search_finds_no_hole() -> None:
    result = dense_polar_verification(radial_step_m=2.0, angular_step_deg=0.25)
    assert result["sampled_worst_distance_m"] < GUARANTEED_RECEPTION_RADIUS_M
    assert math.isclose(
        result["sampled_worst_distance_m"],
        analytic_coverage_bound()["worst_distance_m"],
        abs_tol=1e-9,
    )


def test_every_boundary_angle_is_covered() -> None:
    angles = np.linspace(0.0, 2.0 * math.pi, 100_001)
    x = TARGET_RADIUS_M * np.cos(angles)
    y = TARGET_RADIUS_M * np.sin(angles)
    assert float(np.max(nearest_center_distance(x, y))) < GUARANTEED_RECEPTION_RADIUS_M
