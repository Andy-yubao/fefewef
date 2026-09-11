"""Q1 bounded-bearing intersection and exact disk-clipped diameter geometry.

The implementation is deliberately small: the number of observations in Q1 is
tiny, so half-plane boundary pairs and diameter candidates are enumerated.
Circle arcs are represented analytically; they are never replaced by a sampled
polygon in the numerical result.
"""

from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Iterable, Sequence


TAU = 2.0 * math.pi


@dataclass(frozen=True)
class GeometryTolerance:
    absolute: float = 1.0e-9
    feasibility: float = 1.0e-7
    angle: float = 1.0e-10
    dedup: float = 1.0e-7


TOL = GeometryTolerance()


@dataclass(frozen=True)
class Point:
    x: float
    y: float

    def __add__(self, other: "Point") -> "Point":
        return Point(self.x + other.x, self.y + other.y)

    def __sub__(self, other: "Point") -> "Point":
        return Point(self.x - other.x, self.y - other.y)

    def __mul__(self, scalar: float) -> "Point":
        return Point(self.x * scalar, self.y * scalar)


@dataclass(frozen=True)
class BearingObservation:
    sensor: Point
    bearing_deg: float
    error_deg: float = 1.0


@dataclass(frozen=True)
class HalfPlane:
    """Closed half-plane a*x + b*y <= c."""

    a: float
    b: float
    c: float

    def contains(self, point: Point, tol: GeometryTolerance = TOL) -> bool:
        scale = max(1.0, abs(self.c), math.hypot(self.a, self.b) * norm(point))
        return self.a * point.x + self.b * point.y <= self.c + tol.feasibility * scale


@dataclass(frozen=True)
class Segment:
    start: Point
    end: Point


@dataclass(frozen=True)
class Arc:
    """Counter-clockwise circle arc; end may exceed 2*pi."""

    start_angle: float
    end_angle: float
    radius: float
    full_circle: bool = False


@dataclass(frozen=True)
class ClippedRegion:
    polygon: tuple[Point, ...]
    radius: float
    circle_active: bool
    segments: tuple[Segment, ...]
    arcs: tuple[Arc, ...]


@dataclass(frozen=True)
class DiameterResult:
    distance: float
    first: Point
    second: Point


def cross(first: Point, second: Point) -> float:
    return first.x * second.y - first.y * second.x


def dot(first: Point, second: Point) -> float:
    return first.x * second.x + first.y * second.y


def norm(point: Point) -> float:
    return math.hypot(point.x, point.y)


def distance(first: Point, second: Point) -> float:
    return norm(first - second)


def unit(angle_rad: float) -> Point:
    return Point(math.cos(angle_rad), math.sin(angle_rad))


def point_on_circle(angle_rad: float, radius: float) -> Point:
    direction = unit(angle_rad)
    return direction * radius


def bearing_wedge_halfplanes(observation: BearingObservation) -> tuple[HalfPlane, HalfPlane]:
    """Return the two half-planes bounding one forward bearing wedge.

    For v = X-S and lower/upper boundary unit vectors u_l/u_u, the
    convention is cross(u_l, v) >= 0 and cross(u_u, v) <= 0.  Sine/cosine
    make this valid across the 0/360 degree seam without angle comparisons.
    """

    if not 0.0 < observation.error_deg < 90.0:
        raise ValueError("error_deg must lie strictly between 0 and 90 degrees")
    centre = math.radians(observation.bearing_deg % 360.0)
    error = math.radians(observation.error_deg)
    lower = unit(centre - error)
    upper = unit(centre + error)
    sx, sy = observation.sensor.x, observation.sensor.y
    lower_side = HalfPlane(lower.y, -lower.x, lower.y * sx - lower.x * sy)
    upper_side = HalfPlane(-upper.y, upper.x, -upper.y * sx + upper.x * sy)
    return lower_side, upper_side


def observations_to_halfplanes(
    observations: Iterable[BearingObservation],
) -> list[HalfPlane]:
    halfplanes: list[HalfPlane] = []
    for observation in observations:
        halfplanes.extend(bearing_wedge_halfplanes(observation))
    return halfplanes


def _line_intersection(first: HalfPlane, second: HalfPlane) -> Point | None:
    determinant = first.a * second.b - second.a * first.b
    scale = max(1.0, math.hypot(first.a, first.b) * math.hypot(second.a, second.b))
    if abs(determinant) <= TOL.absolute * scale:
        return None
    return Point(
        (first.c * second.b - second.c * first.b) / determinant,
        (first.a * second.c - second.a * first.c) / determinant,
    )


def _deduplicate(points: Iterable[Point]) -> list[Point]:
    result: list[Point] = []
    for point in points:
        if all(distance(point, existing) > TOL.dedup for existing in result):
            result.append(point)
    return result


def convex_hull(points: Sequence[Point]) -> list[Point]:
    """Return a counter-clockwise hull without repeating its first vertex."""

    ordered = sorted(_deduplicate(points), key=lambda point: (point.x, point.y))
    if len(ordered) <= 1:
        return ordered

    def build(sequence: Iterable[Point]) -> list[Point]:
        chain: list[Point] = []
        for point in sequence:
            while len(chain) >= 2 and cross(chain[-1] - chain[-2], point - chain[-1]) <= TOL.absolute:
                chain.pop()
            chain.append(point)
        return chain

    lower = build(ordered)
    upper = build(reversed(ordered))
    return lower[:-1] + upper[:-1]


def _bounded_by_normals(halfplanes: Sequence[HalfPlane]) -> bool:
    angles = sorted(math.atan2(halfplane.b, halfplane.a) % TAU for halfplane in halfplanes)
    if len(angles) < 3:
        return False
    gaps = [angles[index + 1] - angles[index] for index in range(len(angles) - 1)]
    gaps.append(angles[0] + TAU - angles[-1])
    return max(gaps) < math.pi - TOL.angle


def intersect_halfplanes(halfplanes: Sequence[HalfPlane]) -> list[Point]:
    """Intersect a small set of half-planes by exact boundary-pair enumeration.

    Complexity is O(h^3), which is preferable here to a delicate general-purpose
    half-plane-intersection implementation because h=2m is small.
    """

    if not _bounded_by_normals(halfplanes):
        raise ValueError("half-plane intersection is unbounded; add a geometrically independent observation")
    candidates: list[Point] = []
    for first_index, first in enumerate(halfplanes):
        for second in halfplanes[first_index + 1 :]:
            point = _line_intersection(first, second)
            if point is not None and all(halfplane.contains(point) for halfplane in halfplanes):
                candidates.append(point)
    hull = convex_hull(candidates)
    if len(hull) < 3:
        raise ValueError("half-plane intersection is empty or degenerate")
    return hull


def locate_polygon(observations: Sequence[BearingObservation]) -> list[Point]:
    return intersect_halfplanes(observations_to_halfplanes(observations))


def polygon_halfplanes(polygon: Sequence[Point]) -> list[HalfPlane]:
    """Convert a counter-clockwise convex polygon to inward edge constraints."""

    result: list[HalfPlane] = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        edge = end - start
        # cross(edge, X-start) >= 0  <=>  edge.y*x-edge.x*y <= constant
        result.append(HalfPlane(edge.y, -edge.x, edge.y * start.x - edge.x * start.y))
    return result


def _segment_circle_parameters(start: Point, end: Point, radius: float) -> list[float]:
    direction = end - start
    qa = dot(direction, direction)
    qb = 2.0 * dot(start, direction)
    qc = dot(start, start) - radius * radius
    discriminant = qb * qb - 4.0 * qa * qc
    scale = max(1.0, qb * qb, abs(4.0 * qa * qc))
    if discriminant < -TOL.feasibility * scale:
        return []
    discriminant = max(0.0, discriminant)
    root = math.sqrt(discriminant)
    values = [(-qb - root) / (2.0 * qa), (-qb + root) / (2.0 * qa)]
    return sorted(value for value in values if -TOL.absolute <= value <= 1.0 + TOL.absolute)


def _clipped_edge(start: Point, end: Point, radius: float) -> Segment | None:
    direction = end - start
    qa = dot(direction, direction)
    qb = 2.0 * dot(start, direction)
    qc = dot(start, start) - radius * radius
    discriminant = qb * qb - 4.0 * qa * qc
    if discriminant < 0.0:
        if norm(start) <= radius + TOL.feasibility and norm(end) <= radius + TOL.feasibility:
            return Segment(start, end)
        return None
    root = math.sqrt(max(0.0, discriminant))
    inside_start = (-qb - root) / (2.0 * qa)
    inside_end = (-qb + root) / (2.0 * qa)
    low = max(0.0, inside_start)
    high = min(1.0, inside_end)
    if high - low <= TOL.absolute:
        return None
    return Segment(start + direction * low, start + direction * high)


def _inside_polygon(point: Point, halfplanes: Sequence[HalfPlane]) -> bool:
    return all(halfplane.contains(point) for halfplane in halfplanes)


def clip_polygon_with_disk(polygon: Sequence[Point], radius: float = 1800.0) -> ClippedRegion:
    """Construct the exact line-segment/circular-arc boundary of P intersect disk."""

    if radius <= 0.0 or len(polygon) < 3:
        raise ValueError("a positive radius and a non-degenerate polygon are required")
    polygon_tuple = tuple(polygon)
    if all(norm(vertex) <= radius + TOL.feasibility for vertex in polygon):
        segments = tuple(Segment(start, end) for start, end in zip(polygon, polygon[1:] + polygon[:1]))
        return ClippedRegion(polygon_tuple, radius, False, segments, ())

    constraints = polygon_halfplanes(polygon)
    segments: list[Segment] = []
    intersection_angles: list[float] = []
    for start, end in zip(polygon, polygon[1:] + polygon[:1]):
        clipped = _clipped_edge(start, end, radius)
        if clipped is not None:
            segments.append(clipped)
        direction = end - start
        for parameter in _segment_circle_parameters(start, end, radius):
            point = start + direction * min(1.0, max(0.0, parameter))
            if _inside_polygon(point, constraints):
                intersection_angles.append(math.atan2(point.y, point.x) % TAU)

    angles: list[float] = []
    for angle in sorted(intersection_angles):
        if not angles or abs(angle - angles[-1]) > TOL.angle:
            angles.append(angle)
    if len(angles) > 1 and TAU - angles[-1] + angles[0] <= TOL.angle:
        angles[0] = 0.5 * (angles[0] + angles[-1] - TAU) % TAU
        angles.pop()

    arcs: list[Arc] = []
    if not angles:
        if _inside_polygon(Point(radius, 0.0), constraints):
            arcs.append(Arc(0.0, TAU, radius, True))
    else:
        extended = angles + [angles[0] + TAU]
        for start_angle, end_angle in zip(extended, extended[1:]):
            midpoint = point_on_circle(0.5 * (start_angle + end_angle), radius)
            if _inside_polygon(midpoint, constraints):
                arcs.append(Arc(start_angle, end_angle, radius))

    if not segments and not arcs:
        raise ValueError("polygon and target disk do not intersect with positive area")
    return ClippedRegion(polygon_tuple, radius, True, tuple(segments), tuple(arcs))


def polygon_diameter(polygon: Sequence[Point]) -> DiameterResult:
    if not polygon:
        raise ValueError("diameter requires at least one point")
    best = DiameterResult(0.0, polygon[0], polygon[0])
    for first_index, first in enumerate(polygon):
        for second in polygon[first_index + 1 :]:
            candidate = distance(first, second)
            if candidate > best.distance:
                best = DiameterResult(candidate, first, second)
    return best


def _angle_on_arc(angle: float, arc: Arc) -> bool:
    if arc.full_circle:
        return True
    adjusted = angle % TAU
    while adjusted < arc.start_angle - TOL.angle:
        adjusted += TAU
    return adjusted <= arc.end_angle + TOL.angle


def _boundary_points(region: ClippedRegion) -> list[Point]:
    points: list[Point] = []
    for segment in region.segments:
        points.extend((segment.start, segment.end))
    for arc in region.arcs:
        if not arc.full_circle:
            points.extend(
                (point_on_circle(arc.start_angle, arc.radius), point_on_circle(arc.end_angle, arc.radius))
            )
    return _deduplicate(points)


def _antipodal_angle(first: Arc, second: Arc) -> float | None:
    if first.full_circle or second.full_circle:
        return 0.0
    for shift in range(-2, 3):
        second_start = second.start_angle - math.pi + shift * TAU
        second_end = second.end_angle - math.pi + shift * TAU
        low = max(first.start_angle, second_start)
        high = min(first.end_angle, second_end)
        if low <= high + TOL.angle:
            return 0.5 * (low + high)
    return None


def clipped_region_diameter(region: ClippedRegion) -> DiameterResult:
    """Exact finite-candidate diameter for a convex line/arc boundary."""

    if not region.circle_active:
        return polygon_diameter(region.polygon)
    if any(arc.full_circle for arc in region.arcs):
        return DiameterResult(2.0 * region.radius, Point(region.radius, 0.0), Point(-region.radius, 0.0))

    points = _boundary_points(region)
    if not points:
        raise ValueError("clipped region has no boundary candidates")
    best = polygon_diameter(points)

    # For fixed p, squared distance to R*u(theta) is maximized at theta=arg(-p).
    for point in points:
        opposite_angle = math.atan2(-point.y, -point.x) % TAU
        for arc in region.arcs:
            if _angle_on_arc(opposite_angle, arc):
                other = point_on_circle(opposite_angle, arc.radius)
                candidate = distance(point, other)
                if candidate > best.distance:
                    best = DiameterResult(candidate, point, other)

    # Two circular arcs attain their maximum internally only at antipodal points.
    for first_index, first_arc in enumerate(region.arcs):
        for second_arc in region.arcs[first_index:]:
            angle = _antipodal_angle(first_arc, second_arc)
            if angle is not None:
                first = point_on_circle(angle, first_arc.radius)
                second = point_on_circle(angle + math.pi, second_arc.radius)
                candidate = distance(first, second)
                if candidate > best.distance:
                    best = DiameterResult(candidate, first, second)
    return best


def solve_q1(
    observations: Sequence[BearingObservation], radius: float = 1800.0
) -> tuple[list[Point], ClippedRegion, DiameterResult]:
    polygon = locate_polygon(observations)
    region = clip_polygon_with_disk(polygon, radius)
    return polygon, region, clipped_region_diameter(region)

