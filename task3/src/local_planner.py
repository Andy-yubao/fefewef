"""Local measurement candidates and hard/probabilistic shortlist scoring."""

from __future__ import annotations

from dataclasses import dataclass
import math

import numpy as np
from scipy.optimize import linprog
from scipy.spatial import ConvexHull, QhullError

from .channel_state import ChannelState, Observation
from .config import PhysicalConfig, PlannerConfig
from .geometry import angle_diff_rad, min_distance_to_cells


@dataclass(frozen=True)
class LocalCandidate:
    point: np.ndarray
    source: str
    guaranteed_reception: bool
    expected_radius_m: float
    p90_radius_m: float
    no_signal_probability: float
    geometry_quality: float
    fim_e_score: float


def _unique_points(items: list[tuple[np.ndarray, str]], ndigits: int = 6) -> list[tuple[np.ndarray, str]]:
    seen: set[tuple[float, float]] = set()
    result: list[tuple[np.ndarray, str]] = []
    for point, source in items:
        p = np.asarray(point, float)
        if not np.all(np.isfinite(p)):
            continue
        key = tuple(np.round(p, ndigits))
        if key not in seen:
            seen.add(key)
            result.append((p, source))
    return result


def convex_chebyshev_center(points: np.ndarray) -> np.ndarray:
    """Chebyshev center of the convex hull enclosing a possibly nonconvex set."""
    points = np.unique(np.asarray(points, float), axis=0)
    if len(points) < 3:
        return np.mean(points, axis=0)
    try:
        hull = ConvexHull(points)
    except QhullError:
        return np.mean(points, axis=0)
    # scipy hull equations: normal*x + offset <= 0 inside.
    normals = hull.equations[:, :2]
    offsets = hull.equations[:, 2]
    norm = np.linalg.norm(normals, axis=1)
    a = np.column_stack((normals, norm))
    b = -offsets
    objective = np.array([0.0, 0.0, -1.0])
    answer = linprog(objective, A_ub=a, b_ub=b, bounds=[(None, None), (None, None), (0.0, None)], method="highs")
    return answer.x[:2] if answer.success else np.mean(points, axis=0)


def boundary_representatives(points: np.ndarray, count: int = 8) -> np.ndarray:
    points = np.unique(np.asarray(points, float), axis=0)
    if len(points) <= count:
        return points
    try:
        hull = ConvexHull(points)
        boundary = points[hull.vertices]
    except QhullError:
        boundary = points
    idx = np.linspace(0, len(boundary) - 1, min(count, len(boundary)), dtype=int)
    return boundary[idx]


def _first_direction(channel: ChannelState) -> Observation | None:
    return next((o for o in channel.history if o.result == "direction"), None)


def _geometry_quality(sensor1: np.ndarray, candidate: np.ndarray, targets: np.ndarray) -> np.ndarray:
    v1 = sensor1 - targets
    v2 = candidate - targets
    d1 = np.linalg.norm(v1, axis=1)
    d2 = np.linalg.norm(v2, axis=1)
    cross = np.abs(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0])
    sin_angle = cross / np.maximum(d1 * d2, 1e-9)
    return sin_angle / np.sqrt(np.maximum(d1 * d2, 10000.0))


def _fim_e_score(channel: ChannelState, candidate: np.ndarray, targets: np.ndarray) -> float:
    """Mean E-optimal score for ranking only (never used as a hard bound)."""
    sensors = [np.asarray(o.position, float) for o in channel.history if o.result == "direction"]
    sensors.append(np.asarray(candidate, float))
    values = []
    for target in targets:
        information = np.zeros((2, 2), float)
        for sensor in sensors:
            d = target - sensor
            r2 = max(float(d @ d), 1e-9)
            h = np.array([-d[1], d[0]]) / r2
            information += np.outer(h, h)
        values.append(float(np.linalg.eigvalsh(information)[0]))
    return float(np.mean(values)) if values else 0.0


def _predicted_radii(channel: ChannelState, candidate: np.ndarray, particles: np.ndarray,
                     planner: PlannerConfig, physical: PhysicalConfig) -> tuple[np.ndarray, float]:
    first = _first_direction(channel)
    current_radius = channel.certificate().radius_m
    if first is None or len(particles) == 0:
        return np.full(max(1, len(particles)), current_radius), 0.0
    sensor1 = np.asarray(first.position, float)
    d2 = np.linalg.norm(particles - candidate, axis=1)
    # Ordering prior only: deterministic per-particle reception radii span the
    # legal range. Hard state updates never use these samples.
    ranks = np.arange(len(particles))
    radius_samples = physical.reception_min_m + (
        (ranks * 0.6180339887498949 + channel.channel * 0.1732050807568877) % 1.0
    ) * (physical.reception_max_m - physical.reception_min_m)
    detected = d2 <= radius_samples
    v1 = sensor1 - particles
    v2 = candidate - particles
    d1 = np.linalg.norm(v1, axis=1)
    cross = np.abs(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0])
    sin_angle = cross / np.maximum(d1 * d2, 1e-9)
    # First-order bounded-line intersection width; this is an ordering proxy,
    # never a hard confidence region or a clearing certificate.
    angular = math.radians(physical.bearing_error_deg)
    intersect_width = angular * np.sqrt(d1 * d1 + d2 * d2) / np.maximum(sin_angle, 0.02)
    localized = np.maximum(channel.grid.cell_radius_m, np.minimum(current_radius, intersect_width))
    predicted = np.where(detected, localized, current_radius)
    return predicted, float(np.mean(~detected))


def _hard_worst_radius(channel: ChannelState, candidate: np.ndarray,
                       support: np.ndarray, guaranteed: bool) -> float:
    """Non-probabilistic worst-branch proxy for the rolling-hard ablation."""
    current = channel.certificate().radius_m
    first = _first_direction(channel)
    if first is None or len(support) == 0 or not guaranteed:
        return current
    sensor1 = np.asarray(first.position, float)
    v1 = sensor1 - support
    v2 = candidate - support
    d1 = np.linalg.norm(v1, axis=1)
    d2 = np.linalg.norm(v2, axis=1)
    cross = np.abs(v1[:, 0] * v2[:, 1] - v1[:, 1] * v2[:, 0])
    sin_angle = cross / np.maximum(d1 * d2, 1e-9)
    angular = math.radians(channel.physical.bearing_error_deg)
    widths = angular * np.sqrt(d1 * d1 + d2 * d2) / np.maximum(sin_angle, 0.02)
    return float(max(channel.grid.cell_radius_m, min(current, np.max(widths))))


def generate_local_candidates(
    channel: ChannelState,
    current_position: np.ndarray,
    coverage_points: np.ndarray,
    unvisited_coverage: list[int],
    use_particles: bool,
) -> list[LocalCandidate]:
    """Generate all required candidate families, then annotate a short list."""
    cfg, phys = channel.planner, channel.physical
    feasible = channel.grid.centers[channel.possible]
    if len(feasible) == 0:
        return []
    mec = channel.certificate()
    cheb = convex_chebyshev_center(feasible)
    centroid = np.mean(feasible, axis=0)
    raw: list[tuple[np.ndarray, str]] = [
        (mec.center, "mec_center"),
        (cheb, "chebyshev_center"),
        (centroid, "centroid"),
    ]
    raw.extend((p, "boundary") for p in boundary_representatives(feasible))
    first = _first_direction(channel)
    if first is not None:
        sensor1 = np.asarray(first.position, float)
        line = centroid - sensor1
        norm = np.linalg.norm(line)
        if norm > 1e-9:
            normal = np.array([-line[1], line[0]]) / norm
            raw.append((centroid + cfg.local_offset_m * normal, "geometry_orthogonal"))
            raw.append((centroid - cfg.local_offset_m * normal, "geometry_orthogonal"))
    for angle in np.linspace(0.0, 2.0 * math.pi, cfg.candidate_ring_count, endpoint=False):
        raw.append((mec.center + cfg.local_offset_m * np.array([math.cos(angle), math.sin(angle)]), "candidate_ring"))
    raw.extend((coverage_points[i], "coverage_reuse") for i in unvisited_coverage)
    raw = [(p, name) for p, name in _unique_points(raw) if not channel.already_measured(p)]
    if not raw:
        return []

    corners = channel.grid.cell_corners(channel.possible)
    particles = channel.grid.representative_points(
        channel.possible,
        max_points=cfg.particle_count if use_particles else min(24, cfg.particle_count),
        seed=cfg.seed + 37 * channel.channel + channel.bearing_count,
    )
    annotated: list[LocalCandidate] = []
    e_scores: list[float] = []
    first_sensor = np.asarray(first.position, float) if first is not None else np.asarray(current_position, float)
    for point, source in raw:
        max_distance = float(np.max(np.linalg.norm(corners - point, axis=1)))
        guaranteed = max_distance <= phys.reception_min_m + cfg.numeric_distance_tol_m
        predicted, p_no = _predicted_radii(channel, point, particles, cfg, phys)
        quality = float(np.mean(_geometry_quality(first_sensor, point, particles))) if len(particles) else 0.0
        e_scores.append(_fim_e_score(channel, point, particles))
        if not use_particles:
            hard_radius = _hard_worst_radius(channel, point, particles, guaranteed)
            predicted = np.array([hard_radius])
            p_no = 0.0 if guaranteed else 1.0
        annotated.append(LocalCandidate(
            point=point,
            source=source,
            guaranteed_reception=guaranteed,
            expected_radius_m=float(np.mean(predicted)),
            p90_radius_m=float(np.quantile(predicted, cfg.risk_quantile)),
            no_signal_probability=p_no,
            geometry_quality=quality,
            fim_e_score=e_scores[-1],
        ))

    # Explicitly include the winners of the three task-2 families.
    geometry = max(annotated, key=lambda c: c.geometry_quality)
    e_index = int(np.argmax(np.asarray(e_scores) / np.maximum(
        1.0, np.array([np.linalg.norm(c.point - current_position) for c in annotated]) / phys.speed_mps
    )))
    e_opt = annotated[e_index]
    expected = min(annotated, key=lambda c: c.expected_radius_m)
    winner_keys = {
        tuple(np.round(geometry.point, 6)): "task2_geometry",
        tuple(np.round(e_opt.point, 6)): "task2_e_optimal",
        tuple(np.round(expected.point, 6)): "task2_expected_diameter",
    }
    final: list[LocalCandidate] = []
    for c in annotated:
        key = tuple(np.round(c.point, 6))
        if key in winner_keys:
            c = LocalCandidate(c.point, f"{c.source}+{winner_keys[key]}", c.guaranteed_reception,
                               c.expected_radius_m, c.p90_radius_m, c.no_signal_probability,
                               c.geometry_quality, c.fim_e_score)
        final.append(c)
    # Guarantee-reception points are preferred whenever at least one exists.
    guaranteed = [c for c in final if c.guaranteed_reception]
    return guaranteed if guaranteed else final


def select_by_family(candidates: list[LocalCandidate], family: str,
                     current_position: np.ndarray, planner: PlannerConfig) -> LocalCandidate:
    if not candidates:
        raise ValueError("empty local candidate set")
    travel = lambda c: float(np.linalg.norm(c.point - current_position)) / 5.0
    if family == "geometry":
        return max(candidates, key=lambda c: c.geometry_quality - 1e-5 * travel(c))
    if family == "e_optimal":
        return max(candidates, key=lambda c: c.fim_e_score / max(1.0, travel(c)))
    if family == "expected_diameter":
        return min(candidates, key=lambda c: c.expected_radius_m + 0.05 * travel(c))
    # Shortlist re-ranking by expected finish plus a P90 tail penalty.
    return min(candidates, key=lambda c: (
        travel(c) + 5.0 + c.expected_radius_m / 5.0
        + planner.tail_weight * c.p90_radius_m / 5.0
        + c.no_signal_probability * 60.0
    ))
