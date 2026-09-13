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
    distance,
    locate_polygon,
    minimum_enclosing_circle_polygon,
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


def test_case_5_problem_hexagon_is_not_covered_by_its_diameter_circle() -> None:
    validation_target = Point(100.0, 300.0)
    sensors = [
        Point(713.63, 1193.59),
        Point(-939.50, 362.10),
        Point(590.63, -611.06),
    ]
    measured_bearings_deg = [235.05529, 356.78364, 117.85767]
    fixed_observations = [
        BearingObservation(sensor, angle, error_deg=1.0)
        for sensor, angle in zip(sensors, measured_bearings_deg)
    ]

    polygon = locate_polygon(fixed_observations)
    region = clip_polygon_with_disk(polygon)
    diameter = clipped_region_diameter(region)
    minimum_circle = minimum_enclosing_circle_polygon(polygon)

    assert len(polygon) == 6
    assert not region.circle_active
    assert diameter.distance == pytest.approx(43.3485304667, abs=1.0e-6)
    assert minimum_circle.center.x == pytest.approx(99.685371680, abs=1.0e-6)
    assert minimum_circle.center.y == pytest.approx(308.254040053, abs=1.0e-6)
    assert minimum_circle.radius == pytest.approx(23.0981169810, abs=1.0e-6)
    assert minimum_circle.support_vertex_indices == (0, 2, 3)
    assert 2.0 * minimum_circle.radius > diameter.distance + 2.8
    assert all(observation.error_deg == pytest.approx(1.0) for observation in fixed_observations)

    for observation in fixed_observations:
        lower = (observation.bearing_deg - observation.error_deg) % 360.0
        upper = (observation.bearing_deg + observation.error_deg) % 360.0
        assert (upper - lower) % 360.0 == pytest.approx(2.0)
        true_bearing = bearing(observation.sensor, validation_target)
        wrapped_error = (observation.bearing_deg - true_bearing + 180.0) % 360.0 - 180.0
        assert -1.0 <= wrapped_error <= 1.0

    diameter_center = (diameter.first + diameter.second) * 0.5
    diameter_radius = diameter.distance / 2.0
    assert distance(diameter.first, diameter_center) == pytest.approx(diameter_radius)
    assert distance(diameter.second, diameter_center) == pytest.approx(diameter_radius)
    outside_indices = tuple(
        index
        for index, vertex in enumerate(polygon)
        if distance(vertex, diameter_center) > diameter_radius + 1.0e-7
    )
    assert outside_indices == (1, 2)
    assert all(
        distance(vertex, minimum_circle.center)
        <= minimum_circle.radius + 1.0e-7
        for vertex in polygon
    )
    assert all(
        distance(first, second) > 1.0e-6
        for first, second in zip(polygon, polygon[1:] + polygon[:1])
    )


def test_minimum_enclosing_circle_degenerate_inputs() -> None:
    with pytest.raises(ValueError):
        minimum_enclosing_circle_polygon([])

    singleton = minimum_enclosing_circle_polygon([Point(2.0, -3.0)])
    assert singleton.center == Point(2.0, -3.0)
    assert singleton.radius == 0.0
    assert singleton.support_vertex_indices == (0,)

    collinear = minimum_enclosing_circle_polygon(
        [Point(-2.0, 0.0), Point(0.0, 0.0), Point(5.0, 0.0)]
    )
    assert collinear.center == Point(1.5, 0.0)
    assert collinear.radius == pytest.approx(3.5)
    assert collinear.support_vertex_indices == (0, 2)


def test_full_disk_special_case() -> None:
    polygon = [Point(-2000.0, -2000.0), Point(2000.0, -2000.0), Point(2000.0, 2000.0), Point(-2000.0, 2000.0)]
    region = clip_polygon_with_disk(polygon)
    assert region.arcs == (Arc(0.0, 2.0 * math.pi, 1800.0, True),)
    assert clipped_region_diameter(region).distance == pytest.approx(3600.0)


def test_zero_degree_wraparound_uses_vector_sides() -> None:
    lower, upper = bearing_wedge_halfplanes(BearingObservation(Point(0.0, 0.0), 0.0))
    assert lower.contains(Point(100.0, 0.0)) and upper.contains(Point(100.0, 0.0))
    assert not (lower.contains(Point(-100.0, 0.0)) and upper.contains(Point(-100.0, 0.0)))
