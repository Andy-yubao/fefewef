"""Seven-point guaranteed-search skeleton and its analytic certificate."""

from __future__ import annotations

import math
from dataclasses import dataclass

import numpy as np

from .config import PhysicalConfig, PlannerConfig


@dataclass(frozen=True)
class CoverageCertificate:
    centers: np.ndarray
    inner_voronoi_m: float
    boundary_midpoint_m: float
    worst_distance_m: float
    margin_m: float
    route_length_m: float

    @property
    def valid(self) -> bool:
        return self.margin_m > 0.0


def seven_points(rotation_deg: float = 0.0, ring_radius_m: float = 1200.0) -> np.ndarray:
    """Return the origin followed by adjacent counter-clockwise hexagon vertices."""
    theta = math.radians(rotation_deg) + np.arange(6) * math.pi / 3.0
    ring = np.column_stack((ring_radius_m * np.cos(theta), ring_radius_m * np.sin(theta)))
    return np.vstack((np.zeros((1, 2)), ring))


def analytic_certificate(
    physical: PhysicalConfig = PhysicalConfig(),
    planner: PlannerConfig = PlannerConfig(),
) -> CoverageCertificate:
    """Compute the exact sixfold-symmetry upper bound used in the proof."""
    count = planner.coverage_ring_vertices
    if not isinstance(count, int) or not 3 <= count <= 12:
        raise ValueError('coverage ring must have 3 through 12 vertices')
    half = math.pi / count
    ring = planner.ring_radius_m
    target = physical.target_radius_m
    inner = ring / (2.0 * math.cos(half))
    boundary = math.sqrt(target * target + ring * ring - 2.0 * target * ring * math.cos(half))
    worst = max(inner, boundary)
    centers = regular_coverage_points(planner.rotation_deg, ring, count)
    route = float(np.sum(np.linalg.norm(np.diff(centers, axis=0), axis=1)))
    return CoverageCertificate(
        centers=centers,
        inner_voronoi_m=inner,
        boundary_midpoint_m=boundary,
        worst_distance_m=worst,
        margin_m=physical.reception_min_m - worst,
        route_length_m=route,
    )


def _choose_sparse_orientation(
    bearings_deg: list[float], base_rotation_deg: float,
) -> tuple[float, bool]:
    """Choose a hexagon whose six radial rays avoid all origin bearings.

    Rotations separated by 60 degrees have the same covering set, so the
    sparse strategy keeps the canonical 12 rotation representatives used by
    the existing route interface.  The lexicographic score first protects
    against radial collinearity, then balances density over all six vertices,
    and finally keeps the initial search window light.
    """
    candidates: list[tuple[tuple[float, ...], float, bool]] = []
    for step in range(12):
        rotation = (base_rotation_deg + 5.0 * step) % 60.0
        angles = (rotation + np.arange(6) * 60.0) % 360.0
        distances = np.asarray([
            min(abs(((bearing - angle + 180.0) % 360.0) - 180.0) for angle in angles)
            for bearing in bearings_deg
        ])
        per_vertex = np.asarray([
            sum(max(0.0, 1.0 - abs(((bearing - angle + 180.0) % 360.0) - 180.0) / 30.0) ** 2
                for bearing in bearings_deg)
            for angle in angles
        ])
        for reverse in (False, True):
            first = float(angles[0] if not reverse else angles[-1])
            signed = np.asarray([
                ((bearing - first) % 360.0) if not reverse else ((first - bearing) % 360.0)
                for bearing in bearings_deg
            ])
            window_load = float(np.count_nonzero((signed <= 90.0) | (signed >= 330.0)))
            # A bearing outside [-30, +90] is not admitted until the sweep
            # reaches it.  Prefer the direction with fewer such delayed
            # bearings; the previous sparse-start version minimized
            # ``window_load`` and could strand a source for almost a full turn.
            delayed = (signed > 90.0) & (signed < 330.0)
            delayed_count = float(np.count_nonzero(delayed))
            delayed_angle = float(np.sum(np.maximum(0.0, signed[delayed] - 90.0)))
            first_density = float(per_vertex[0] if not reverse else per_vertex[-1])
            transverse_quality = float(sum(
                abs(math.sin(math.radians(first - bearing)))
                for bearing in bearings_deg
            ))
            score = (
                round(float(np.min(distances)), 9),
                -round(float(np.max(per_vertex)), 9),
                -round(float(np.sum(per_vertex)), 9),
                transverse_quality,
                -delayed_count,
                -delayed_angle,
                window_load,
                -first_density,
                -rotation,
                -float(reverse),
            )
            candidates.append((score, rotation, reverse))
    _score, rotation, reverse = max(candidates, key=lambda item: item[0])
    return rotation, reverse


def choose_orientation(
    first_bearings_deg: list[float], base_rotation_deg: float = 0.0,
    strategy: str = "transverse",
) -> tuple[float, bool]:
    """Choose a legal orientation without changing the coverage guarantee."""
    if not first_bearings_deg:
        return base_rotation_deg, False
    if strategy == "sparse_six":
        return _choose_sparse_orientation(first_bearings_deg, base_rotation_deg)
    if strategy != "transverse":
        raise ValueError(f"unknown orientation strategy: {strategy}")
    best: tuple[float, float, bool] | None = None
    for offset in np.linspace(0.0, 55.0, 12):
        rotation = (base_rotation_deg + float(offset)) % 60.0
        vertices = seven_points(rotation)[1:]
        angles = np.degrees(np.arctan2(vertices[:, 1], vertices[:, 0])) % 360.0
        # Favor vertices transverse to the origin bearings, so the backbone also localizes.
        quality = 0.0
        for bearing in first_bearings_deg:
            acute = np.abs(((angles - bearing + 90.0) % 180.0) - 90.0)
            quality += float(np.max(np.sin(np.radians(acute))))
        for reverse in (False, True):
            ordered = angles[::-1] if reverse else angles
            first_quality = sum(abs(math.sin(math.radians(float(ordered[0] - b)))) for b in first_bearings_deg)
            key = (quality + 0.05 * first_quality, -rotation, reverse)
            if best is None or key[0] > best[0]:
                best = key
    assert best is not None
    return (-best[1]) % 60.0, bool(best[2])


def regular_coverage_points(rotation_deg: float, ring_radius_m: float, count: int = 6) -> np.ndarray:
    if count == 6:
        return seven_points(rotation_deg, ring_radius_m)
    theta = math.radians(rotation_deg) + np.arange(count) * (2.0 * math.pi / count)
    return np.vstack((np.zeros((1, 2)),
                      np.column_stack((ring_radius_m*np.cos(theta),ring_radius_m*np.sin(theta)))))


def ordered_points(rotation_deg: float, reverse: bool, ring_radius_m: float = 1200.0,
                   ring_vertices: int = 6) -> np.ndarray:
    points = regular_coverage_points(rotation_deg, ring_radius_m, ring_vertices)
    if reverse:
        points = np.vstack((points[0], points[:0:-1]))
    return points


def covers_target_samples(points: np.ndarray, target_radius_m: float, receive_radius_m: float,
                          radial_n: int = 181, angular_n: int = 1440) -> float:
    """Dense diagnostic only; the analytic certificate remains authoritative."""
    radii = np.linspace(0.0, target_radius_m, radial_n)
    angles = np.linspace(0.0, 2.0 * math.pi, angular_n, endpoint=False)
    rr, aa = np.meshgrid(radii, angles, indexing="ij")
    xy = np.column_stack(((rr * np.cos(aa)).ravel(), (rr * np.sin(aa)).ravel()))
    nearest = np.min(np.linalg.norm(xy[:, None, :] - points[None, :, :], axis=2), axis=1)
    return float(receive_radius_m - np.max(nearest))
