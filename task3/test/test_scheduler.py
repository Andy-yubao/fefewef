"""Scheduler timing and anti-starvation invariants."""

from __future__ import annotations

import numpy as np

from task3.src.channel_state import Observation, initialize_channels
from task3.src.config import PhysicalConfig, PlannerConfig
from task3.src.coverage import seven_points
from task3.src.geometry import CellGrid
from task3.src.policies import POLICIES
from task3.src.scheduler import Action, ActionKind, Scheduler


def test_local_action_limit_forces_next_coverage_point() -> None:
    physical = PhysicalConfig()
    planner = PlannerConfig(grid_step_m=25.0, local_action_limit=3)
    grid = CellGrid.target_disk(physical.target_radius_m, planner.grid_step_m)
    channels = initialize_channels(grid, physical, planner)
    channels[1].apply_observation(Observation((0.0, 0.0), "direction", 10.0, 0))
    points = seven_points()
    scheduler = Scheduler("hybrid", "shortlist", physical, planner)
    action = scheduler.choose(channels, np.zeros(2), 1, points, [1, 2, 3, 4, 5, 6], 3)
    assert action.kind == ActionKind.SEARCH
    assert np.allclose(action.position, points[1])
    assert scheduler.last_audit is not None
    assert scheduler.last_audit["type"] == "scheduler_audit"
    assert scheduler.last_audit["chosen_kind"] == "SEARCH"
    assert scheduler.last_audit["chosen_source"] == "coverage_forced"
    assert scheduler.last_audit["coverage_next_distance_m"] == float(np.linalg.norm(points[1]))
    assert scheduler.last_audit["best_localize_channel"] is None
    assert scheduler.last_audit["best_clear_channel"] is None


def test_channel_switch_cost_is_constant_not_channel_distance() -> None:
    physical = PhysicalConfig()
    assert physical.switch_s == 1.0
    current = 1
    costs = [physical.switch_s if c != current else 0.0 for c in (2, 10, 20)]
    assert costs == [1.0, 1.0, 1.0]


def test_candidate_020_registry_resolves_complete_online_configuration() -> None:
    spec = POLICIES["candidate_020_grid5_center_approach"]
    planner = PlannerConfig(**spec.planner_overrides)
    scheduler = Scheduler(spec.mode, spec.local_family, PhysicalConfig(), planner)
    assert scheduler.mode == "hybrid"
    assert scheduler.local_family == "center_approach"
    assert planner.grid_step_m == 5.0
    assert planner.local_channel_limit == 3
    assert planner.local_action_limit == 3


def test_zero_search_defer_regret_weight_preserves_scheduler_choice() -> None:
    physical = PhysicalConfig()
    planner = PlannerConfig(grid_step_m=25.0, search_defer_regret_weight=0.0)
    grid = CellGrid.target_disk(physical.target_radius_m, planner.grid_step_m)
    zero_channels = initialize_channels(grid, physical, planner)
    default_channels = initialize_channels(grid, physical, planner)
    observation = Observation((0.0, 0.0), "direction", 10.0, 0)
    zero_channels[1].apply_observation(observation)
    default_channels[1].apply_observation(observation)
    points = seven_points()

    zero_action = Scheduler("hybrid", "shortlist", physical, planner).choose(
        zero_channels, np.zeros(2), 1, points, [1, 2, 3, 4, 5, 6], 0
    )
    default_action = Scheduler(
        "hybrid", "shortlist", physical, PlannerConfig(grid_step_m=25.0)
    ).choose(default_channels, np.zeros(2), 1, points, [1, 2, 3, 4, 5, 6], 0)

    assert zero_action.kind == default_action.kind
    assert zero_action.channel == default_action.channel
    assert zero_action.score_s == default_action.score_s
    assert zero_action.source == default_action.source
    assert np.array_equal(zero_action.position, default_action.position)


def test_search_defer_regret_uses_maximum_one_step_proximity_cost() -> None:
    scheduler = Scheduler("hybrid", "shortlist", PhysicalConfig(), PlannerConfig())
    local_actions = [
        Action(ActionKind.LOCALIZE, np.array([2.0, 0.0]), 1, 0.0, "test"),
        Action(ActionKind.CLEAR, np.array([8.0, 0.0]), 2, 0.0, "test"),
    ]

    regret_s = scheduler._search_defer_regret(
        np.array([0.0, 0.0]), np.array([10.0, 0.0]), local_actions
    )

    assert regret_s == 1.2


def test_candidate_036_only_adds_defer_regret_to_candidate_020() -> None:
    baseline = POLICIES["candidate_020_grid5_center_approach"]
    candidate = POLICIES["candidate_036_grid5_center_defer1"]
    candidate_overrides = dict(candidate.planner_overrides)

    assert candidate_overrides.pop("search_defer_regret_weight") == 1.0
    assert candidate.mode == baseline.mode
    assert candidate.local_family == baseline.local_family
    assert candidate_overrides == baseline.planner_overrides
