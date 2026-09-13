"""Channel lifecycle, observation history, and termination tests."""

from __future__ import annotations

import numpy as np
import pytest

from task3.src.channel_state import (ChannelStatus, Observation,
                                     initialize_channels, termination_status)
from task3.src.config import PhysicalConfig, PlannerConfig
from task3.src.geometry import CellGrid


def make_state():
    physical = PhysicalConfig()
    planner = PlannerConfig(grid_step_m=25.0)
    grid = CellGrid.target_disk(physical.target_radius_m, planner.grid_step_m)
    return initialize_channels(grid, physical, planner), physical


def test_unknown_found_cleared_transition() -> None:
    channels, _ = make_state()
    state = channels[3]
    state.apply_observation(Observation((0.0, 0.0), "direction", 12.0, 0))
    assert state.status == ChannelStatus.FOUND
    state.mark_cleared()
    assert state.status == ChannelStatus.CLEARED


def test_unknown_absent_only_after_all_seven_coverage_points() -> None:
    channels, _ = make_state()
    state = channels[4]
    for i in range(6):
        state.apply_observation(Observation((10000.0 + i, 0.0), "no_signal", coverage_index=i))
        assert not state.mark_absent_if_covered()
    state.apply_observation(Observation((10006.0, 0.0), "no_signal", coverage_index=6))
    assert state.mark_absent_if_covered()
    assert state.status == ChannelStatus.ABSENT


def test_same_channel_same_place_not_repeated() -> None:
    channels, _ = make_state()
    state = channels[2]
    state.apply_observation(Observation((0.0, 0.0), "no_signal", coverage_index=0))
    with pytest.raises(ValueError, match="same channel"):
        state.apply_observation(Observation((0.0, 0.0), "no_signal", coverage_index=0))


def test_near_requests_immediate_clear_signal() -> None:
    channels, _ = make_state()
    state = channels[1]
    assert state.apply_observation(Observation((0.0, 0.0), "near", coverage_index=0)) is True
    assert state.status == ChannelStatus.FOUND


def test_channel_clear_certificate_requires_safe_mec_radius() -> None:
    channels, _ = make_state()
    state = channels[6]
    state.status = ChannelStatus.FOUND
    state.possible[:] = False
    state.possible[len(state.possible) // 2] = True
    assert state.safe_clear_point() is not None
    state._certificate_cache = None
    state.possible[:] = False
    left = int(np.argmin(state.grid.centers[:, 0]))
    right = int(np.argmax(state.grid.centers[:, 0]))
    state.possible[[left, right]] = True
    assert state.safe_clear_point() is None


def test_only_allowed_success_termination_conditions() -> None:
    channels, physical = make_state()
    for i in range(1, 17):
        channels[i].status = ChannelStatus.FOUND
        channels[i].mark_cleared()
    assert termination_status(channels, False, physical) == (True, "upper_bound_reached")

    channels, physical = make_state()
    for i in range(1, 11):
        channels[i].status = ChannelStatus.FOUND
        channels[i].mark_cleared()
    for i in range(11, 21):
        channels[i].status = ChannelStatus.ABSENT
    assert termination_status(channels, True, physical) == (
        True, "coverage_certificate_and_all_found_cleared"
    )


def test_below_lower_bound_is_diagnostic_not_success() -> None:
    channels, physical = make_state()
    for state in channels.values():
        state.status = ChannelStatus.ABSENT
    assert termination_status(channels, True, physical) == (False, "invalid_below_problem_lower_bound")
