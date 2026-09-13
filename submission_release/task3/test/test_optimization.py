"""Safety and accounting tests for the opt-in 043+ experiments."""

from dataclasses import replace
import copy
import math

import numpy as np
import pytest

from task3.src.channel_state import ChannelState, ChannelStatus, Observation
from task3.src.completion_planner import (
    CompletionNode, CompletionResolver, CompletionRoutePlanner, RegionOpportunityPlanner, guaranteed_reception)
from task3.src.completion_planner import posterior_weights
from task3.src.opportunity_planner import EmbeddedEvent, EmbeddedEventKind
from task3.src.config import PhysicalConfig, PlannerConfig
from task3.src.dynamic_open_route import (
    RouteNode, RouteNodeKind, SourceResolver)
from task3.src.geometry import CellGrid, bearing_deg, max_distance_to_cells
from task3.src.mock_simulator import MockSimulator, Scenario, Source, random_scenario
from task3.src.optimized_controller import OptimizedController
from task3.src.policies import POLICIES


def state_from_cells(cells, step=5.):
    grid=CellGrid(np.array(cells,float),step,1800.)
    state=ChannelState(1,grid)
    state.status=ChannelStatus.FOUND
    state.tsp_window_armed=True
    return state


@pytest.mark.parametrize('limit',[1,12])
def test_clear_does_not_switch_or_change_next_measure_channel(limit):
    planner=CompletionRoutePlanner(PhysicalConfig(),PlannerConfig(open_route_exact_node_limit=limit))
    nodes=[RouteNode(RouteNodeKind.SOURCE,np.array([0.,0.]),channel=2,
                     action='CLEAR',operation_cost_s=5.),
           RouteNode(RouteNodeKind.SOURCE,np.array([10.,0.]),channel=1,
                     action='MEASURE',operation_cost_s=5.)]
    route=planner.plan(np.zeros(2),1,nodes)
    assert route.nodes[0].action=='CLEAR'
    assert route.cost_s==pytest.approx(12.)
    assert planner.next_channel(nodes[0],1)==1


def test_joint_choices_preserve_one_obligation_per_source_and_precedence():
    node=CompletionNode(RouteNodeKind.SOURCE,np.array([100.,300.]),channel=2,
        operation_cost_s=5.,predicted_endpoint=np.array([100.,0.]),additional_cost_s=60.)
    alternative=replace(node,point=np.array([80.,0.]),additional_cost_s=4.)
    node=replace(node,alternatives=(alternative,))
    nodes=[node,RouteNode(RouteNodeKind.COVERAGE,np.array([200.,0.]),vertex=1),
           RouteNode(RouteNodeKind.COVERAGE,np.array([250.,0.]),vertex=2)]
    original=CompletionRoutePlanner(PhysicalConfig(),PlannerConfig()).plan(np.zeros(2),1,nodes)
    optimized=CompletionRoutePlanner(PhysicalConfig(),PlannerConfig(joint_service_alternatives=True)).plan(np.zeros(2),1,nodes)
    assert optimized.cost_s<=original.cost_s
    assert len(optimized.nodes)==3
    assert [n.vertex for n in optimized.nodes if n.kind==RouteNodeKind.COVERAGE]==[1,2]
    assert sum(n.channel==2 for n in optimized.nodes)==1
    assert np.allclose(next(n.point for n in optimized.nodes if n.channel==2),alternative.point)
    assert not optimized.exact


def test_free_order_is_explicit_and_keeps_every_coverage_obligation():
    nodes=[RouteNode(RouteNodeKind.COVERAGE,np.array([100.,0.]),vertex=1),
           RouteNode(RouteNodeKind.COVERAGE,np.array([1.,0.]),vertex=2)]
    planner=CompletionRoutePlanner(PhysicalConfig(),PlannerConfig(free_coverage_order=True))
    route=planner.plan(np.zeros(2),1,nodes)
    assert [n.vertex for n in route.nodes]==[2,1]
    assert route.cost_s==pytest.approx(20.)


def test_full_cell_reception_accepts_safe_point_outside_mec_inner_disk():
    state=state_from_cells([[-500,0],[500,0]])
    point=np.array([0.,800.])
    circle=state.certificate()
    assert np.linalg.norm(point-circle.center)+circle.radius_m>1000
    assert guaranteed_reception(state,point)
    planner=RegionOpportunityPlanner(PhysicalConfig(),PlannerConfig())
    assert planner.reception_class(state,point)=='guaranteed'
    assert not guaranteed_reception(state,np.array([0.,1000.]))


def test_completion_rollout_updates_copies_not_hard_belief():
    state=state_from_cells([[x,y] for x in range(300,501,5) for y in (-5,0,5)])
    state.history=[Observation((0.,0.),'direction',0.)]
    state.bearing_count=1
    before=copy.deepcopy(state)
    planner=PlannerConfig(completion_lookahead=True,completion_sample_count=3)
    resolver=CompletionResolver(PhysicalConfig(),planner)
    result=resolver.current_service_target(state,np.array([0.,100.]),np.array([[0.,0.],[1000.,500.]]),[1])
    assert result is not None and result.action=='MEASURE'
    assert guaranteed_reception(state,result.point)
    assert np.array_equal(state.possible,before.possible)
    assert state.history==before.history and state.bearing_count==before.bearing_count
    assert state.status==before.status
    assert resolver.estimates[1].sample_count==9


def test_exhausted_local_candidates_fall_back_to_finite_cell_cover(monkeypatch):
    state=state_from_cells([[100.,0.],[150.,0.]])
    monkeypatch.setattr(SourceResolver,'current_service_target',lambda *args:None)
    resolver=CompletionResolver(PhysicalConfig(),PlannerConfig())
    target=resolver.current_service_target(state,np.zeros(2),np.zeros((1,2)),[])
    assert target.action=='CLEAR' and target.reason=='conservative_fallback'
    assert len(state.fallback_queue)==state.possible_count
    for cell in state.grid.centers[state.possible]:
        assert any(np.linalg.norm(cell-point)+state.grid.cell_radius_m<=20
                   for point in state.fallback_queue)


def controller(sources=(),**overrides):
    physical=PhysicalConfig()
    planner=PlannerConfig(**overrides)
    mock=MockSimulator(Scenario('test',7201,tuple(sources)),physical)
    return OptimizedController(mock,physical,planner)


def test_upper_bound_uses_distinct_discoveries_not_known_total():
    ctl=controller(focus_after_upper_bound_discovered=True)
    ctl.known_total=10
    for i in range(1,11):
        ctl.channels[i].status=ChannelStatus.CLEARED
    ctl._update_absence_certificates()
    assert ctl.channels[11].status==ChannelStatus.UNKNOWN
    for i in range(11,17):
        ctl.channels[i].status=ChannelStatus.FOUND
    ctl._update_absence_certificates()
    assert all(ctl.channels[i].status==ChannelStatus.ABSENT for i in range(17,21))
    assert ctl._search_complete()
    from task3.src.channel_state import termination_status
    assert not termination_status(ctl.channels,True,ctl.physical)[0]


def test_discovery_upper_bound_stops_inside_an_in_progress_scan():
    sources=[Source(i,(300.*math.cos(i),300.*math.sin(i)),1000.) for i in range(1,17)]
    ctl=controller(sources,focus_after_upper_bound_discovered=True)
    ctl.client.enter()
    ctl._scan_unknown_coverage(0)
    assert len([a for a in ctl.client.actions if a['path']=='/measure'])==16
    assert sum(s.status==ChannelStatus.FOUND for s in ctl.channels.values())==16
    assert all(ctl.channels[i].status==ChannelStatus.ABSENT for i in range(17,21))


def test_absence_certificate_is_per_channel_and_retirement_is_not_visit():
    ctl=controller(adaptive_search_certificate=True)
    ctl.channels[1].possible[:]=False
    ctl._update_absence_certificates()
    assert ctl.channels[1].status==ChannelStatus.ABSENT
    assert ctl.channels[2].status==ChannelStatus.UNKNOWN
    ctl.coverage_completed={0}
    # Every remaining unknown position is very close to V2, so other anchors
    # may retire, but at least one anchor covering all cells must remain.
    for state in ctl.channels.values():
        if state.status==ChannelStatus.UNKNOWN:
            state.possible[:]=False
            ids=state.grid.containing_cell_indices(ctl.coverage[2])
            state.possible[ids]=True
    ctl._retire_redundant_vertices()
    assert ctl.retired_vertices
    assert ctl.coverage_completed=={0}
    remaining=ctl._remaining_vertices()
    assert remaining
    cells=ctl._unknown_union()
    assert np.all(np.logical_or.reduce([
        max_distance_to_cells(ctl.coverage[i],cells,ctl.grid.half_m)<=1000 for i in remaining]))


def test_local_refinement_preserves_every_sampled_feasible_truth():
    ctl=controller(refine_certificate=True)
    source=np.array([600.,400.])
    grid=CellGrid(np.array([[x,y] for x in range(570,636,5) for y in range(370,436,5)],float),5.,1800.)
    state=ChannelState(1,grid)
    for point,error in [(np.array([0.,0.]),.95),(np.array([900.,0.]),-.95)]:
        state.apply_observation(Observation(tuple(point),'direction',bearing_deg(point,source)+error))
    before=state.certificate().radius_m
    ctl._refine(state)
    assert state.grid.step_m==2.5
    assert np.any(state.possible[state.grid.containing_cell_indices(source)])
    assert state.certificate().radius_m<=before+1e-6


def test_probe_miss_preserves_truth_and_budget_then_resumes_localizing():
    source=Source(1,(30.,0.),1000.)
    ctl=controller([source],optical_probe_limit=1,optical_probe_min_fraction=.6)
    state=state_from_cells([[0.,0.],[5.,0.],[30.,0.]])
    ctl.channels[1]=state
    assert ctl._probe_admissible(state,np.zeros(2))
    ctl.client.enter()
    ctl._record_clear(np.zeros(2),1,'bounded_optical_probe',certified=False)
    assert state.status==ChannelStatus.FOUND
    assert state.bearing_tolerance_extra_deg==0.
    assert np.any(state.possible[state.grid.containing_cell_indices(np.array(source.position))])
    assert not ctl._probe_admissible(state,np.zeros(2))
    assert not any(d['type']=='unexpected_clear_failure' for d in ctl.diagnostics)


def test_enroute_trial_miss_uses_noncertified_failure_path_and_exhausts_budget():
    ctl=controller([Source(1,(100.,0.),1000.)],opportunistic_probe_budget=1)
    state=state_from_cells([[0.,0.],[100.,0.]])
    ctl.channels[1]=state
    ctl.client.enter()
    event=EmbeddedEvent(np.zeros(2),1,EmbeddedEventKind.CLEAR,
                        'opportunistic_optical_probe',0.,'heuristic_occupancy')
    result=ctl._execute_embedded(event,None)
    assert result=='enroute_probe_missed'
    assert ctl.enroute_probe_count==1 and not ctl._last_embedded_causes_replan
    assert state.status==ChannelStatus.FOUND and state.bearing_tolerance_extra_deg==0
    assert state.possible[state.grid.containing_cell_indices(np.array([100.,0.]))].any()
    assert ctl.client.last_virtual_time_s==pytest.approx(3.)


def test_posterior_integrates_one_receiver_radius_and_does_not_change_cells():
    state=state_from_cells([[900.,0.],[1400.,0.]])
    state.history=[Observation((0.,0.),'direction',0.)]
    before=state.possible.copy()
    weights=posterior_weights(state,state.grid.centers)
    assert weights==pytest.approx([5/6,1/6])
    # Repeating the same constraint must not spuriously square its weight.
    state.history.append(state.history[0])
    assert posterior_weights(state,state.grid.centers)==pytest.approx(weights)
    assert np.array_equal(before,state.possible)


def test_moving_anchors_preserves_full_outer_coverage_and_visited_locations():
    ctl=controller(adaptive_search_certificate=True,adaptive_anchor_positions=True,
                   free_coverage_order=True)
    ctl.client.enter()
    ctl._scan_unknown_coverage(0)
    ctl._scan_unknown_coverage(1)
    before=ctl.coverage.copy()
    cells=ctl._unknown_union()
    ctl._shift_coverage_anchors()
    assert np.array_equal(before[:2],ctl.coverage[:2])
    assert np.max(np.linalg.norm(before-ctl.coverage,axis=1))>1
    remaining=ctl._remaining_vertices()
    assert np.all(np.logical_or.reduce([
        max_distance_to_cells(ctl.coverage[i],cells,ctl.grid.half_m)<=1000 for i in remaining]))
    assert any(d['type']=='coverage_anchor_shift' for d in ctl.diagnostics)


def test_near_clear_has_separate_unique_accounted_operation():
    ctl=controller([Source(1,(0.,0.),1000.)])
    ctl.client.enter()
    ctl._record_measure(np.zeros(2),1,'test')
    ops=sorted((d for d in ctl.diagnostics if d['type']=='actual_operation'),key=lambda d:d['operation_id'])
    assert [d['action'] for d in ops]==['MEASURE','CLEAR']
    assert [d['cost_s'] for d in ops]==pytest.approx([5.,5.])
    assert sum(d['cost_s'] for d in ops)==pytest.approx(ctl.client.last_virtual_time_s)


@pytest.mark.parametrize('source_count',[10,16])
def test_combined_full_clear_and_all_operation_costs(source_count):
    physical=PhysicalConfig()
    planner=PlannerConfig(**POLICIES['candidate_048_combined'].planner_overrides,
                          seed=20261190,completion_sample_count=2)
    scenario=random_scenario(20261190+source_count,source_count=source_count)
    mock=MockSimulator(scenario,physical)
    ctl=OptimizedController(mock,physical,planner,known_total=None)
    result=ctl.run()
    assert result.success and result.cleared_count==source_count
    assert not any(d['type']=='unexpected_clear_failure' for d in result.diagnostics)
    ops=sorted((d for d in result.diagnostics if d['type']=='actual_operation'),key=lambda d:d['operation_id'])
    assert len(ops)==result.action_count
    assert [d['operation_id'] for d in ops]==list(range(1,len(ops)+1))
    assert sum(d['cost_s'] for d in ops)==pytest.approx(result.virtual_time_s)
    for state,truth in [(ctl.channels[s.channel],s.position) for s in scenario.sources]:
        assert np.any(state.possible[state.grid.containing_cell_indices(np.array(truth))])


@pytest.mark.parametrize('fixed_error',[-.995,.995])
@pytest.mark.parametrize('policy',['candidate_049_joint_completion','candidate_053_free_order',
                                  'candidate_057_posterior_free','candidate_059_adaptive_probe'])
def test_joint_policy_boundary_sources_and_extreme_errors_keep_truth(fixed_error,policy):
    class ExtremeMock(MockSimulator):
        def _error_deg(self,channel,position):
            return fixed_error

    class AuditedController(OptimizedController):
        def _measure(self,point,channel,coverage_index=None):
            super()._measure(point,channel,coverage_index)
            truth=next((s.position for s in self.client.scenario.sources if s.channel==channel),None)
            if truth is not None:
                state=self.channels[channel]
                assert state.status!=ChannelStatus.ABSENT
                assert np.any(state.possible[state.grid.containing_cell_indices(np.asarray(truth))])

    # Boundary sources plus nearly collinear inner sources; minimum and
    # maximum receive radii. Same-location error stays fixed as required.
    sources=[Source(i+1,(1799.*math.cos(i*math.pi/3),1799.*math.sin(i*math.pi/3)),
                    1000. if i%2 else 1500.) for i in range(6)]
    sources += [Source(i+7,(200.+i*230.,10.),1000.) for i in range(4)]
    physical=PhysicalConfig()
    planner=PlannerConfig(**POLICIES[policy].planner_overrides,
                          seed=20261199,completion_sample_count=2)
    mock=ExtremeMock(Scenario('boundary-and-collinear',20261199,tuple(sources)),physical)
    result=AuditedController(mock,physical,planner).run()
    assert result.success and result.cleared_count==10
    assert not any(d['type']=='unexpected_clear_failure' for d in result.diagnostics)
