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
    half = math.pi / 6.0
    ring = planner.ring_radius_m
    target = physical.target_radius_m
    inner = ring / (2.0 * math.cos(half))
    boundary = math.sqrt(target * target + ring * ring - 2.0 * target * ring * math.cos(half))
    worst = max(inner, boundary)
    centers = seven_points(planner.rotation_deg, ring)
    route = float(np.sum(np.linalg.norm(np.diff(centers, axis=0), axis=1)))
    return CoverageCertificate(
        centers=centers,
        inner_voronoi_m=inner,
        boundary_midpoint_m=boundary,
        worst_distance_m=worst,
        margin_m=physical.reception_min_m - worst,
        route_length_m=route,
    )


def choose_orientation(first_bearings_deg: list[float], base_rotation_deg: float = 0.0) -> tuple[float, bool]:
    """Choose among 12 rotations and two traversal directions without changing coverage."""
    if not first_bearings_deg:
        return base_rotation_deg, False
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


def ordered_points(rotation_deg: float, reverse: bool, ring_radius_m: float = 1200.0) -> np.ndarray:
    points = seven_points(rotation_deg, ring_radius_m)
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

