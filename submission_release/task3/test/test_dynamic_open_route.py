"""Directed tests for candidate 039's dynamic open-route invariants."""

from __future__ import annotations

from types import SimpleNamespace
import math

import numpy as np
import pytest

from task3.src.channel_state import ChannelStatus, Observation
from task3.src.config import PhysicalConfig, PlannerConfig
from task3.src.coverage import choose_orientation, ordered_points, seven_points
from task3.src.dynamic_open_route import (
    AngularCrossingGuard,
    DirectedSweepProgress,
    DynamicOpenRoutePlanner,
    GuardDecision,
    GuardLevel,
    LocalizationStage,
    RouteNode,
    RouteNodeKind,
    ServiceTarget,
    SourceResolver,
    build_candidate_nodes,
    localization_stage,
)
from task3.src.dynamic_open_route_controller import DynamicOpenRouteController
from task3.experiments.plot_route import resolution_order, source_points
from task3.src.mock_simulator import MockSimulator, Scenario, Source
from task3.src.opportunity_planner import EmbeddedEvent, EmbeddedEventKind, OpportunityPlanner
from task3.src.policies import POLICIES
from task3.src.route_planner import RouteLeg


def test_sparse_six_orientation_avoids_all_radial_collinearity() -> None:
    rotation, reverse = choose_orientation([0.0], strategy="sparse_six")
    vertices = seven_points(rotation)[1:]
    separations = [
        min(abs(((0.0 - math.degrees(math.atan2(y, x)) + 180.0) % 360.0) - 180.0)
            for x, y in vertices)
    ]
    assert min(separations) == pytest.approx(30.0)
    assert reverse in (False, True)


def test_sparse_six_preserves_hexagon_covering_set() -> None:
    rotation, _reverse = choose_orientation([17.0, 188.0, 301.0], strategy="sparse_six")
    distances = np.sort(np.linalg.norm(seven_points(rotation)[1:], axis=1))
    assert np.allclose(distances, np.full(6, 1200.0))


def node(kind: RouteNodeKind, x: float, y: float, *, vertex=None, channel=None) -> RouteNode:
    return RouteNode(kind, np.array([x, y], float), vertex=vertex, channel=channel)


def test_a_direct_source_to_source_is_allowed() -> None:
    planner = DynamicOpenRoutePlanner(PhysicalConfig(), PlannerConfig())
    route = planner.plan(np.array([0.0, 0.0]), 1, [
        node(RouteNodeKind.COVERAGE, 10, 0, vertex=2),
        node(RouteNodeKind.COVERAGE, 20, 0, vertex=3),
        node(RouteNodeKind.SOURCE, 2, 0, channel=7),
    ])
    assert route.first_target is not None
    assert route.first_target.kind == RouteNodeKind.SOURCE
    assert np.allclose(route.first_target.point, [2, 0])


def test_b_coverage_precedence_is_hard() -> None:
    planner = DynamicOpenRoutePlanner(PhysicalConfig(), PlannerConfig())
    nodes = [
        node(RouteNodeKind.COVERAGE, 10, 0, vertex=2),
        node(RouteNodeKind.COVERAGE, -1, 0, vertex=3),
        node(RouteNodeKind.SOURCE, 2, 2, channel=1),
        node(RouteNodeKind.SOURCE, 3, 2, channel=2),
        node(RouteNodeKind.SOURCE, 4, 2, channel=3),
    ]
    route = planner.plan(np.zeros(2), 1, nodes)
    labels = [item.label for item in route.nodes]
    assert labels.index("V2") < labels.index("V3")


class FakeState:
    def __init__(self, channel: int, center: tuple[float, float], bearing_count: int = 2,
                 radius_m: float = 100.0, safe: bool = False):
        self.channel = channel
        self.status = ChannelStatus.FOUND
        self.bearing_count = bearing_count
        self.history = []
        self._center = np.asarray(center, float)
        self._radius_m = radius_m
        self._safe = safe
        self.tsp_window_armed = True

    def certificate(self):
        return SimpleNamespace(center=self._center, radius_m=self._radius_m)

    def safe_clear_point(self):
        return self._center.copy() if self._safe else None

    def already_measured(self, point):
        return False


class FakeResolver:
    def __init__(self):
        self.calls: list[int] = []
        self.physical = PhysicalConfig()
        self.planner = PlannerConfig()

    def current_service_target(self, state, *_args):
        self.calls.append(state.channel)
        return ServiceTarget(state.certificate().center.copy(), "MEASURE", "fake", 5.0)


def test_preplanned_cross_view_is_scheduled_on_preceding_edge() -> None:
    controller = DynamicOpenRouteController(
        MockSimulator(Scenario(
            "cross-view-schedule", 20,
            tuple(Source(c, (300.0 + c, 250.0), 1500.0) for c in range(1, 11)),
        )),
        planner=PlannerConfig(preplanned_cross_view=True),
    )
    state = FakeState(7, (400.0, 700.0), bearing_count=1, radius_m=750.0)
    state.history = [Observation((0.0, 0.0), "direction", 60.0, 0)]
    state.cross_view_point = None
    state.cross_view_edge = None
    state.cross_view_armed = False
    controller.channels = {7: state}
    controller.coverage = ordered_points(0.0, False, 1200.0)
    controller.progress = DirectedSweepProgress(0.0, "CCW")
    controller._initialize_cross_view_tasks()
    expected = 0.5 * (controller.coverage[1] + controller.coverage[2])
    assert state.cross_view_edge == 2
    assert np.allclose(state.cross_view_point, expected)
    controller._refresh_cross_view_window(state)
    assert state.cross_view_armed


def test_preplanned_cross_view_survives_second_collinear_bearing() -> None:
    state = FakeState(7, (400.0, 700.0), bearing_count=2, radius_m=750.0)
    state.cross_view_point = (900.0, 500.0)
    state.cross_view_edge = 2
    state.cross_view_armed = True
    controller = DynamicOpenRouteController(MockSimulator(Scenario(
        "cross-view-cancel", 21,
        tuple(Source(c, (300.0 + c, 250.0), 1500.0) for c in range(1, 11)),
    )))
    controller.progress = DirectedSweepProgress(0.0, "CCW")
    controller._refresh_cross_view_window(state)
    assert state.cross_view_point is not None
    assert state.cross_view_armed


def test_preplanned_cross_view_cancels_after_rough_localization() -> None:
    state = FakeState(7, (400.0, 700.0), bearing_count=2, radius_m=40.0)
    state.cross_view_point = (900.0, 500.0)
    state.cross_view_edge = 2
    state.cross_view_armed = True
    controller = DynamicOpenRouteController(MockSimulator(Scenario(
        "cross-view-cancel", 21,
        tuple(Source(c, (300.0 + c, 250.0), 1500.0) for c in range(1, 11)),
    )))
    controller.progress = DirectedSweepProgress(0.0, "CCW")
    controller._refresh_cross_view_window(state)
    assert state.cross_view_point is None
    assert not state.cross_view_armed


def test_c_armed_source_remains_visible_after_local_angular_rollback() -> None:
    coverage = ordered_points(0.0, False, 1200.0)
    progress = DirectedSweepProgress(0.0, "CCW", maximum=math.radians(80.0))
    states = {
        1: FakeState(1, (1000 * math.cos(math.radians(30)), 1000 * math.sin(math.radians(30)))),
        2: FakeState(2, (1000 * math.cos(math.radians(90)), 1000 * math.sin(math.radians(90)))),
    }
    nodes, anchors = build_candidate_nodes(
        current_position=np.array([1.0, 0.0]), progress=progress,
        coverage=coverage, completed_vertices={0, 1}, channels=states,
        resolver=FakeResolver(),
    )
    assert anchors == [2, 3, 4, 5, 6]
    assert [item.channel for item in nodes if item.kind == RouteNodeKind.SOURCE] == [1, 2]


def test_c2_unarmed_source_is_suspended_until_coverage_cleanup() -> None:
    coverage = ordered_points(0.0, False, 1200.0)
    state = FakeState(12, (-305.0, -687.5), bearing_count=1, radius_m=754.2)
    state.tsp_window_armed = False
    nodes, _ = build_candidate_nodes(
        current_position=coverage[1], progress=DirectedSweepProgress(0.0, "CCW"),
        coverage=coverage, completed_vertices={0, 1}, channels={12: state},
        resolver=FakeResolver(),
    )
    assert all(item.channel != 12 for item in nodes)
    cleanup, _ = build_candidate_nodes(
        current_position=coverage[-1], progress=DirectedSweepProgress(0.0, "CCW"),
        coverage=coverage, completed_vertices=set(range(len(coverage))), channels={12: state},
        resolver=FakeResolver(),
    )
    assert any(item.channel == 12 for item in cleanup)


def test_c3_unreliable_origin_enclosing_certificate_does_not_arm_or_guard() -> None:
    controller = DynamicOpenRouteController(MockSimulator(Scenario(
        "window-gate", 10, tuple(Source(c, (300 + c, 250), 1500) for c in range(1, 11))
    )))
    controller.progress = DirectedSweepProgress(math.radians(10.0), "CCW")
    state = FakeState(12, (-305.0, -687.5), bearing_count=1, radius_m=754.2)
    state.tsp_window_armed = False
    controller._refresh_tsp_window(state)
    assert not state.tsp_window_armed
    target = node(RouteNodeKind.COVERAGE, 410.4, 1127.6, vertex=2)
    assert controller.crossing_guard.check(
        np.array([1181.8, 208.4]), target, controller.progress, {12: state}
    ).level == GuardLevel.NONE


def test_d_local_angular_rollback_does_not_reduce_progress() -> None:
    progress = DirectedSweepProgress(0.0, "CCW")
    progress.update(np.array([math.cos(1.2), math.sin(1.2)]))
    before = progress.maximum
    progress.update(np.array([math.cos(0.7), math.sin(0.7)]))
    assert progress.maximum == before


def test_e_one_source_exposes_one_route_node() -> None:
    coverage = ordered_points(0.0, False, 1200.0)
    resolver = FakeResolver()
    nodes, _ = build_candidate_nodes(
        current_position=np.zeros(2), progress=DirectedSweepProgress(0.0, "CCW"),
        coverage=coverage, completed_vertices={0, 1},
        channels={4: FakeState(4, (500, 800))}, resolver=resolver,
    )
    assert resolver.calls == [4]
    assert sum(item.channel == 4 for item in nodes) == 1


def test_f_source_action_returns_to_global_planning() -> None:
    scenario = Scenario("single-step", 1, tuple(
        Source(channel, (300.0 + channel, 250.0), 1500.0) for channel in range(1, 11)
    ))
    controller = DynamicOpenRouteController(
        MockSimulator(scenario), planner=PlannerConfig(grid_step_m=50.0), known_total=10,
    )
    assert not hasattr(controller, "active_task")
    assert POLICIES["candidate_039_dynamic_open_route"].controller == "dynamic_open_route"


def test_g_opportunity_is_segment_generic() -> None:
    state = FakeState(9, (500.0, 100.0), bearing_count=1)
    state.history = [Observation((0.0, 0.0), "direction", 10.0, 0)]
    planner = OpportunityPlanner(PhysicalConfig(), PlannerConfig(shared_min_sin_angle=0.0))
    events = planner.events(
        RouteLeg(np.array([0.0, 0.0]), np.array([1000.0, 0.0]), "source_to_source", -1),
        {9: state},
    )
    assert any(event.kind == EmbeddedEventKind.MEASURE for event in events)
    assert all(abs(event.position[1]) < 1e-9 for event in events)


def crossing_fixture() -> tuple[AngularCrossingGuard, DirectedSweepProgress, FakeState, RouteNode]:
    guard = AngularCrossingGuard(PhysicalConfig(), PlannerConfig(shared_min_sin_angle=0.1))
    progress = DirectedSweepProgress(0.0, "CCW")
    state = FakeState(5, (600.0, 600.0), bearing_count=1)
    state.history = [Observation((0.0, 0.0), "direction", 45.0, 0)]
    target = node(RouteNodeKind.COVERAGE, 0.0, 1200.0, vertex=2)
    return guard, progress, state, target


def test_h_zero_detour_guard_keeps_original_target() -> None:
    guard, progress, state, target = crossing_fixture()
    decision = guard.check(np.array([1200.0, 0.0]), target, progress, {5: state})
    assert decision.level == GuardLevel.ZERO_DETOUR
    assert decision.target is target
    assert decision.event is not None


def test_i_small_detour_replaces_first_target(monkeypatch) -> None:
    guard, progress, state, target = crossing_fixture()
    monkeypatch.setattr(guard.opportunities, "events", lambda *_args, **_kwargs: [])
    point = np.array([570.0, 570.0])
    monkeypatch.setattr(guard, "_valid_points", lambda *_args: [point])
    decision = guard.check(np.array([1200.0, 0.0]), target, progress, {5: state})
    assert decision.level == GuardLevel.SMALL_DETOUR
    assert decision.target.kind == RouteNodeKind.GUARD
    assert decision.detour_m is not None and decision.detour_m <= 100.0


def test_j_hard_guard_cannot_be_priced_away(monkeypatch) -> None:
    guard, progress, state, target = crossing_fixture()
    monkeypatch.setattr(guard.opportunities, "events", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(guard, "_valid_points", lambda *_args: [np.array([-1000.0, 0.0])])
    decision = guard.check(np.array([1200.0, 0.0]), target, progress, {5: state})
    assert decision.level == GuardLevel.FORCED
    assert decision.target.kind == RouteNodeKind.GUARD
    assert decision.target.channel == 5


def test_k_mid_segment_second_bearing_requests_replan(monkeypatch) -> None:
    scenario = Scenario("event", 3, tuple(
        Source(channel, (500.0, 0.0), 1500.0) for channel in range(1, 11)
    ))
    mock = MockSimulator(scenario)
    controller = DynamicOpenRouteController(mock, planner=PlannerConfig(grid_step_m=50.0))
    mock.enter()
    controller._measure(np.zeros(2), 1, 0)
    event = EmbeddedEvent(np.array([0.0, 200.0]), 1, EmbeddedEventKind.MEASURE, "test", 0.2)
    reason = controller._execute_embedded(event, None)
    assert reason == "second_bearing_obtained"
    assert np.allclose(mock.position, event.position)


def test_l_coverage_completion_advances_two_anchor_horizon() -> None:
    coverage = ordered_points(0.0, False, 1200.0)
    nodes, anchors = build_candidate_nodes(
        current_position=coverage[2], progress=DirectedSweepProgress(0.0, "CCW", math.pi / 3),
        coverage=coverage, completed_vertices={0, 1, 2}, channels={}, resolver=FakeResolver(),
    )
    assert anchors == [3, 4, 5, 6]
    assert [item.vertex for item in nodes] == [3, 4, 5, 6]


def test_source_labels_follow_successful_clear_order_not_channel_id() -> None:
    row = {
        "actions": [
            {"path": "/clear", "channel": 18, "response": {"clear_result": "success"}},
            {"path": "/clear", "channel": 5, "response": {"clear_result": "success"}},
        ]
    }
    ranks = resolution_order(row)
    points, labels = source_points([
        {"channel": 5, "position": [0, 0]},
        {"channel": 18, "position": [1, 1]},
    ], ranks)
    assert len(points) == 2
    assert labels == ["#2", "#1"]


def test_opportunity_filter_respects_bearing_limit_and_minimum_spacing(monkeypatch) -> None:
    scenario = Scenario("opportunity-filter", 8, tuple(
        Source(channel, (300.0 + channel, 250.0), 1500.0) for channel in range(1, 11)
    ))
    controller = DynamicOpenRouteController(MockSimulator(scenario))
    state = controller.channels[1]
    state.status = ChannelStatus.FOUND
    state.bearing_count = controller.planner.max_bearings_before_fallback
    captured = {}

    def fake_events(leg, channels):
        captured["channels"] = channels
        return [EmbeddedEvent(np.array([5.0, 0.0]), 2, EmbeddedEventKind.MEASURE, "near", 0.1)]

    monkeypatch.setattr(controller.opportunity_planner, "events", fake_events)
    target = node(RouteNodeKind.COVERAGE, 100.0, 0.0, vertex=2)
    guard = GuardDecision(GuardLevel.NONE, None, target, None, None, 0.0)
    assert controller._opportunity_events(np.zeros(2), target, guard) == []
    assert 1 not in captured["channels"]


def test_low_impact_extra_bearing_does_not_require_replan(monkeypatch) -> None:
    scenario = Scenario("opportunity-significance", 9, tuple(
        Source(channel, (300.0 + channel, 250.0), 1500.0) for channel in range(1, 11)
    ))
    controller = DynamicOpenRouteController(MockSimulator(scenario))
    controller.channels[1].status = ChannelStatus.FOUND
    controller.channels[1].bearing_count = 2
    controller.client.enter()
    monkeypatch.setattr(controller, "_record_measure", lambda *args, **kwargs: None)
    event = EmbeddedEvent(np.array([100.0, 0.0]), 1, EmbeddedEventKind.MEASURE, "extra", 0.5)
    assert controller._execute_embedded(event, None) == "opportunistic_belief_change"
    assert controller._last_embedded_causes_replan is False


def test_m_localization_stages_are_independent_of_lifecycle() -> None:
    planner = PlannerConfig(rough_localization_diameter_m=100.0)
    assert localization_stage(FakeState(1, (500, 0), radius_m=60), planner) == LocalizationStage.BROAD
    assert localization_stage(FakeState(2, (500, 0), radius_m=50), planner) == LocalizationStage.ROUGH
    assert localization_stage(FakeState(3, (500, 0), radius_m=5, safe=True), planner) == LocalizationStage.CLEARABLE
    edge = FakeState(4, (1000, 0), bearing_count=1, radius_m=300)
    edge.history = [
        Observation((0.0, 0.0), "no_signal", None, 0),
        Observation((500.0, 0.0), "direction", 0.0, 1),
    ]
    assert localization_stage(edge, planner) == LocalizationStage.EDGE_LOCALIZING
    edge.bearing_count = 2
    edge.history.append(Observation((800.0, 200.0), "direction", 20.0, None))
    assert localization_stage(edge, planner) == LocalizationStage.EDGE_LOCALIZING


def test_n_coverage_vertex_active_revisit_prioritizes_found_broad(monkeypatch) -> None:
    controller = DynamicOpenRouteController(MockSimulator(Scenario(
        "revisit", 1, tuple(Source(c, (300 + c, 250), 1500) for c in range(1, 11))
    )))
    for state in controller.channels.values():
        state.status = ChannelStatus.ABSENT
    state = controller.channels[18]
    state.status = ChannelStatus.FOUND
    controller.progress = DirectedSweepProgress(
        math.atan2(controller.coverage[1, 1], controller.coverage[1, 0]), "CCW"
    )
    bearing = math.degrees(math.atan2(controller.coverage[2, 1], controller.coverage[2, 0])) + 10.0
    state.history = [Observation((0.0, 0.0), "direction", bearing, 0)]
    controller.opportunity_planner.reception_class = lambda *_args: "possible"
    controller.opportunity_planner.measurement_geometry = lambda *_args: (300.0, 45.0)
    calls = []
    monkeypatch.setattr(
        controller, "_record_measure",
        lambda point, channel, reason, **kwargs: calls.append((channel, reason)) or True,
    )
    controller._scan_unknown_coverage(1)
    assert calls == [(18, "coverage_found_revisit")]


def test_o_possible_opportunity_requires_information_geometry() -> None:
    state = FakeState(9, (1000.0, 1000.0), bearing_count=1, radius_m=500.0)
    state.history = [Observation((0.0, 0.0), "direction", 45.0, 0)]
    planner = OpportunityPlanner(PhysicalConfig(), PlannerConfig(shared_min_sin_angle=0.1))
    events = planner.events(
        RouteLeg(np.array([0.0, 0.0]), np.array([1000.0, 0.0]), "segment", -1),
        {9: state}, allow_possible=True,
    )
    assert events and events[0].reception_class == "possible"


def test_p_impossible_opportunity_is_rejected() -> None:
    state = FakeState(9, (3000.0, 3000.0), bearing_count=1, radius_m=50.0)
    state.history = [Observation((0.0, 0.0), "direction", 45.0, 0)]
    planner = OpportunityPlanner(PhysicalConfig(), PlannerConfig(shared_min_sin_angle=0.1))
    assert planner.events(
        RouteLeg(np.array([0.0, 0.0]), np.array([1000.0, 0.0]), "segment", -1),
        {9: state}, allow_possible=True,
    ) == []


def test_q_broad_guard_remains_after_second_bearing() -> None:
    guard = AngularCrossingGuard(PhysicalConfig(), PlannerConfig())
    state = FakeState(9, (1000.0, 1000.0), bearing_count=2, radius_m=300.0)
    assert guard.needs_localization_guard(state)


def test_r_guard_deadline_is_monotonic() -> None:
    guard = AngularCrossingGuard(PhysicalConfig(), PlannerConfig())
    progress = DirectedSweepProgress(0.0, "CCW", maximum=0.2)
    state = FakeState(9, (1000.0, 1000.0), bearing_count=2, radius_m=300.0)
    first = guard.guard_progress(state, progress)
    guard._historical_deadlines[state.channel] = first
    state._center = np.asarray((700.0, 700.0))
    assert guard.guard_progress(state, progress) >= first


def test_s_revisit_vertices_are_the_two_before_origin_bearing() -> None:
    controller = DynamicOpenRouteController(MockSimulator(Scenario(
        "revisit-window", 2, tuple(Source(c, (300 + c, 250), 1500) for c in range(1, 11))
    )))
    controller.coverage = ordered_points(0.0, False, 1200.0)
    controller.progress = DirectedSweepProgress(0.0, "CCW")
    state = FakeState(19, (500.0, 0.0), bearing_count=1)
    state.history = [Observation((0.0, 0.0), "direction", 190.0, 0)]
    assert controller._origin_revisit_vertices(state) == {3, 4}


def test_t_rough_service_competes_with_coverage_by_route_cost() -> None:
    planner = DynamicOpenRoutePlanner(PhysicalConfig(), PlannerConfig())
    rough = RouteNode(
        RouteNodeKind.SOURCE, np.array([800.0, 0.0]), channel=19,
        reason="service_rough_certificate_center", operation_cost_s=5.0,
    )
    broad = RouteNode(
        RouteNodeKind.SOURCE, np.array([10.0, 0.0]), channel=13,
        reason="service_transverse", operation_cost_s=5.0,
    )
    coverage = node(RouteNodeKind.COVERAGE, 20.0, 0.0, vertex=4)
    assert planner.plan(np.zeros(2), 1, [coverage, broad, rough]).first_target is broad


def test_u_clearable_source_is_not_hidden_behind_sweep_horizon() -> None:
    coverage = ordered_points(0.0, False, 1200.0)
    state = FakeState(19, (1000.0, 0.0), bearing_count=3, radius_m=10.0, safe=True)
    nodes, _ = build_candidate_nodes(
        current_position=np.array([0.0, 1200.0]),
        progress=DirectedSweepProgress(0.0, "CCW", maximum=math.pi / 2),
        coverage=coverage, completed_vertices={0, 1, 2}, channels={19: state},
        resolver=SourceResolver(PhysicalConfig(), PlannerConfig()),
    )
    assert any(item.channel == 19 and item.action == "CLEAR" for item in nodes)


def test_u2_rough_source_is_not_hidden_behind_sweep_horizon() -> None:
    coverage = ordered_points(0.0, False, 1200.0)
    state = FakeState(19, (1000.0, 0.0), bearing_count=2, radius_m=25.0)
    nodes, _ = build_candidate_nodes(
        current_position=np.array([0.0, 1200.0]),
        progress=DirectedSweepProgress(0.0, "CCW", maximum=math.pi / 2),
        coverage=coverage, completed_vertices={0, 1, 2}, channels={19: state},
        resolver=SourceResolver(PhysicalConfig(), PlannerConfig()),
    )
    rough = next(item for item in nodes if item.channel == 19)
    assert rough.action == "MEASURE"
    assert rough.reason == "service_rough_certificate_center"


def test_v_one_source_only_once_per_macro_segment(monkeypatch) -> None:
    controller = DynamicOpenRouteController(MockSimulator(Scenario(
        "macro-segment", 4, tuple(Source(c, (300 + c, 250), 1500) for c in range(1, 11))
    )))
    for state in controller.channels.values():
        state.status = ChannelStatus.ABSENT
    controller.channels[11].status = ChannelStatus.FOUND
    captured = {}
    def fake_events(_leg, channels, **_kwargs):
        captured["channels"] = set(channels)
        return []
    monkeypatch.setattr(controller.opportunity_planner, "events", fake_events)
    target = node(RouteNodeKind.COVERAGE, 100.0, 0.0, vertex=2)
    guard = GuardDecision(GuardLevel.NONE, None, target, None, None, 0.0)
    controller._opportunity_events(np.zeros(2), target, guard, {11})
    assert 11 not in captured["channels"]


def test_w_service_measurement_clears_immediately_when_certified(monkeypatch) -> None:
    controller = DynamicOpenRouteController(MockSimulator(Scenario(
        "service-continuity", 5, tuple(Source(c, (300 + c, 250), 1500) for c in range(1, 11))
    )))
    controller.progress = DirectedSweepProgress(0.0, "CCW")
    state = controller.channels[19]
    state.status = ChannelStatus.FOUND
    monkeypatch.setattr(state, "safe_clear_point", lambda: np.array([12.0, 0.0]))
    monkeypatch.setattr(controller, "_opportunity_events", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(controller, "_record_measure", lambda *_args, **_kwargs: True)
    clears = []
    monkeypatch.setattr(controller, "_record_clear", lambda point, channel, reason, **kwargs: clears.append((channel, reason)))
    target = RouteNode(RouteNodeKind.SOURCE, np.array([10.0, 0.0]), channel=19, reason="service_rough_certificate_center")
    guard = GuardDecision(GuardLevel.NONE, None, target, None, None, 0.0)
    reason = controller._move_and_act(target, guard)
    assert reason == "source_became_clearable_and_cleared"
    assert clears == [(19, "immediate_clear_after_service_measurement")]


def test_x_possible_opportunity_waits_for_origin_bearing_window() -> None:
    controller = DynamicOpenRouteController(MockSimulator(Scenario(
        "origin-window", 6, tuple(Source(c, (300 + c, 250), 1500) for c in range(1, 11))
    )))
    controller.coverage = ordered_points(0.0, False, 1200.0)
    controller.progress = DirectedSweepProgress(0.0, "CCW")
    state = FakeState(11, (-200.0, -1000.0), bearing_count=1)
    state.history = [Observation((0.0, 0.0), "direction", 278.0, 0)]
    assert not controller._origin_localization_window_allows(state, controller.coverage[1])
    assert controller._origin_localization_window_allows(state, controller.coverage[4])


def test_y_edge_localizing_target_is_transverse_not_certificate_center() -> None:
    state = FakeState(2, (900.0, 0.0), bearing_count=1, radius_m=300.0)
    state.history = [
        Observation((0.0, 0.0), "no_signal", None, 0),
        Observation((600.0, 0.0), "direction", 0.0, 1),
    ]
    target = SourceResolver(PhysicalConfig(), PlannerConfig()).current_service_target(
        state, np.array([600.0, 0.0]), ordered_points(0.0, False, 1200.0), [2, 3]
    )
    assert target is not None
    assert target.reason == "service_edge_cross_bearing"
    assert not np.allclose(target.point, state.certificate().center)
    prior = np.asarray(state.history[-1].position) - state.certificate().center
    candidate = target.point - state.certificate().center
    cosine = float(np.dot(prior, candidate) / (np.linalg.norm(prior) * np.linalg.norm(candidate)))
    crossing_deg = math.degrees(math.acos(np.clip(cosine, -1.0, 1.0)))
    assert abs(crossing_deg - 45.0) < 1e-8
    assert np.linalg.norm(target.point) <= PhysicalConfig().target_radius_m


def test_z_guard_uses_forward_support_and_treats_passed_frontier_as_overdue(monkeypatch) -> None:
    guard = AngularCrossingGuard(PhysicalConfig(), PlannerConfig())
    progress = DirectedSweepProgress(math.radians(40.0), "CCW", math.radians(101.1))
    state = FakeState(7, (-720.0, 1250.0), bearing_count=1, radius_m=514.8)
    state.history = [
        Observation((0.0, 0.0), "no_signal", None, 0),
        Observation((-208.4, 1181.8), "direction", 120.0, 2),
    ]
    frontier = guard.guard_progress(state, progress)
    assert frontier <= progress.maximum
    monkeypatch.setattr(guard.opportunities, "events", lambda *_args, **_kwargs: [])
    monkeypatch.setattr(guard, "_valid_points", lambda *_args: [np.array([-500.0, 900.0])])
    target = node(RouteNodeKind.COVERAGE, -1127.6, 410.4, vertex=3)
    assert guard.check(np.array([-208.4, 1181.8]), target, progress, {7: state}).level != GuardLevel.NONE


def test_za_scheduled_guard_is_not_marked_complete_before_measurement(monkeypatch) -> None:
    guard, progress, state, target = crossing_fixture()
    decision = guard.check(np.array([1200.0, 0.0]), target, progress, {5: state})
    assert decision.level == GuardLevel.ZERO_DETOUR
    assert 5 not in guard._last_guard_bearing
