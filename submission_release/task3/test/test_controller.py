"""End-to-end mock runs, near handling, and anti-starvation behavior."""

from __future__ import annotations

import pytest

from task3.src.config import PlannerConfig
from task3.src.controller import SearchController
from task3.src.mock_simulator import MockSimulator, Scenario, Source, random_scenario


def test_near_at_origin_is_cleared_immediately() -> None:
    sources = (Source(1, (0.0, 0.0), 1000.0),) + tuple(
        Source(c, (100.0 + c, 100.0), 1200.0) for c in range(2, 11)
    )
    scenario = Scenario("near-origin", 9, sources)
    mock = MockSimulator(scenario)
    result = SearchController(mock, planner=PlannerConfig(grid_step_m=25.0), known_total=10).run()
    first_measure = next(i for i, a in enumerate(mock.actions) if a["path"] == "/measure")
    assert mock.actions[first_measure]["channel"] == 1
    assert mock.actions[first_measure]["response"]["measure_result"] == "near"
    assert mock.actions[first_measure + 1]["path"] == "/clear"
    assert mock.actions[first_measure + 1]["response"]["clear_result"] == "success"
    assert result.success and result.clear_ratio == 1.0
    parts = result.time_breakdown
    assert result.virtual_time_s == pytest.approx(
        parts.movement_s + parts.switching_s + parts.measurement_s
        + parts.optical_s + parts.laser_s
    )
    assert result.first_discovery_time_s is not None
    assert result.mean_found_to_clear_s is not None
    assert result.per_channel_timing[1]["found_to_clear_s"] == pytest.approx(5.0)


@pytest.mark.parametrize("mode", ["two_stage", "enroute", "rolling_hard", "hybrid"])
def test_all_baselines_clear_same_random_case(mode: str) -> None:
    scenario = random_scenario(20260915)
    mock = MockSimulator(scenario)
    result = SearchController(
        mock, mode=mode, planner=PlannerConfig(grid_step_m=25.0, particle_count=32),
        known_total=scenario.total,
    ).run()
    assert result.success
    assert result.clear_ratio == 1.0
    assert set(mock.cleared) == {s.channel for s in scenario.sources}
    if result.termination_reason != "upper_bound_reached":
        assert result.coverage_completed == list(range(7))


def test_fixed_location_measurement_error_is_not_resampled() -> None:
    scenario = Scenario("fixed-error", 5, (Source(1, (500.0, 10.0), 1500.0),) * 10)
    # Duplicate source tuple is irrelevant here; channel lookup returns first.
    mock = MockSimulator(scenario)
    mock.enter()
    a = mock.measure((0.0, 0.0), 1)
    b = mock.measure((0.0, 0.0), 1)
    assert a["svd_deg"] == b["svd_deg"]


def test_random_scenario_can_fix_source_count_without_changing_default() -> None:
    fixed = random_scenario(20260911, source_count=16)
    assert fixed.total == 16
    assert len({source.channel for source in fixed.sources}) == 16
    default = random_scenario(20260911)
    assert 10 <= default.total <= 16
    with pytest.raises(ValueError, match="source_count"):
        random_scenario(20260911, source_count=17)


def test_scheduler_audit_matches_every_recorded_decision() -> None:
    scenario = random_scenario(20260916, source_count=10)
    mock = MockSimulator(scenario)
    result = SearchController(
        mock, planner=PlannerConfig(grid_step_m=25.0, particle_count=32),
        known_total=scenario.total,
    ).run()
    audits = [item for item in result.diagnostics if item["type"] == "scheduler_audit"]
    decisions = [item for item in result.diagnostics if item["type"] == "decision"]
    assert len(audits) == len(decisions) > 0
    for audit, decision in zip(audits, decisions):
        assert audit["chosen_kind"] == decision["kind"]
        assert audit["chosen_channel"] == decision["channel"]
        assert audit["chosen_score_s"] == decision["score_s"]
        assert audit["chosen_source"] == decision["source"]
        assert len(audit["channel_snapshots"]) == 20
        assert all(
            candidate["kind"] in {"LOCALIZE", "CLEAR"}
            for candidate in audit["local_candidates"]
        )
        for candidate in audit["local_candidates"]:
            if candidate["kind"] == "LOCALIZE":
                assert candidate["candidate_expected_radius_m"] is not None
