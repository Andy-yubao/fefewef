"""Hard-set containment, MEC, and finite-cover tests."""

from __future__ import annotations

import math

import numpy as np

from task3.src.geometry import (CellGrid, fallback_cover_centers,
                                max_distance_to_cells,
                                minimum_enclosing_circle,
                                safe_mec_for_cells)


def test_direction_wraps_across_zero_and_keeps_truth() -> None:
    grid = CellGrid.target_disk(step_m=20.0)
    sensor = np.array([0.0, 0.0])
    truth = np.array([1000.0, -math.tan(math.radians(0.4)) * 1000.0])
    measured = 0.35  # sector straddles 0/360 degrees
    keep = grid.direction_keep_mask(sensor, measured)
    truth_cells = grid.containing_cell_indices(truth)
    assert len(truth_cells) > 0
    assert np.any(keep[truth_cells])


def test_random_legal_directions_never_remove_truth_cell() -> None:
    rng = np.random.default_rng(20260911)
    grid = CellGrid.target_disk(step_m=25.0)
    for _ in range(100):
        radius = rng.uniform(6.0, 1499.0)
        true_angle = rng.uniform(0.0, 2.0 * math.pi)
        truth = radius * np.array([math.cos(true_angle), math.sin(true_angle)])
        error = rng.uniform(-1.0, 1.0)
        measured = (math.degrees(true_angle) + error) % 360.0
        keep = grid.direction_keep_mask(np.zeros(2), measured)
        cells = grid.containing_cell_indices(truth)
        assert len(cells) and np.any(keep[cells])


def test_no_signal_deletes_only_wholly_inside_1000m_disk() -> None:
    grid = CellGrid.target_disk(step_m=20.0)
    keep = grid.no_signal_keep_mask(np.zeros(2), 1000.0)
    max_d = max_distance_to_cells(np.zeros(2), grid.centers, grid.half_m)
    assert not np.any(keep[max_d <= 1000.0])
    # Points well inside 1500 m but outside 1000 m must remain possible.
    band = (np.linalg.norm(grid.centers, axis=1) > 1100.0) & (np.linalg.norm(grid.centers, axis=1) < 1400.0)
    assert np.all(keep[band])


def test_minimum_enclosing_circle_known_triangle() -> None:
    points = np.array([[0.0, 0.0], [4.0, 0.0], [0.0, 3.0]])
    circle = minimum_enclosing_circle(points, seed=7)
    assert np.allclose(circle.center, [2.0, 1.5], atol=1e-7)
    assert math.isclose(circle.radius_m, 2.5, abs_tol=1e-6)
    assert np.all(np.linalg.norm(points - circle.center, axis=1) <= circle.radius_m)


def test_nonconvex_cell_union_has_safe_outer_mec() -> None:
    grid = CellGrid.target_disk(step_m=20.0)
    mask = np.zeros(len(grid.centers), dtype=bool)
    wanted = [(-30.0, -10.0), (-10.0, -10.0), (10.0, -10.0), (-30.0, 10.0), (-30.0, 30.0)]
    for point in wanted:
        idx = int(np.argmin(np.linalg.norm(grid.centers - point, axis=1)))
        mask[idx] = True
    circle = safe_mec_for_cells(grid, mask)
    corners = grid.cell_corners(mask)
    assert np.all(np.linalg.norm(corners - circle.center, axis=1) <= circle.radius_m + 1e-7)


def test_safe_clear_uses_mec_radius_not_diameter_shortcut() -> None:
    # Equilateral triangle has diameter 40 but circumradius 40/sqrt(3)>20.
    points = np.array([[0.0, 0.0], [40.0, 0.0], [20.0, 20.0 * math.sqrt(3.0)]])
    circle = minimum_enclosing_circle(points)
    assert math.isclose(np.max(np.linalg.norm(points[:, None] - points[None, :], axis=2)), 40.0)
    assert circle.radius_m > 20.0


def test_fallback_cell_centers_leave_no_cell_gap() -> None:
    grid = CellGrid.target_disk(step_m=25.0)
    mask = np.zeros(len(grid.centers), dtype=bool)
    mask[::137] = True
    centers = fallback_cover_centers(grid, mask, clear_radius_m=20.0)
    assert len(centers) == np.count_nonzero(mask)
    assert grid.cell_radius_m < 20.0
    for center in centers[:20]:
        offsets = np.array([[-grid.half_m, -grid.half_m], [-grid.half_m, grid.half_m],
                            [grid.half_m, -grid.half_m], [grid.half_m, grid.half_m]])
        assert np.max(np.linalg.norm(offsets, axis=1)) <= 20.0

