"""Minimal behavioral tests for candidate 038's task-queue architecture."""

from __future__ import annotations

import numpy as np

from task3.src.channel_state import ChannelStatus, Observation
from task3.src.config import PlannerConfig
from task3.src.controller import SearchController
from task3.src.mock_simulator import MockSimulator, Scenario, Source
from task3.src.policies import POLICIES
from task3.src.route_embedded_controller import RouteEmbeddedController
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


def test_020_and_037_remain_separate_and_instantiable() -> None:
    scenario = fixed_scenario()
    planner = PlannerConfig(grid_step_m=25.0)
    legacy = SearchController(MockSimulator(scenario), planner=planner)
    embedded = RouteEmbeddedController(MockSimulator(scenario), planner=planner)
    assert type(legacy) is SearchController
    assert type(embedded) is RouteEmbeddedController
    assert POLICIES["candidate_020_grid5_center_approach"].controller == "legacy"
    assert POLICIES["candidate_037_route_embedded_sweep"].controller == "route_embedded"
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


def test_completed_sector_is_rejected_as_normal_resolve_candidate() -> None:
    route = RoutePlanner().plan([])
    sweep = TaskSweepPlanner(route.coverage, route.sweep_direction)
    completed = {1}
    assert not sweep.is_forward_compatible(route.coverage[1], completed)
    assert sweep.is_forward_compatible(route.coverage[2], completed)
