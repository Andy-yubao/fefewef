from __future__ import annotations

import math
from pathlib import Path
import sys

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.q1 import (  # noqa: E402
    Arc,
    BearingObservation,
    ClippedRegion,
    Point,
    clip_polygon_with_disk,
    clipped_region_diameter,
    bearing_wedge_halfplanes,
    locate_polygon,
    norm,
    polygon_diameter,
)


def bearing(sensor: Point, target: Point) -> float:
    return math.degrees(math.atan2(target.y - sensor.y, target.x - sensor.x)) % 360.0


def observations(sensors: list[Point], target: Point) -> list[BearingObservation]:
    return [BearingObservation(sensor, bearing(sensor, target)) for sensor in sensors]


def area(polygon: list[Point]) -> float:
    return 0.5 * abs(
        sum(
            first.x * second.y - first.y * second.x
            for first, second in zip(polygon, polygon[1:] + polygon[:1])
        )
    )


def test_case_1_standard_two_station_intersection() -> None:
    target = Point(100.0, 300.0)
    polygon = locate_polygon(observations([Point(-600.0, -400.0), Point(700.0, -300.0)], target))
    assert len(polygon) == 4
    assert polygon_diameter(polygon).distance > 0.0


def test_case_2_third_station_shrinks_region() -> None:
    target = Point(100.0, 300.0)
    two = locate_polygon(observations([Point(-600.0, -400.0), Point(700.0, -300.0)], target))
    three = locate_polygon(
        observations([Point(-600.0, -400.0), Point(700.0, -300.0), Point(700.0, 700.0)], target)
    )
    assert area(three) < area(two)
    assert polygon_diameter(three).distance < polygon_diameter(two).distance


def test_case_3_target_disk_inactive() -> None:
    target = Point(100.0, 300.0)
    polygon = locate_polygon(observations([Point(-600.0, -400.0), Point(700.0, -300.0)], target))
    region = clip_polygon_with_disk(polygon)
    assert not region.circle_active
    assert not region.arcs
    assert clipped_region_diameter(region).distance == pytest.approx(polygon_diameter(polygon).distance)


def test_case_4_active_disk_arc_and_exact_diameter() -> None:
    # This rectangle crosses x=1800.  The clipped boundary contains a circle arc.
    polygon = [Point(1500.0, -600.0), Point(2100.0, -600.0), Point(2100.0, 600.0), Point(1500.0, 600.0)]
    region = clip_polygon_with_disk(polygon)
    result = clipped_region_diameter(region)
    assert region.circle_active
    assert region.arcs
    assert all(norm(point) <= 1800.0 + 1.0e-6 for point in (result.first, result.second))
    # One diagonal joins a rectangle corner to the opposite circle/edge crossing.
    circle_crossing_x = math.sqrt(1800.0**2 - 600.0**2)
    expected = math.hypot(circle_crossing_x - 1500.0, 1200.0)
    assert result.distance == pytest.approx(expected, abs=1.0e-6)


def test_case_4c_bearing_intersection_triggers_target_disk() -> None:
    target = Point(1780.0, 0.0)
    polygon = locate_polygon(observations([Point(500.0, -800.0), Point(500.0, 800.0)], target))
    region = clip_polygon_with_disk(polygon)
    result = clipped_region_diameter(region)
    assert region.circle_active and region.arcs
    assert max(norm(vertex) for vertex in polygon) > 1800.0
    assert all(norm(point) <= 1800.0 + 1.0e-6 for point in (result.first, result.second))


def test_case_4b_antipodal_points_inside_arc_interiors() -> None:
    # A strip-clipped disk whose upper/lower semicircle interiors contain a diameter.
    polygon = [Point(-2000.0, -200.0), Point(2000.0, -200.0), Point(2000.0, 200.0), Point(-2000.0, 200.0)]
    region = clip_polygon_with_disk(polygon)
    assert clipped_region_diameter(region).distance == pytest.approx(3600.0, abs=1.0e-6)


def test_case_5_jung_equilateral_counterexample() -> None:
    side = 120.0
    triangle = [Point(0.0, 0.0), Point(side, 0.0), Point(side / 2.0, side * math.sqrt(3.0) / 2.0)]
    assert polygon_diameter(triangle).distance == pytest.approx(side)
    assert 2.0 * side / math.sqrt(3.0) > side


def test_full_disk_special_case() -> None:
    polygon = [Point(-2000.0, -2000.0), Point(2000.0, -2000.0), Point(2000.0, 2000.0), Point(-2000.0, 2000.0)]
    region = clip_polygon_with_disk(polygon)
    assert region.arcs == (Arc(0.0, 2.0 * math.pi, 1800.0, True),)
    assert clipped_region_diameter(region).distance == pytest.approx(3600.0)


def test_zero_degree_wraparound_uses_vector_sides() -> None:
    lower, upper = bearing_wedge_halfplanes(BearingObservation(Point(0.0, 0.0), 0.0))
    assert lower.contains(Point(100.0, 0.0)) and upper.contains(Point(100.0, 0.0))
    assert not (lower.contains(Point(-100.0, 0.0)) and upper.contains(Point(-100.0, 0.0)))
