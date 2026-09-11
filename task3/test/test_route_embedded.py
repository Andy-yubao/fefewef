"""Minimal invariants for the route-embedded sweep architecture."""

from __future__ import annotations

import numpy as np
import pytest

from task3.src.channel_state import ChannelStatus, Observation, initialize_channels
from task3.src.config import PhysicalConfig, PlannerConfig
from task3.src.geometry import CellGrid
from task3.src.mock_simulator import MockSimulator, Scenario, Source
from task3.src.opportunity_planner import (
    EmbeddedEventKind,
    OpportunityPlanner,
    segment_disk_entry,
    segment_disk_interval,
)
from task3.src.route_embedded_controller import RouteEmbeddedController
from task3.src.route_planner import RouteLeg, RoutePlanner


def test_route_plan_is_one_monotonic_ring_order() -> None:
    route = RoutePlanner().plan([10.0, 115.0])
    legs = route.legs()
    assert [leg.coverage_target for leg in legs] == [1, 2, 3, 4, 5, 6]
    assert all(np.allclose(left.end, right.start) for left, right in zip(legs, legs[1:]))
    ring_angles = np.unwrap(np.arctan2(route.coverage[1:, 1], route.coverage[1:, 0]))
    increments = np.diff(ring_angles)
    assert np.all(increments > 0.0) or np.all(increments < 0.0)


def test_on_route_point_adds_no_geometric_distance() -> None:
    start = np.array([0.0, 0.0])
    end = np.array([10.0, 0.0])
    hit = segment_disk_entry(start, end, np.array([5.0, 0.0]), 0.0)
    assert hit is not None
    point, fraction = hit
    assert fraction == pytest.approx(0.5)
    assert np.linalg.norm(point - start) + np.linalg.norm(end - point) == pytest.approx(10.0)
    assert segment_disk_interval(start, end, np.array([5.0, 0.0]), 2.0) == pytest.approx((0.3, 0.7))


def test_route_crossing_certified_clear_region_produces_clear() -> None:
    physical = PhysicalConfig()
    planner = PlannerConfig(grid_step_m=5.0)
    grid = CellGrid.target_disk(physical.target_radius_m, planner.grid_step_m)
    channels = initialize_channels(grid, physical, planner)
    state = channels[1]
    state.status = ChannelStatus.FOUND
    state.possible[:] = False
    state.possible[grid.containing_cell_indices(np.array([0.0, 0.0]))] = True
    leg = RouteLeg(np.array([-50.0, 0.0]), np.array([50.0, 0.0]), "test", 1)
    events = OpportunityPlanner(physical, planner).events(leg, channels)
    assert len(events) == 1
    assert events[0].kind == EmbeddedEventKind.CLEAR
    certificate = state.certificate()
    assert np.linalg.norm(events[0].position - certificate.center) + certificate.radius_m <= (
        physical.clear_radius_m - planner.clear_margin_m + 1e-7
    )


def test_route_crossing_guaranteed_region_produces_useful_measurement() -> None:
    physical = PhysicalConfig()
    planner = PlannerConfig(grid_step_m=5.0)
    grid = CellGrid.target_disk(physical.target_radius_m, planner.grid_step_m)
    channels = initialize_channels(grid, physical, planner)
    state = channels[1]
    state.status = ChannelStatus.FOUND
    state.possible[:] = False
    for point in (np.array([-50.0, 0.0]), np.array([50.0, 0.0])):
        state.possible[grid.containing_cell_indices(point)] = True
    state.history.append(Observation((-200.0, 0.0), "direction", 0.0, 0))
    leg = RouteLeg(np.array([0.0, -100.0]), np.array([0.0, 100.0]), "test", 1)
    events = OpportunityPlanner(physical, planner).events(leg, channels)
    assert len(events) == 1
    assert events[0].kind == EmbeddedEventKind.MEASURE
    assert np.linalg.norm(events[0].position - leg.start) + np.linalg.norm(
        leg.end - events[0].position
    ) == pytest.approx(leg.length_m)


def test_coverage_milestone_does_not_batch_measure_found_channels() -> None:
    sources = tuple(Source(c, (500.0, 10.0 * c), 1500.0) for c in range(1, 11))
    mock = MockSimulator(Scenario("unknown-only", 4, sources))
    controller = RouteEmbeddedController(
        mock, planner=PlannerConfig(grid_step_m=25.0), known_total=10
    )
    mock.enter()
    controller._measure(np.zeros(2), 1, 0)
    assert controller.channels[1].status == ChannelStatus.FOUND
    controller.coverage = RoutePlanner(controller.planner).plan([]).coverage
    controller._scan_unknown_coverage(1)
    found_at_vertex = [
        action for action in mock.actions
        if action["path"] == "/measure"
        and action["channel"] == 1
        and np.allclose(action["position"], controller.coverage[1])
    ]
    assert found_at_vertex == []


def test_route_embedded_controller_closes_small_fixed_case() -> None:
    sources = tuple(
        Source(c, (300.0 + 30.0 * c, -400.0 + 60.0 * c), 1500.0)
        for c in range(1, 11)
    )
    scenario = Scenario("route-embedded-smoke", 7, sources)
    mock = MockSimulator(scenario)
    result = RouteEmbeddedController(
        mock, planner=PlannerConfig(grid_step_m=25.0), known_total=10
    ).run()
    assert result.success
    assert result.clear_ratio == 1.0
    scans = [item for item in result.diagnostics if item["type"] == "coverage_unknown_scan"]
    assert scans
    assert scans[0]["unknown_measurements"] == 20
    assert all("unknown_measurements" in item for item in scans)
