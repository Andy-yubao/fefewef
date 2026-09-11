"""Scheduler timing and anti-starvation invariants."""

from __future__ import annotations

import numpy as np

from task3.src.channel_state import Observation, initialize_channels
from task3.src.config import PhysicalConfig, PlannerConfig
from task3.src.coverage import seven_points
from task3.src.geometry import CellGrid
from task3.src.policies import POLICIES
from task3.src.scheduler import ActionKind, Scheduler


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
