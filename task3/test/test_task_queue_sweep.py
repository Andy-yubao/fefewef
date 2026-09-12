"""Minimal behavioral tests for candidate 038's task-queue architecture."""

from __future__ import annotations

import numpy as np
from types import SimpleNamespace

from task3.src.channel_state import ChannelStatus
from task3.src.config import PlannerConfig
from task3.src.controller import SearchController
from task3.src.coverage import ordered_points
from task3.src.mock_simulator import MockSimulator, Scenario, Source
from task3.src.policies import POLICIES
from task3.src.route_planner import RoutePlanner
from task3.src.task_driven_controller import TaskDrivenController
from task3.src.task_queue import Task, TaskKind, TaskQueue
from task3.src.task_sweep_planner import TaskSweepPlanner


def fixed_scenario() -> Scenario:
    sources = tuple(
        Source(channel, (250.0 + 25.0 * channel, -350.0 + 55.0 * channel), 1500.0)
        for channel in range(1, 11)
    )
    return Scenario("task-queue-fixed", 17, sources)


def test_020_and_038_remain_separate_and_instantiable() -> None:
    scenario = fixed_scenario()
    planner = PlannerConfig(grid_step_m=25.0)
    legacy = SearchController(MockSimulator(scenario), planner=planner)
    task_queue = TaskDrivenController(MockSimulator(scenario), planner=planner)
    assert type(legacy) is SearchController
    assert type(task_queue) is TaskDrivenController
    assert POLICIES["candidate_020_grid5_center_approach"].controller == "legacy"
    assert POLICIES["candidate_038_task_queue_sweep"].controller == "task_queue"


def test_active_is_not_preempted_when_waiting_reorders() -> None:
    queue = TaskQueue()
    active = Task(TaskKind.RESOLVE_SOURCE, channel=8, order_key=(0,))
    queue.rebuild([active, Task(TaskKind.ADVANCE_COVERAGE, vertex=3, order_key=(1,))])
    assert queue.select_active() == active
    queue.rebuild([
        active,
        Task(TaskKind.RESOLVE_SOURCE, channel=15, order_key=(-1,)),
        Task(TaskKind.ADVANCE_COVERAGE, vertex=3, order_key=(1,)),
    ])
    assert queue.active == active
    assert queue.waiting[0].channel == 15


def test_waiting_reorders_after_new_belief_order_is_supplied() -> None:
    queue = TaskQueue()
    ch8 = Task(TaskKind.RESOLVE_SOURCE, channel=8, order_key=(2,))
    ch15 = Task(TaskKind.RESOLVE_SOURCE, channel=15, order_key=(1,))
    queue.rebuild([ch8, ch15])
    assert [task.channel for task in queue.waiting] == [15, 8]
    queue.rebuild([
        Task(TaskKind.RESOLVE_SOURCE, channel=8, order_key=(0,)),
        Task(TaskKind.RESOLVE_SOURCE, channel=15, order_key=(3,)),
    ])
    assert [task.channel for task in queue.waiting] == [8, 15]


def test_opportunistic_measure_does_not_change_active() -> None:
    scenario = fixed_scenario()
    mock = MockSimulator(scenario)
    controller = TaskDrivenController(mock, planner=PlannerConfig(grid_step_m=25.0))
    mock.enter()
    controller._measure(np.zeros(2), 8, 0)
    controller._measure(np.zeros(2), 15, 0)
    route = RoutePlanner(controller.planner).plan([0.0])
    controller.coverage = route.coverage
    controller.sweep_direction = route.sweep_direction
    controller.sweep_planner = TaskSweepPlanner(
        route.coverage, route.sweep_direction, controller.physical, controller.planner
    )
    controller.task_queue.active = Task(TaskKind.RESOLVE_SOURCE, channel=8)
    controller._do_measure(np.array([0.0, 100.0]), 15, "test_opportunity", True)
    controller._refresh_waiting("test")
    assert controller.task_queue.active is not None
    assert controller.task_queue.active.channel == 8


def test_advance_scans_unknown_but_not_found_channels() -> None:
    scenario = fixed_scenario()
    mock = MockSimulator(scenario)
    controller = TaskDrivenController(mock, planner=PlannerConfig(grid_step_m=25.0))
    mock.enter()
    controller._measure(np.zeros(2), 1, 0)
    assert controller.channels[1].status == ChannelStatus.FOUND
    route = RoutePlanner(controller.planner).plan([])
    controller.coverage = route.coverage
    controller.sweep_direction = route.sweep_direction
    controller.sweep_planner = TaskSweepPlanner(
        route.coverage, route.sweep_direction, controller.physical, controller.planner
    )
    controller.task_queue.active = Task(TaskKind.ADVANCE_COVERAGE, vertex=1)
    controller._scan_unknown_coverage(1)
    found_at_vertex = [
        action for action in mock.actions
        if action["path"] == "/measure" and action["channel"] == 1
        and np.allclose(action["position"], route.coverage[1])
    ]
    assert found_at_vertex == []


def test_resolve_source_closes_a_fixed_case() -> None:
    scenario = fixed_scenario()
    mock = MockSimulator(scenario)
    result = TaskDrivenController(
        mock, planner=PlannerConfig(grid_step_m=25.0), known_total=10
    ).run()
    assert result.success
    assert result.clear_ratio == 1.0
    starts = [item for item in result.diagnostics if item["type"] == "task_started"]
    assert any(item["active_task_type"] == "ResolveSource" for item in starts)
    assert all(
        item["active_task_type"] in {"ResolveSource", "AdvanceCoverage"}
        for item in result.diagnostics
        if item["type"] == "task_action" and item["movement_m"] > 0.0
    )


def _found_controller() -> TaskDrivenController:
    scenario = fixed_scenario()
    mock = MockSimulator(scenario)
    controller = TaskDrivenController(mock, planner=PlannerConfig(grid_step_m=25.0))
    mock.enter()
    controller._measure(np.zeros(2), 1, 0)
    route = RoutePlanner(controller.planner).plan([])
    controller.coverage = route.coverage
    controller.sweep_direction = route.sweep_direction
    controller.sweep_planner = TaskSweepPlanner(
        route.coverage, route.sweep_direction, controller.physical, controller.planner
    )
    return controller


def test_not_ready_resolve_stays_waiting_behind_advance(monkeypatch) -> None:
    controller = _found_controller()
    monkeypatch.setattr(controller, "_normal_resolve_action", lambda channel: None)
    tasks = controller._available_tasks()
    resolve = next(task for task in tasks if task.kind == TaskKind.RESOLVE_SOURCE)
    assert not resolve.ready
    controller.task_queue.rebuild(tasks)
    active = controller.task_queue.select_active()
    assert active is not None and active.kind == TaskKind.ADVANCE_COVERAGE
    assert any(task.identity == resolve.identity for task in controller.task_queue.waiting)


def test_ready_resolve_can_become_active(monkeypatch) -> None:
    controller = _found_controller()
    source_rank = controller.sweep_planner.service_window(
        controller.channels[1], frontier_rank=-1
    ).source_rank
    controller.coverage_completed.update(range(1, source_rank + 2))
    point = np.asarray(controller.client.position, float)
    monkeypatch.setattr(
        controller,
        "_normal_resolve_action",
        lambda channel: ("CLEAR", point, "certified_clear_point", True),
    )
    controller.task_queue.rebuild(controller._available_tasks())
    active = controller.task_queue.select_active()
    assert active is not None and active.kind == TaskKind.RESOLVE_SOURCE
    assert active.activation_reason == "certified_clear_point"


def test_fallback_is_gated_below_bearing_limit() -> None:
    controller = _found_controller()
    state = controller.channels[1]
    state.fallback_queue = [tuple(controller.coverage[1])]
    assert state.bearing_count < controller.planner.max_bearings_before_fallback
    assert controller._fallback_clear_point(1) is None


def test_fallback_cannot_escape_behind_frontier() -> None:
    controller = _found_controller()
    controller.coverage_completed.update({1, 2})
    state = controller.channels[1]
    state.bearing_count = controller.planner.max_bearings_before_fallback
    state.fallback_queue = [tuple(controller.coverage[1])]
    assert controller._fallback_clear_point(1) is None
    assert state.fallback_queue == [tuple(controller.coverage[1])]


def test_cw_and_ccw_sector_ranks_follow_traversal_order() -> None:
    ccw_points = ordered_points(0.0, False)
    cw_points = ordered_points(0.0, True)
    ccw = TaskSweepPlanner(ccw_points, "CCW")
    cw = TaskSweepPlanner(cw_points, "CW")
    east = np.array([1200.0, 0.0])
    assert ccw.rank_for_point(east) == 0
    assert cw.rank_for_point(east) == 5
    assert cw.rank_for_point(cw_points[1]) == 0
    assert ccw.is_forward_compatible(east, frontier_rank=5)


def test_service_deadline_uses_certificate_center_not_radius() -> None:
    route = RoutePlanner().plan([])
    sweep = TaskSweepPlanner(route.coverage, route.sweep_direction)
    state = SimpleNamespace(certificate=lambda: SimpleNamespace(
        center=route.coverage[3], radius_m=5000.0
    ))
    future = sweep.service_window(state, frontier_rank=0)
    current = sweep.service_window(state, frontier_rank=2)
    assert future.source_rank == 2 and not future.deadline
    assert current.source_rank == 2 and current.deadline


def test_completed_rank_is_rejected_as_normal_resolve_candidate() -> None:
    route = RoutePlanner().plan([])
    sweep = TaskSweepPlanner(route.coverage, route.sweep_direction)
    frontier_rank = 1
    assert not sweep.is_forward_compatible(route.coverage[1], frontier_rank)
    assert sweep.is_forward_compatible(route.coverage[2], frontier_rank)
    assert sweep.is_forward_compatible(route.coverage[3], frontier_rank)


def test_active_resolve_movement_monotonically_updates_leg_progress() -> None:
    controller = _found_controller()
    controller.coverage_completed.add(1)
    controller.task_queue.active = Task(TaskKind.RESOLVE_SOURCE, channel=1)
    start = controller.coverage[1]
    end = controller.coverage[2]

    quarter = start + 0.25 * (end - start)
    controller._record_action(
        "MEASURE", 1, start, quarter, "forward_center_measurement"
    )
    assert np.isclose(controller._leg_progress_fraction, 0.25)

    three_quarters = start + 0.75 * (end - start)
    controller._record_action(
        "CLEAR", 1, quarter, three_quarters, "certified_clear_point"
    )
    assert np.isclose(controller._leg_progress_fraction, 0.75)

    controller._record_action(
        "MEASURE", 1, three_quarters, quarter, "another_dedicated_action"
    )
    assert np.isclose(controller._leg_progress_fraction, 0.75)


def test_forward_route_does_not_reselect_reached_leg_prefix(monkeypatch) -> None:
    controller = _found_controller()
    controller.coverage_completed.add(1)
    controller.task_queue.active = Task(TaskKind.RESOLVE_SOURCE, channel=1)
    start = controller.coverage[1]
    passed = start + 0.3 * (controller.coverage[2] - start)
    controller._record_action(
        "CLEAR", 1, start, passed, "certified_clear_point"
    )
    monkeypatch.setattr(controller, "_measurement_useful_at", lambda channel, point: True)

    point = controller._forward_route_measurement(1)
    assert point is not None
    _, fraction = controller._route_progress(point)
    assert fraction > 0.3


def test_radial_detour_does_not_advance_leg_progress() -> None:
    controller = _found_controller()
    controller.coverage_completed.add(1)
    controller.task_queue.active = Task(TaskKind.RESOLVE_SOURCE, channel=1)
    start = controller.coverage[1]
    radial = 1.1 * start

    controller._record_action(
        "MEASURE", 1, start, radial, "forward_center_measurement"
    )
    assert controller._leg_progress_fraction == 0.0
