"""论文第 3、5、6 节共用的二维几何核心（仅依赖 NumPy）。"""
from __future__ import annotations

from dataclasses import dataclass
import math
from itertools import combinations
from typing import Iterable, Sequence

import numpy as np

EPS = 1e-8
TAU = 2.0 * math.pi


@dataclass(frozen=True)
class Observation:
    station: tuple[float, float]
    bearing_deg: float
    error_deg: float = 1.0


@dataclass(frozen=True)
class HalfPlane:
    """闭半平面 a*x+b*y<=c。"""

    a: float
    b: float
    c: float

    def contains(self, point: Sequence[float], tol: float = EPS) -> bool:
        x, y = point
        scale = max(1.0, abs(self.c), math.hypot(self.a, self.b) * math.hypot(x, y))
        return self.a * x + self.b * y <= self.c + tol * scale


@dataclass(frozen=True)
class Arc:
    """以原点为圆心的逆时针圆弧；end 可以大于 2*pi。"""

    start: float
    end: float
    radius: float
    full: bool = False


@dataclass(frozen=True)
class DiskClippedRegion:
    polygon: np.ndarray
    radius: float
    segments: tuple[tuple[np.ndarray, np.ndarray], ...]
    arcs: tuple[Arc, ...]
    circle_active: bool


@dataclass(frozen=True)
class Circle:
    center: np.ndarray
    radius: float


def bearing_halfplanes(obs: Observation) -> tuple[HalfPlane, HalfPlane]:
    """把一次 ±error 示向变成两个前向半平面。"""
    if not 0.0 < obs.error_deg < 90.0:
        raise ValueError("error_deg must be in (0, 90)")
    sx, sy = obs.station
    theta = math.radians(obs.bearing_deg % 360.0)
    error = math.radians(obs.error_deg)
    lower = (math.cos(theta - error), math.sin(theta - error))
    upper = (math.cos(theta + error), math.sin(theta + error))
    return (
        HalfPlane(lower[1], -lower[0], lower[1] * sx - lower[0] * sy),
        HalfPlane(-upper[1], upper[0], -upper[1] * sx + upper[0] * sy),
    )


def _line_intersection(p: HalfPlane, q: HalfPlane) -> np.ndarray | None:
    det = p.a * q.b - q.a * p.b
    if abs(det) <= 1e-12:
        return None
    return np.array([(p.c * q.b - q.c * p.b) / det,
                     (p.a * q.c - q.a * p.c) / det])


def convex_hull(points: Iterable[Sequence[float]]) -> np.ndarray:
    """Andrew 单调链；返回逆时针顶点且不重复首点。"""
    pts = sorted({(float(p[0]), float(p[1])) for p in points})
    if len(pts) <= 1:
        return np.asarray(pts, dtype=float)

    def cross(o, a, b):
        return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

    lower: list[tuple[float, float]] = []
    upper: list[tuple[float, float]] = []
    for p in pts:
        while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= EPS:
            lower.pop()
        lower.append(p)
    for p in reversed(pts):
        while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= EPS:
            upper.pop()
        upper.append(p)
    return np.asarray(lower[:-1] + upper[:-1], dtype=float)


def intersect_bearings(observations: Sequence[Observation]) -> np.ndarray:
    """枚举边界交点得到有界硬可行多边形；不充分时明确报错。"""
    planes = [plane for obs in observations for plane in bearing_halfplanes(obs)]
    normal_angles = sorted(math.atan2(p.b, p.a) % TAU for p in planes)
    gaps = [b - a for a, b in zip(normal_angles, normal_angles[1:])]
    if normal_angles:
        gaps.append(normal_angles[0] + TAU - normal_angles[-1])
    if len(planes) < 3 or max(gaps, default=TAU) >= math.pi - 1e-10:
        raise ValueError("bearing intersection is unbounded; take another independent observation")
    candidates = []
    for p, q in combinations(planes, 2):
        x = _line_intersection(p, q)
        if x is not None and all(h.contains(x) for h in planes):
            candidates.append(x)
    hull = convex_hull(candidates)
    if len(hull) < 3:
        raise ValueError("bearing intersection is empty or degenerate")
    return hull


def _polygon_halfplanes(polygon: np.ndarray) -> list[HalfPlane]:
    planes = []
    for start, end in zip(polygon, np.roll(polygon, -1, axis=0)):
        dx, dy = end - start
        planes.append(HalfPlane(dy, -dx, dy * start[0] - dx * start[1]))
    return planes


def _segment_disk_interval(a: np.ndarray, b: np.ndarray, radius: float) -> tuple[float, float] | None:
    d = b - a
    aa, bb = float(d @ d), float(2.0 * (a @ d))
    cc = float(a @ a - radius * radius)
    disc = bb * bb - 4.0 * aa * cc
    if disc < -EPS:
        return (0.0, 1.0) if np.linalg.norm(a) <= radius and np.linalg.norm(b) <= radius else None
    root = math.sqrt(max(0.0, disc))
    lo, hi = max(0.0, (-bb - root) / (2.0 * aa)), min(1.0, (-bb + root) / (2.0 * aa))
    return (lo, hi) if hi - lo > EPS else None


def clip_polygon_with_disk(polygon: np.ndarray, radius: float = 1800.0) -> DiskClippedRegion:
    """精确保留 P 与目标圆交集的线段/解析圆弧边界。"""
    polygon = np.asarray(polygon, dtype=float)
    if len(polygon) < 3 or radius <= 0:
        raise ValueError("a non-degenerate polygon and positive radius are required")
    if np.all(np.linalg.norm(polygon, axis=1) <= radius + EPS):
        segs = tuple((a.copy(), b.copy()) for a, b in zip(polygon, np.roll(polygon, -1, axis=0)))
        return DiskClippedRegion(polygon, radius, segs, (), False)

    planes = _polygon_halfplanes(polygon)
    segments: list[tuple[np.ndarray, np.ndarray]] = []
    angles: list[float] = []
    for a, b in zip(polygon, np.roll(polygon, -1, axis=0)):
        interval = _segment_disk_interval(a, b, radius)
        if interval:
            lo, hi = interval
            segments.append((a + lo * (b - a), a + hi * (b - a)))
        d = b - a
        aa, bb = float(d @ d), float(2.0 * (a @ d))
        cc = float(a @ a - radius * radius)
        disc = bb * bb - 4.0 * aa * cc
        if disc >= -EPS:
            root = math.sqrt(max(0.0, disc))
            for t in ((-bb - root) / (2.0 * aa), (-bb + root) / (2.0 * aa)):
                if -EPS <= t <= 1.0 + EPS:
                    x = a + min(1.0, max(0.0, t)) * d
                    if all(h.contains(x) for h in planes):
                        angles.append(math.atan2(x[1], x[0]) % TAU)

    angles = sorted(angles)
    angles = [a for i, a in enumerate(angles) if i == 0 or a - angles[i - 1] > 1e-10]
    arcs: list[Arc] = []
    if not angles:
        if all(h.contains((radius, 0.0)) for h in planes):
            arcs.append(Arc(0.0, TAU, radius, True))
    else:
        for start, end in zip(angles, angles[1:] + [angles[0] + TAU]):
            middle = 0.5 * (start + end)
            x = radius * np.array([math.cos(middle), math.sin(middle)])
            if all(h.contains(x) for h in planes):
                arcs.append(Arc(start, end, radius))
    if not segments and not arcs:
        raise ValueError("polygon and target disk have no positive-area intersection")
    return DiskClippedRegion(polygon, radius, tuple(segments), tuple(arcs), True)


def polygon_diameter(points: np.ndarray) -> tuple[float, np.ndarray, np.ndarray]:
    pts = np.asarray(points, dtype=float)
    if not len(pts):
        raise ValueError("diameter requires points")
    best = (0.0, pts[0], pts[0])
    for i, j in combinations(range(len(pts)), 2):
        d = float(np.linalg.norm(pts[i] - pts[j]))
        if d > best[0]:
            best = (d, pts[i], pts[j])
    return best


def _on_arc(angle: float, arc: Arc) -> bool:
    if arc.full:
        return True
    angle %= TAU
    while angle < arc.start - 1e-10:
        angle += TAU
    return angle <= arc.end + 1e-10


def region_diameter(region: DiskClippedRegion) -> tuple[float, np.ndarray, np.ndarray]:
    """检查线段端点、端点反向圆周点和圆弧对径点。"""
    if not region.circle_active:
        return polygon_diameter(region.polygon)
    if any(a.full for a in region.arcs):
        p = np.array([region.radius, 0.0])
        return 2.0 * region.radius, p, -p
    boundary = [p for segment in region.segments for p in segment]
    for arc in region.arcs:
        boundary.extend(region.radius * np.array([math.cos(t), math.sin(t)]) for t in (arc.start, arc.end))
    boundary = np.unique(np.round(np.asarray(boundary), 10), axis=0)
    best = polygon_diameter(boundary)
    for p in boundary:
        angle = math.atan2(-p[1], -p[0]) % TAU
        if any(_on_arc(angle, arc) for arc in region.arcs):
            q = region.radius * np.array([math.cos(angle), math.sin(angle)])
            d = float(np.linalg.norm(p - q))
            if d > best[0]:
                best = (d, p, q)
    for i, a in enumerate(region.arcs):
        for b in region.arcs[i:]:
            for shift in range(-2, 3):
                lo = max(a.start, b.start - math.pi + shift * TAU)
                hi = min(a.end, b.end - math.pi + shift * TAU)
                if lo <= hi + 1e-10:
                    t = 0.5 * (lo + hi)
                    p = region.radius * np.array([math.cos(t), math.sin(t)])
                    return max(best, (2.0 * region.radius, p, -p), key=lambda item: item[0])
    return best


def _circle2(a: np.ndarray, b: np.ndarray) -> Circle:
    center = (a + b) / 2.0
    return Circle(center, float(np.linalg.norm(a - center)))


def _circle3(a: np.ndarray, b: np.ndarray, c: np.ndarray) -> Circle | None:
    ax, ay = a; bx, by = b; cx, cy = c
    d = 2.0 * (ax * (by - cy) + bx * (cy - ay) + cx * (ay - by))
    if abs(d) < 1e-12:
        return None
    a2, b2, c2 = a @ a, b @ b, c @ c
    center = np.array([(a2 * (by - cy) + b2 * (cy - ay) + c2 * (ay - by)) / d,
                       (a2 * (cx - bx) + b2 * (ax - cx) + c2 * (bx - ax)) / d])
    return Circle(center, float(np.linalg.norm(center - a)))


def minimum_enclosing_circle(points: np.ndarray, seed: int = 0) -> Circle:
    """随机增量最小包围圆；固定 seed，最后显式校验并上调舍入误差。"""
    pts = np.unique(np.asarray(points, dtype=float), axis=0)
    if not len(pts):
        raise ValueError("minimum enclosing circle requires points")
    pts = pts[np.random.default_rng(seed).permutation(len(pts))]
    circle = Circle(pts[0].copy(), 0.0)
    for i, p in enumerate(pts):
        if np.linalg.norm(p - circle.center) <= circle.radius + EPS:
            continue
        circle = Circle(p.copy(), 0.0)
        for j, q in enumerate(pts[:i]):
            if np.linalg.norm(q - circle.center) <= circle.radius + EPS:
                continue
            circle = _circle2(p, q)
            for r in pts[:j]:
                if np.linalg.norm(r - circle.center) <= circle.radius + EPS:
                    continue
                candidate = _circle3(p, q, r)
                if candidate is None:
                    pairs = (_circle2(p, q), _circle2(p, r), _circle2(q, r))
                    candidate = min((c for c in pairs if all(
                        np.linalg.norm(x - c.center) <= c.radius + EPS for x in (p, q, r))),
                                    key=lambda c: c.radius)
                circle = candidate
    required = float(np.max(np.linalg.norm(pts - circle.center, axis=1)))
    return Circle(circle.center, max(circle.radius, required) + 1e-9)


def cell_corners(centers: np.ndarray, step: float) -> np.ndarray:
    offsets = 0.5 * step * np.array([[-1, -1], [-1, 1], [1, -1], [1, 1]])
    return (np.asarray(centers)[:, None, :] + offsets[None, :, :]).reshape(-1, 2)
