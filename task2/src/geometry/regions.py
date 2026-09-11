"""Set-membership regions for bounded bearing error."""
from __future__ import annotations

import math
from typing import Iterable

import numpy as np
from shapely.geometry import Point, Polygon
from shapely import contains_xy

from ..config import PhysicalConfig
from .angles import angle_diff, bearing, intersection_angle


def disk(center=(0.0, 0.0), radius=1800.0, resolution=64):
    return Point(float(center[0]), float(center[1])).buffer(
        float(radius), quad_segs=max(8, int(resolution))
    )


def bearing_sector(sensor, measured_rad, error_rad, max_range, min_range=0.0,
                   resolution=32):
    """Closed annular sector compatible with one bounded bearing observation."""
    sx, sy = map(float, sensor)
    n = max(2, int(resolution))
    outer_angles = np.linspace(measured_rad - error_rad,
                               measured_rad + error_rad, n)
    outer = [(sx + max_range * math.cos(a), sy + max_range * math.sin(a))
             for a in outer_angles]
    if min_range <= 0:
        coords = [(sx, sy), *outer, (sx, sy)]
    else:
        inner_angles = outer_angles[::-1]
        inner = [(sx + min_range * math.cos(a), sy + min_range * math.sin(a))
                 for a in inner_angles]
        coords = [*outer, *inner, outer[0]]
    return Polygon(coords).buffer(0)


def first_feasible_region(sensor1, measured_rad, cfg=PhysicalConfig(),
                          reception_radius=None, resolution=64):
    """Target possible set after a normal first bearing measurement.

    If the individual reception radius is unknown, the conservative upper bound
    1500 m is used. The lower 5 m disk is excluded because it would yield `near`.
    """
    r = cfg.reception_max if reception_radius is None else reception_radius
    target = disk((0.0, 0.0), cfg.target_radius, resolution)
    sector = bearing_sector(sensor1, measured_rad,
                            math.radians(cfg.bearing_error_deg), r,
                            cfg.near_radius, resolution // 2)
    return target.intersection(sector).buffer(0)


def localization_region(sensors, measured_rads, cfg=PhysicalConfig(),
                        reception_radii=None, resolution=64):
    """Intersection region from normal bearing outcomes at all sensors."""
    region = disk((0.0, 0.0), cfg.target_radius, resolution)
    if reception_radii is None:
        reception_radii = [cfg.reception_max] * len(sensors)
    for s, a, r in zip(sensors, measured_rads, reception_radii):
        sector = bearing_sector(s, a, math.radians(cfg.bearing_error_deg),
                                r, cfg.near_radius, resolution // 2)
        region = region.intersection(sector)
        if region.is_empty:
            break
    return region.buffer(0)


def _coords_from_geometry(geom):
    if geom.is_empty:
        return np.empty((0, 2))
    hull = geom.convex_hull
    if hull.geom_type == "Point":
        return np.array([[hull.x, hull.y]])
    if hull.geom_type == "LineString":
        return np.asarray(hull.coords, dtype=float)
    return np.asarray(hull.exterior.coords[:-1], dtype=float)


def convex_diameter(geom):
    """Exact farthest vertex pair of the convex hull (small polygons)."""
    xy = _coords_from_geometry(geom)
    if len(xy) < 2:
        return 0.0
    # Sector-intersection hulls contain few vertices; vectorized all-pairs is
    # simpler and numerically safer than a rotating-calipers implementation.
    delta = xy[:, None, :] - xy[None, :, :]
    return float(np.sqrt(np.max(np.sum(delta * delta, axis=-1))))


def region_area_diameter(region):
    return float(region.area), convex_diameter(region)


def sample_region_grid(region, step=80.0, max_points=None, rng=None):
    """Approximately uniform deterministic grid samples from a region."""
    if region.is_empty:
        return np.empty((0, 2))
    xmin, ymin, xmax, ymax = region.bounds
    xs = np.arange(xmin + step / 2, xmax + 1e-9, step)
    ys = np.arange(ymin + step / 2, ymax + 1e-9, step)
    pts = np.array([(x, y) for y in ys for x in xs
                    if region.covers(Point(float(x), float(y)))], dtype=float)
    if len(pts) == 0:
        c = region.representative_point()
        pts = np.array([[c.x, c.y]], dtype=float)
    if max_points is not None and len(pts) > max_points:
        rng = np.random.default_rng(0) if rng is None else rng
        pts = pts[rng.choice(len(pts), max_points, replace=False)]
    return pts


def sample_region_random(region, n=80, rng=None):
    """Rejection samples uniformly with respect to region area."""
    if region.is_empty or n <= 0:
        return np.empty((0, 2))
    rng = np.random.default_rng(0) if rng is None else rng
    xmin, ymin, xmax, ymax = region.bounds
    accepted = []
    attempts = 0
    while sum(len(x) for x in accepted) < n and attempts < 200:
        batch = max(256, 4 * (n - sum(len(x) for x in accepted)))
        x = rng.uniform(xmin, xmax, batch)
        y = rng.uniform(ymin, ymax, batch)
        mask = contains_xy(region, x, y)
        if np.any(mask):
            accepted.append(np.column_stack([x[mask], y[mask]]))
        attempts += 1
    if not accepted:
        p = region.representative_point()
        return np.repeat([[p.x, p.y]], n, axis=0)
    return np.vstack(accepted)[:n]


def action_grid(cfg=PhysicalConfig(), step=250.0):
    vals = np.arange(-cfg.target_radius, cfg.target_radius + 1e-9, step)
    return np.array([(x, y) for x in vals for y in vals
                     if x * x + y * y <= cfg.target_radius ** 2 + 1e-9],
                    dtype=float)


def candidate_regions(sensor1, posterior_points, cfg=PhysicalConfig(),
                      step=250.0, radius_samples=None,
                      min_detection_probability=0.25,
                      min_median_abs_sin_angle=0.12):
    """Return action grid plus feasible/recommended masks and diagnostics.

    Feasible: at least one possible target can be received under R_max.
    Recommended: non-negligible detection probability and non-degenerate median
    intersection geometry. Candidate points are kept inside the target disk as
    a bounded, travel-efficient modeling choice (the simulator itself allows
    outside positions).
    """
    grid = action_grid(cfg, step)
    targets = np.asarray(posterior_points, dtype=float)
    if radius_samples is None:
        radius_samples = np.full(len(targets), cfg.reception_max)
    radius_samples = np.asarray(radius_samples, dtype=float)
    d = np.linalg.norm(grid[:, None, :] - targets[None, :, :], axis=2)
    detect = d <= radius_samples[None, :]
    near = d <= cfg.near_radius
    detection_probability = np.mean(detect, axis=1)
    direct_probability = np.mean(near, axis=1)
    ang = np.empty_like(d)
    for j, g in enumerate(targets):
        ang[:, j] = intersection_angle(sensor1, grid, g)
    median_sin = np.median(np.abs(np.sin(ang)), axis=1)
    feasible = np.any(d <= cfg.reception_max, axis=1)
    recommended = (feasible &
                   (detection_probability >= min_detection_probability) &
                   ((median_sin >= min_median_abs_sin_angle) |
                    (direct_probability > 0)))
    # Always provide a useful pool even in coarse-grid edge cases.
    if not np.any(recommended):
        score = detection_probability * (0.1 + median_sin)
        recommended[np.argsort(score)[-min(8, len(score)):]] = True
    return {
        "points": grid,
        "feasible": feasible,
        "recommended": recommended,
        "detection_probability": detection_probability,
        "direct_probability": direct_probability,
        "median_abs_sin_angle": median_sin,
    }
