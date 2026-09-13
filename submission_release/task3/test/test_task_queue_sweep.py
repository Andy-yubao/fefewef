"""Minimal behavioral tests for candidate 038's task-queue architecture."""

from __future__ import annotations

import numpy as np
import pytest
from types import SimpleNamespace

from task3.src.channel_state import ChannelStatus
from task3.src.config import PlannerConfig
from task3.src.controller import SearchController
from task3.src.coverage import ordered_points
from task3.src.mock_simulator import MockSimulator, Scenario, Source
from task3.src.policies import POLICIES
from task3.src.route_planner import RoutePlanner
from task3.src.short_horizon_sequencer import (
    UNKNOWN_COMPLETION,
    CompletionCertainty,
    CompletionPreview,
    TaskPreview,
    choose_short_horizon_sequence,
)
from task3.src.task_driven_controller import SEQUENCING_HORIZON, TaskDrivenController
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
    assert controller.local_leg_retrace_count == 1
    assert np.isclose(controller.local_leg_retrace_m, 0.5 * np.linalg.norm(end - start))


def test_resolve_target_must_not_fall_behind_current_leg_progress() -> None:
    controller = _found_controller()
    controller.coverage_completed.add(1)
    start = controller.coverage[1]
    end = controller.coverage[2]
    controller._sync_leg_progress()
    controller._leg_progress_fraction = 0.5

    behind = start + 0.49 * (end - start)
    current = start + 0.5 * (end - start)
    ahead = start + 0.51 * (end - start)
    assert not controller._is_not_behind_current_leg_progress(behind)
    assert controller._is_not_behind_current_leg_progress(current)
    assert controller._is_not_behind_current_leg_progress(ahead)


def test_local_forward_tolerance_is_converted_from_metres() -> None:
    controller = _found_controller()
    controller.coverage_completed.add(1)
    start = controller.coverage[1]
    end = controller.coverage[2]
    leg_length = float(np.linalg.norm(end - start))
    controller._sync_leg_progress()
    controller._leg_progress_fraction = 0.5

    within_tol = start + (
        0.5 - 0.5 * controller.planner.numeric_distance_tol_m / leg_length
    ) * (end - start)
    beyond_tol = start + (
        0.5 - 2.0 * controller.planner.numeric_distance_tol_m / leg_length
    ) * (end - start)
    assert controller._is_not_behind_current_leg_progress(within_tol)
    assert not controller._is_not_behind_current_leg_progress(beyond_tol)


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
    assert controller.local_leg_retrace_count == 0
    assert controller.local_leg_retrace_m == 0.0


def test_opportunistic_reverse_move_is_not_counted_as_local_retrace() -> None:
    controller = _found_controller()
    controller.coverage_completed.add(1)
    controller.task_queue.active = Task(TaskKind.RESOLVE_SOURCE, channel=1)
    start = controller.coverage[1]
    end = controller.coverage[2]
    three_quarters = start + 0.75 * (end - start)
    quarter = start + 0.25 * (end - start)
    controller._sync_leg_progress()
    controller._leg_progress_fraction = 0.75

    controller._record_action(
        "MEASURE", 1, three_quarters, quarter, "test_opportunity", True
    )
    assert controller.local_leg_retrace_count == 0
    assert controller._leg_progress_fraction == 0.75


def _sequence_decision(
    previews: list[TaskPreview],
    required: set[tuple] | None = None,
    *,
    with_advance: bool = True,
    switch_s: float = 0.0,
    horizon: int = SEQUENCING_HORIZON,
):
    # Every production candidate carries the sweep planner's order_key; an empty
    # key would sort ahead of every real one.
    advance = (
        Task(TaskKind.ADVANCE_COVERAGE, vertex=2, order_key=(1, 2))
        if with_advance else None
    )
    return choose_short_horizon_sequence(
        np.array([0.0, 0.0]),
        None,
        previews,
        advance,
        np.array([0.0, 1000.0]) if with_advance else None,
        required or set(),
        speed_mps=1.0,
        switch_s=switch_s,
        horizon=horizon,
    )


def _completion(
    endpoint: tuple[float, float] | None,
    operation_s: float = 0.0,
    certainty: CompletionCertainty = CompletionCertainty.ESTIMATED,
    requires_measure: bool = True,
    uncertainty_m: float = 0.0,
) -> CompletionPreview:
    return CompletionPreview(
        certainty if endpoint is not None else CompletionCertainty.UNKNOWN,
        endpoint=None if endpoint is None else np.array(endpoint, float),
        operation_s=operation_s,
        requires_measure=requires_measure,
        endpoint_uncertainty_m=uncertainty_m,
        reason="test",
    )


def _preview(
    task: Task,
    x: float,
    completion: CompletionPreview | None = None,
    switch: bool = True,
) -> TaskPreview:
    return TaskPreview(
        task=task,
        immediate_action="MEASURE",
        immediate_reason="test_measurement",
        immediate_operation_time_s=0.0,
        immediate_end_position=np.array([x, 0.0]),
        requires_channel_switch=switch,
        completion=completion if completion is not None else UNKNOWN_COMPLETION,
    )


def _ordering(decision, *tasks):
    """The candidate ordering whose first legs are exactly ``tasks``."""
    for sequence in decision.sequences:
        if sequence.tasks[:len(tasks)] == tuple(tasks):
            return sequence
    raise AssertionError(f"no ordering starting with {[task.label for task in tasks]}")


def test_unpriced_completion_falls_back_to_order_key() -> None:
    forward = Task(TaskKind.RESOLVE_SOURCE, channel=7, order_key=(0, 7))
    in_place = Task(TaskKind.RESOLVE_SOURCE, channel=3, order_key=(2, 3))
    decision = _sequence_decision([
        TaskPreview(
            task=in_place,
            immediate_action="MEASURE",
            immediate_reason="current_position_information",
            immediate_operation_time_s=5.0,
            immediate_end_position=np.array([0.0, 0.0]),
        ),
        _preview(forward, 900.0),
    ])
    # The zero-travel 5 s measure costs 5 while its rival costs 900, yet neither
    # completion is knowable, so commitment falls back to the geometric order.
    assert decision.basis == "order_key"
    assert decision.chosen_task == forward
    assert decision.chosen_sequence is not None
    assert decision.chosen_sequence.immediate_cost_s == 900.0
    assert {task.label for task in decision.unpriced} == {
        in_place.label, forward.label
    }


def test_advance_does_not_claim_a_known_completion() -> None:
    advance = Task(TaskKind.ADVANCE_COVERAGE, vertex=2, order_key=(1, 2))
    decision = choose_short_horizon_sequence(
        np.array([0.0, 0.0]), None, [], advance, np.array([10.0, 0.0]),
        set(), speed_mps=1.0, switch_s=0.0,
    )
    assert decision.chosen_task == advance
    sequence = decision.chosen_sequence
    assert sequence is not None
    # The vertex and the movement cost are still known and reported; only the
    # whole-task completion claim is withdrawn.
    assert np.allclose(sequence.end_position, [10.0, 0.0])
    assert np.isclose(sequence.immediate_cost_s, 10.0)
    assert not sequence.legs[0].completion.known
    assert sequence.legs[0].completion.certainty is CompletionCertainty.UNKNOWN


def test_unknown_completion_never_enters_a_multi_step_rollout() -> None:
    priced = Task(TaskKind.RESOLVE_SOURCE, channel=1, order_key=(0, 1))
    unpriced = Task(TaskKind.RESOLVE_SOURCE, channel=2, order_key=(0, 2))
    decision = _sequence_decision([
        _preview(priced, 5.0, _completion((5.0, 0.0))),
        _preview(unpriced, 5.0),
    ])
    assert decision.basis == "order_key"
    assert all(len(sequence.tasks) == 1 for sequence in decision.sequences)
    assert [task.label for task in decision.unpriced] == [unpriced.label]
    assert [task.label for task in decision.sequenced] == [priced.label]


def test_ordering_prefers_the_nearer_completion_over_order_key() -> None:
    # ch1 sorts first by order key and by label, but finishes 900 m away.
    far = Task(TaskKind.RESOLVE_SOURCE, channel=1, order_key=(0, 1))
    near = Task(TaskKind.RESOLVE_SOURCE, channel=2, order_key=(0, 2))
    decision = _sequence_decision([
        _preview(far, 0.0, _completion((900.0, 0.0))),
        _preview(near, 0.0, _completion((100.0, 0.0))),
    ])
    assert decision.basis == "completion_sequence"
    assert decision.chosen_task == near
    far_first = _ordering(decision, far, near)
    near_first = _ordering(decision, near, far)
    assert near_first.cost_s < far_first.cost_s


def test_second_leg_is_recomputed_from_the_first_end_state() -> None:
    first = Task(TaskKind.RESOLVE_SOURCE, channel=1, order_key=(0, 1))
    second = Task(TaskKind.RESOLVE_SOURCE, channel=2, order_key=(0, 2))
    decision = _sequence_decision(
        [
            _preview(first, 0.0, _completion((10.0, 0.0))),
            _preview(second, 0.0, _completion((100.0, 0.0))),
        ],
        switch_s=1.0,
    )
    pair = _ordering(decision, first, second)
    # 90 m from the first completion point, not 100 m from the planning pose,
    # plus one channel switch because the second task re-measures its channel.
    assert np.isclose(pair.legs[1].cost_s, 91.0)
    # The first leg is entered holding no channel, so it pays a switch as well.
    assert np.isclose(pair.legs[0].cost_s, 11.0)


def test_advance_terminator_prices_reaching_the_next_milestone() -> None:
    first = Task(TaskKind.RESOLVE_SOURCE, channel=1, order_key=(0, 1))
    second = Task(TaskKind.RESOLVE_SOURCE, channel=2, order_key=(0, 2))
    decision = _sequence_decision([
        _preview(first, 0.0, _completion((10.0, 0.0))),
        _preview(second, 0.0, _completion((100.0, 0.0))),
    ])
    pair = _ordering(decision, first, second)
    terminator = pair.legs[-1]
    assert terminator.task.kind == TaskKind.ADVANCE_COVERAGE
    assert not terminator.completion.known
    # The positional term is real travel from the second completion point to the
    # milestone vertex, priced at speed_mps = 1.0.
    expected = float(np.linalg.norm(
        np.array([100.0, 0.0]) - np.array([0.0, 1000.0])
    ))
    assert np.isclose(terminator.cost_s, expected)
    assert np.allclose(terminator.endpoint, [0.0, 1000.0])
    assert np.isclose(pair.cost_s, pair.legs[0].cost_s + pair.legs[1].cost_s + expected)


def test_reordering_is_refused_when_belief_error_exceeds_the_advantage() -> None:
    far = Task(TaskKind.RESOLVE_SOURCE, channel=1, order_key=(0, 1))
    near = Task(TaskKind.RESOLVE_SOURCE, channel=2, order_key=(0, 2))
    # The same 800 m advantage that ordered the pair a moment ago is now inside
    # the certificates that produced it, so nothing is reordered.
    decision = _sequence_decision([
        _preview(far, 0.0, _completion((900.0, 0.0), uncertainty_m=600.0)),
        _preview(near, 0.0, _completion((100.0, 0.0), uncertainty_m=600.0)),
    ])
    assert decision.basis == "order_key_uncertain_completion"
    assert decision.chosen_task == far
    # The rejected comparison is still reported, but nothing is committed from it.
    assert decision.chosen_sequence is None
    assert decision.sequences and all(len(sequence.tasks) >= 2 for sequence in decision.sequences)


def test_sequencing_caps_at_the_horizon_and_reports_the_cap() -> None:
    tasks = [
        Task(TaskKind.RESOLVE_SOURCE, channel=channel, order_key=(0, channel))
        for channel in range(1, 6)
    ]
    decision = _sequence_decision([
        _preview(task, 0.0, _completion((float(10 * task.channel), 0.0)))
        for task in tasks
    ], horizon=3)
    assert [task.channel for task in decision.sequenced] == [1, 2, 3]
    assert all(len(sequence.legs) == 4 for sequence in decision.sequences)


def test_ready_required_resolve_gates_advance_one_step_at_a_time() -> None:
    required_a = Task(TaskKind.RESOLVE_SOURCE, channel=1, order_key=(0, 1))
    required_b = Task(TaskKind.RESOLVE_SOURCE, channel=2, order_key=(3, 2))
    decision = _sequence_decision(
        [_preview(required_a, 2.0), _preview(required_b, 3.0)],
        {required_a.identity, required_b.identity},
    )
    assert decision.basis.startswith("required_")
    assert decision.chosen_task == required_a
    assert all(
        sequence.tasks[0].kind == TaskKind.RESOLVE_SOURCE
        for sequence in decision.sequences
    )


def test_resolves_behind_advance_are_never_sequenced_ahead_of_it() -> None:
    behind = Task(TaskKind.RESOLVE_SOURCE, channel=1, order_key=(2, 1))
    ahead = Task(TaskKind.RESOLVE_SOURCE, channel=2, order_key=(0, 2))
    decision = _sequence_decision([
        _preview(behind, 0.0, _completion((5.0, 0.0))),
        _preview(ahead, 0.0, _completion((900.0, 0.0))),
    ])
    # Only one Resolve precedes Advance, so no rollout is built and the sweep
    # keeps control of the Advance decision.
    assert decision.basis == "order_key"
    assert [task.channel for task in decision.sequenced] == [2]


def test_in_place_measure_does_not_award_task_commitment(monkeypatch) -> None:
    controller = _found_controller()
    cheap = Task(
        TaskKind.RESOLVE_SOURCE, channel=3, ready=True,
        source_sector_rank=0, order_key=(2, 3),
    )
    forward = Task(
        TaskKind.RESOLVE_SOURCE, channel=7, ready=True,
        source_sector_rank=0, order_key=(0, 7),
    )
    monkeypatch.setattr(
        controller,
        "_resolve_preview",
        lambda task: _preview(task, 0.0 if task.channel == 3 else 900.0),
    )
    controller.task_queue.rebuild(controller._sequence_waiting([cheap, forward], "test"))
    active = controller.task_queue.select_active()
    assert active is not None and active.channel == 7


def test_non_ready_resolve_does_not_gate_advance_in_controller(monkeypatch) -> None:
    controller = _found_controller()
    resolve = Task(
        TaskKind.RESOLVE_SOURCE, channel=1, ready=False,
        source_sector_rank=-1, order_key=(0,),
    )
    advance = Task(TaskKind.ADVANCE_COVERAGE, vertex=1, order_key=(1,))
    ordered = controller._sequence_waiting([resolve, advance], "test")
    controller.task_queue.rebuild(ordered)
    assert controller.task_queue.select_active() == advance


def test_all_ready_required_tasks_bypass_top_three(monkeypatch) -> None:
    controller = _found_controller()
    required = [
        Task(
            TaskKind.RESOLVE_SOURCE, channel=channel, ready=True,
            source_sector_rank=-1, order_key=(0, channel),
        )
        for channel in range(1, 5)
    ]
    optional = Task(
        TaskKind.RESOLVE_SOURCE, channel=5, ready=True,
        source_sector_rank=0, order_key=(2, 5),
    )
    advance = Task(TaskKind.ADVANCE_COVERAGE, vertex=1, order_key=(1,))
    monkeypatch.setattr(
        controller, "_resolve_preview", lambda task: _preview(task, float(task.channel))
    )
    controller._sequence_waiting(required + [optional, advance], "test")
    decision = controller.diagnostics[-1]
    assert decision["sequencing_horizon"] == SEQUENCING_HORIZON
    assert set(decision["required_before_advance"]) == {task.label for task in required}
    labels = {item["sequence"] for item in decision["candidate_sequences"]}
    assert labels == {task.label for task in required}


def test_intermediate_resolve_preview_does_not_claim_completion(monkeypatch) -> None:
    controller = _found_controller()
    point = np.asarray(controller.client.position, float)
    monkeypatch.setattr(
        controller,
        "_normal_resolve_action",
        lambda channel: ("MEASURE", point, "current_position_information", False),
    )
    monkeypatch.setattr(
        controller.sweep_planner, "is_forward_compatible", lambda point, rank: False
    )
    preview = controller._resolve_preview(Task(TaskKind.RESOLVE_SOURCE, channel=1))
    assert preview is not None
    assert preview.completion.certainty is CompletionCertainty.UNKNOWN
    assert preview.completion.endpoint is None
    assert not preview.completion.known


def test_certified_clear_preview_has_reliable_completion_fields(monkeypatch) -> None:
    controller = _found_controller()
    point = np.asarray(controller.client.position, float) + np.array([10.0, 0.0])
    monkeypatch.setattr(
        controller,
        "_normal_resolve_action",
        lambda channel: ("CLEAR", point, "certified_clear_point", True),
    )
    preview = controller._resolve_preview(Task(TaskKind.RESOLVE_SOURCE, channel=1))
    assert preview is not None
    assert preview.completion.certainty is CompletionCertainty.EXACT
    assert np.allclose(preview.completion.endpoint, point)
    expected = controller.physical.optical_s + controller.physical.laser_s
    assert np.isclose(preview.completion.operation_s, expected)
    assert not preview.completion.requires_measure


def test_reachable_certificate_center_is_estimated_not_exact(monkeypatch) -> None:
    controller = _found_controller()
    point = np.asarray(controller.client.position, float)
    monkeypatch.setattr(
        controller,
        "_normal_resolve_action",
        lambda channel: ("MEASURE", point, "forward_route_measurement", False),
    )
    monkeypatch.setattr(
        controller.sweep_planner, "is_forward_compatible", lambda point, rank: True
    )
    preview = controller._resolve_preview(Task(TaskKind.RESOLVE_SOURCE, channel=1))
    assert preview is not None
    assert preview.completion.certainty is CompletionCertainty.ESTIMATED
    assert preview.completion.requires_measure
    assert np.allclose(
        preview.completion.endpoint, controller.channels[1].certificate().center
    )
    assert np.isclose(
        preview.completion.operation_s,
        controller.physical.measure_s
        + controller.physical.optical_s
        + controller.physical.laser_s,
    )


def test_completion_preview_rejects_an_unpriced_endpoint() -> None:
    with pytest.raises(ValueError):
        CompletionPreview(CompletionCertainty.ESTIMATED, endpoint=None)
    with pytest.raises(ValueError):
        CompletionPreview(CompletionCertainty.UNKNOWN, endpoint=np.zeros(2))


def test_controller_sequences_waiting_without_preempting_active(monkeypatch) -> None:
    controller = _found_controller()
    active = Task(TaskKind.RESOLVE_SOURCE, channel=1)
    controller.task_queue.active = active
    monkeypatch.setattr(controller, "_resolve_preview", lambda task: _preview(task, 0.0))
    controller._refresh_waiting("opportunistic_observation")
    assert controller.task_queue.active == active
