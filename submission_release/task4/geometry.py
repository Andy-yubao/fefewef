from __future__ import annotations

import math
from typing import Iterable

Point = tuple[float, float]


def distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


def angle_delta_deg(a: float, b: float) -> float:
    return (a - b + 180.0) % 360.0 - 180.0


def bearing_deg(a: Point, b: Point) -> float:
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0])) % 360.0


def regular_circle_polygon(center: Point, radius: float, sides: int = 96, outer: bool = True) -> list[Point]:
    """Polygonal circle approximation; outer=True guarantees circle containment."""
    r = radius / math.cos(math.pi / sides) if outer else radius
    offset = math.pi / sides if outer else 0.0
    return [
        (center[0] + r * math.cos(offset + 2 * math.pi * i / sides),
         center[1] + r * math.sin(offset + 2 * math.pi * i / sides))
        for i in range(sides)
    ]


def _clip_halfplane(poly: list[Point], normal: Point, limit: float, eps: float = 1e-8) -> list[Point]:
    """Clip polygon to normal dot point <= limit."""
    if not poly:
        return []
    out: list[Point] = []
    for a, b in zip(poly, poly[1:] + poly[:1]):
        va = normal[0] * a[0] + normal[1] * a[1] - limit
        vb = normal[0] * b[0] + normal[1] * b[1] - limit
        ina, inb = va <= eps, vb <= eps
        if ina:
            out.append(a)
        if ina != inb:
            t = va / (va - vb)
            out.append((a[0] + t * (b[0] - a[0]), a[1] + t * (b[1] - a[1])))
    return _dedupe(out)


def _dedupe(poly: list[Point], eps: float = 1e-7) -> list[Point]:
    result: list[Point] = []
    for p in poly:
        if not result or distance(p, result[-1]) > eps:
            result.append(p)
    if len(result) > 1 and distance(result[0], result[-1]) <= eps:
        result.pop()
    return result


def clip_bearing_wedge(poly: list[Point], station: Point, measured_deg: float, error_deg: float = 1.01) -> list[Point]:
    low = math.radians(measured_deg - error_deg)
    high = math.radians(measured_deg + error_deg)
    u_low = (math.cos(low), math.sin(low))
    u_high = (math.cos(high), math.sin(high))
    # cross(u_low, p-station) >= 0 -> (u_low_y,-u_low_x).p <= same.station
    n1 = (u_low[1], -u_low[0])
    # cross(u_high, p-station) <= 0 -> (-u_high_y,u_high_x).p <= same.station
    n2 = (-u_high[1], u_high[0])
    poly = _clip_halfplane(poly, n1, n1[0] * station[0] + n1[1] * station[1])
    return _clip_halfplane(poly, n2, n2[0] * station[0] + n2[1] * station[1])


def clip_convex(poly: list[Point], clipper: list[Point]) -> list[Point]:
    """Intersect CCW convex polygons."""
    result = poly
    for a, b in zip(clipper, clipper[1:] + clipper[:1]):
        # Interior is left of edge: cross(edge,p-a)>=0.
        normal = (b[1] - a[1], a[0] - b[0])
        result = _clip_halfplane(result, normal, normal[0] * a[0] + normal[1] * a[1])
        if not result:
            break
    return result


def feasible_polygon(observations: Iterable[tuple[Point, float]], arena_radius: float = 1800.0) -> list[Point]:
    poly = regular_circle_polygon((0.0, 0.0), arena_radius, outer=True)
    for station, direction in observations:
        poly = clip_bearing_wedge(poly, station, direction)
        # A positive reading proves distance <= emitter radius <= 1500 m.
        poly = clip_convex(poly, regular_circle_polygon(station, 1500.0, outer=True))
        if not poly:
            break
    return poly


def polygon_centroid(poly: list[Point]) -> Point:
    if not poly:
        raise ValueError("empty polygon")
    area2 = 0.0
    cx = cy = 0.0
    for a, b in zip(poly, poly[1:] + poly[:1]):
        cross = a[0] * b[1] - b[0] * a[1]
        area2 += cross
        cx += (a[0] + b[0]) * cross
        cy += (a[1] + b[1]) * cross
    if abs(area2) < 1e-10:
        return (sum(p[0] for p in poly) / len(poly), sum(p[1] for p in poly) / len(poly))
    return (cx / (3.0 * area2), cy / (3.0 * area2))


def polygon_diameter(poly: list[Point]) -> float:
    return max((distance(a, b) for i, a in enumerate(poly) for b in poly[i + 1 :]), default=0.0)


def enclosing_center_radius(poly: list[Point]) -> tuple[Point, float]:
    """Exact minimum enclosing circle for a small convex vertex set (O(n^3))."""
    if not poly:
        raise ValueError("empty polygon")
    candidates: list[Point] = list(poly)
    for i, a in enumerate(poly):
        for b in poly[i + 1 :]:
            candidates.append(((a[0] + b[0]) / 2, (a[1] + b[1]) / 2))
    for i, a in enumerate(poly):
        for j in range(i + 1, len(poly)):
            b = poly[j]
            for c in poly[j + 1 :]:
                d = 2 * (a[0] * (b[1] - c[1]) + b[0] * (c[1] - a[1]) + c[0] * (a[1] - b[1]))
                if abs(d) < 1e-9:
                    continue
                aa, bb, cc = a[0] ** 2 + a[1] ** 2, b[0] ** 2 + b[1] ** 2, c[0] ** 2 + c[1] ** 2
                candidates.append(((aa * (b[1] - c[1]) + bb * (c[1] - a[1]) + cc * (a[1] - b[1])) / d,
                                   (aa * (c[0] - b[0]) + bb * (a[0] - c[0]) + cc * (b[0] - a[0])) / d))
    best_center = candidates[0]
    best_radius = math.inf
    for center in candidates:
        radius = max(distance(center, p) for p in poly)
        if radius < best_radius:
            best_center, best_radius = center, radius
    return best_center, best_radius


def serpentine_grid(half_extent: float = 1800.0, spacing: float = 600.0) -> list[Point]:
    n = round(2 * half_extent / spacing)
    coords = [-half_extent + i * spacing for i in range(n + 1)]
    route: list[Point] = []
    for row, y in enumerate(coords):
        xs = coords if row % 2 == 0 else list(reversed(coords))
        route.extend((x, y) for x in xs)
    return route
