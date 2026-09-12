"""Stable policy registry for reproducible offline optimization."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass(frozen=True)
class PolicySpec:
    mode: str
    local_family: str
    planner_overrides: dict[str, Any] = field(default_factory=dict)
    parent_id: str | None = None
    description: str = ""
    controller: str = "legacy"


POLICIES: dict[str, PolicySpec] = {
    "B0_two_stage": PolicySpec("two_stage", "shortlist", {"local_action_limit": 3}),
    "B1_enroute": PolicySpec("enroute", "shortlist", {"local_action_limit": 3}),
    "B2_rolling_hard": PolicySpec("rolling_hard", "shortlist", {"local_action_limit": 3}),
    "B3_hybrid": PolicySpec("hybrid", "shortlist", {"local_action_limit": 3}),
    "A_geometry": PolicySpec("hybrid", "geometry", {"local_action_limit": 3}),
    "A_e_optimal": PolicySpec("hybrid", "e_optimal", {"local_action_limit": 3}),
    "A_expected_diameter": PolicySpec("hybrid", "expected_diameter", {"local_action_limit": 3}),
    "S_local_limit_1": PolicySpec("hybrid", "shortlist", {"local_action_limit": 1}),
    "S_local_limit_5": PolicySpec("hybrid", "shortlist", {"local_action_limit": 5}),
    "champion_000_geometry_baseline": PolicySpec(
        "hybrid", "geometry", {"local_action_limit": 3},
        description="Fixed-16 baseline matching the historical A_geometry configuration.",
    ),
    "candidate_001_upper_bound_focus": PolicySpec(
        "hybrid", "geometry",
        {"local_action_limit": 3, "focus_after_upper_bound_discovered": True},
        parent_id="champion_000_geometry_baseline",
        description="Stop coverage work once 16 distinct sources have been found.",
    ),
    "candidate_002_grid10": PolicySpec(
        "hybrid", "geometry", {"grid_step_m": 10.0, "local_action_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Use a 10 m conservative hard-set grid to reduce excess bearings.",
    ),
    "candidate_003_grid10_travel3e5": PolicySpec(
        "hybrid", "geometry",
        {"grid_step_m": 10.0, "local_action_limit": 3, "geometry_travel_weight": 3e-5},
        parent_id="champion_000_geometry_baseline",
        description="Grid10 with a threefold geometry travel penalty.",
    ),
    "candidate_004_grid10_travel1e4": PolicySpec(
        "hybrid", "geometry",
        {"grid_step_m": 10.0, "local_action_limit": 3, "geometry_travel_weight": 1e-4},
        parent_id="champion_000_geometry_baseline",
        description="Grid10 with a tenfold geometry travel penalty.",
    ),
    "candidate_005_grid10_offset250": PolicySpec(
        "hybrid", "geometry",
        {"grid_step_m": 10.0, "local_action_limit": 3, "local_offset_m": 250.0},
        parent_id="champion_000_geometry_baseline",
        description="Grid10 with shorter local orthogonal and ring offsets.",
    ),
    "candidate_006_grid10_offset750": PolicySpec(
        "hybrid", "geometry",
        {"grid_step_m": 10.0, "local_action_limit": 3, "local_offset_m": 750.0},
        parent_id="champion_000_geometry_baseline",
        description="Grid10 with longer local offsets for stronger intersections.",
    ),
    "candidate_007_grid10_coverage_first": PolicySpec(
        "hybrid", "geometry", {"grid_step_m": 10.0, "local_action_limit": 0},
        parent_id="champion_000_geometry_baseline",
        description="Finish the coverage route before any off-route local action.",
    ),
    "candidate_008_grid10_limit1": PolicySpec(
        "hybrid", "geometry", {"grid_step_m": 10.0, "local_action_limit": 1},
        parent_id="champion_000_geometry_baseline",
        description="Allow at most one local action between coverage vertices.",
    ),
    "candidate_009_grid10_enroute": PolicySpec(
        "enroute", "geometry", {"grid_step_m": 10.0, "route_insert_limit_m": 300.0},
        parent_id="champion_000_geometry_baseline",
        description="Permit only low-detour certified clears until coverage completes.",
    ),
    "candidate_010_grid10_route_geometry": PolicySpec(
        "hybrid", "route_geometry",
        {"grid_step_m": 10.0, "local_offset_m": 750.0, "local_action_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Break near-equal geometry choices using travel toward another channel.",
    ),
    "candidate_011_grid10_route_geometry_limit1": PolicySpec(
        "hybrid", "route_geometry",
        {"grid_step_m": 10.0, "local_offset_m": 750.0, "local_action_limit": 1},
        parent_id="champion_000_geometry_baseline",
        description="Route-aware geometry with one local action between coverage vertices.",
    ),
    "candidate_012_grid10_all_channels": PolicySpec(
        "hybrid", "geometry",
        {"grid_step_m": 10.0, "local_offset_m": 750.0, "local_channel_limit": 20},
        parent_id="champion_000_geometry_baseline",
        description="Score all found channels instead of a nearest-three shortlist.",
    ),
    "candidate_013_grid10_route_all_channels": PolicySpec(
        "hybrid", "route_geometry",
        {"grid_step_m": 10.0, "local_offset_m": 750.0, "local_channel_limit": 20},
        parent_id="champion_000_geometry_baseline",
        description="Combine route-aware measurement points with an all-channel shortlist.",
    ),
    "candidate_014_grid5_offset750": PolicySpec(
        "hybrid", "geometry",
        {"grid_step_m": 5.0, "local_offset_m": 750.0, "local_channel_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Use a 5 m hard-set grid with the stronger 750 m intersection offset.",
    ),
    "candidate_015_grid10_multi_geometry": PolicySpec(
        "hybrid", "multi_geometry",
        {"grid_step_m": 10.0, "local_offset_m": 750.0, "geometry_travel_weight": 1e-5},
        parent_id="champion_000_geometry_baseline",
        description="Choose measurements using all historical bearing directions.",
    ),
    "candidate_016_grid10_multi_geometry_travel1e3": PolicySpec(
        "hybrid", "multi_geometry",
        {"grid_step_m": 10.0, "local_offset_m": 750.0, "geometry_travel_weight": 1e-3},
        parent_id="champion_000_geometry_baseline",
        description="All-bearing angular information with a moderate travel penalty.",
    ),
    "candidate_017_grid10_multi_geometry_travel5e3": PolicySpec(
        "hybrid", "multi_geometry",
        {"grid_step_m": 10.0, "local_offset_m": 750.0, "geometry_travel_weight": 5e-3},
        parent_id="champion_000_geometry_baseline",
        description="All-bearing angular information with a strong travel penalty.",
    ),
    "candidate_018_grid5_multi_geometry_travel1e3": PolicySpec(
        "hybrid", "multi_geometry",
        {"grid_step_m": 5.0, "local_offset_m": 750.0, "geometry_travel_weight": 1e-3},
        parent_id="champion_000_geometry_baseline",
        description="Finer hard grid plus all-bearing angular information.",
    ),
    "candidate_019_grid10_center_approach": PolicySpec(
        "hybrid", "center_approach", {"grid_step_m": 10.0, "local_channel_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Approach a hard-set center so localization movement also advances clearing.",
    ),
    "candidate_020_grid5_center_approach": PolicySpec(
        "hybrid", "center_approach", {"grid_step_m": 5.0, "local_channel_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Center-approach policy with a finer conservative grid.",
    ),
    "candidate_021_grid10_centroid_approach": PolicySpec(
        "hybrid", "centroid_approach", {"grid_step_m": 10.0, "local_channel_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Always approach the centroid of the retained hard cells.",
    ),
    "candidate_022_grid10_mec_approach": PolicySpec(
        "hybrid", "mec_approach", {"grid_step_m": 10.0, "local_channel_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Always approach the current safe outer MEC center.",
    ),
    "candidate_023_grid10_chebyshev_approach": PolicySpec(
        "hybrid", "chebyshev_approach", {"grid_step_m": 10.0, "local_channel_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Always approach the convex-hull Chebyshev center.",
    ),
    "candidate_024_grid5_centroid_approach": PolicySpec(
        "hybrid", "centroid_approach", {"grid_step_m": 5.0, "local_channel_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Centroid approach with a finer conservative grid.",
    ),
    "candidate_025_grid10_center_shared1": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 10.0, "shared_measurement_limit": 1},
        parent_id="champion_000_geometry_baseline",
        description="Take at most one safe shared bearing at each local stop.",
    ),
    "candidate_026_grid10_center_shared3": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 10.0, "shared_measurement_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Take at most three safe shared bearings at each local stop.",
    ),
    "candidate_027_grid10_geometry750_shared3": PolicySpec(
        "hybrid", "geometry",
        {"grid_step_m": 10.0, "local_offset_m": 750.0, "shared_measurement_limit": 3},
        parent_id="champion_000_geometry_baseline",
        description="Combine strong geometry candidates with safe shared bearings.",
    ),
    "candidate_028_grid10_center_adaptive16": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 10.0, "max_bearings_before_fallback": 8,
         "fallback_cell_threshold": 16},
        parent_id="champion_000_geometry_baseline",
        description="Fallback at 16 cells; otherwise allow up to eight bearings.",
    ),
    "candidate_029_grid10_center_adaptive32": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 10.0, "max_bearings_before_fallback": 8,
         "fallback_cell_threshold": 32},
        parent_id="champion_000_geometry_baseline",
        description="Fallback at 32 cells; otherwise allow up to eight bearings.",
    ),
    "candidate_030_grid10_center_adaptive64": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 10.0, "max_bearings_before_fallback": 8,
         "fallback_cell_threshold": 64},
        parent_id="champion_000_geometry_baseline",
        description="Fallback at 64 cells; otherwise allow up to eight bearings.",
    ),
    "candidate_031_grid10_center_adaptive128": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 10.0, "max_bearings_before_fallback": 8,
         "fallback_cell_threshold": 128},
        parent_id="champion_000_geometry_baseline",
        description="Fallback at 128 cells; otherwise allow up to eight bearings.",
    ),
    "candidate_032_grid10_center_coverage0": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 10.0, "coverage_found_measurement_limit": 0},
        parent_id="champion_000_geometry_baseline",
        description="Skip opportunistic found-channel bearings at coverage vertices.",
    ),
    "candidate_033_grid10_center_coverage2": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 10.0, "coverage_found_measurement_limit": 2},
        parent_id="champion_000_geometry_baseline",
        description="Keep at most two found-channel bearings at each coverage vertex.",
    ),
    "candidate_034_grid10_center_coverage4": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 10.0, "coverage_found_measurement_limit": 4},
        parent_id="champion_000_geometry_baseline",
        description="Keep at most four found-channel bearings at each coverage vertex.",
    ),
    "candidate_035_grid10_center_coverage8": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 10.0, "coverage_found_measurement_limit": 8},
        parent_id="champion_000_geometry_baseline",
        description="Keep at most eight found-channel bearings at each coverage vertex.",
    ),
    "candidate_036_grid5_center_defer1": PolicySpec(
        "hybrid", "center_approach",
        {"grid_step_m": 5.0, "local_channel_limit": 3,
         "search_defer_regret_weight": 1.0},
        parent_id="candidate_020_grid5_center_approach",
        description="Candidate 020 plus one-step proximity regret for deferred local actions.",
    ),
    "candidate_038_task_queue_sweep": PolicySpec(
        "task_queue", "center_approach",
        {"grid_step_m": 5.0, "local_channel_limit": 3},
        parent_id="candidate_020_grid5_center_approach",
        description=(
            "Committed ResolveSource/AdvanceCoverage task queue with a fixed "
            "directional sweep, short-horizon route sequencing, and zero-detour "
            "opportunistic observations."
        ),
        controller="task_queue",
    ),
    "candidate_039_dynamic_open_route": PolicySpec(
        "dynamic_open_route", "center_approach",
        {"grid_step_m": 5.0, "local_channel_limit": 20},
        parent_id="candidate_038_task_queue_sweep",
        description=(
            "Dynamic open route from the physical position with two ordered "
            "coverage anchors, single-step source service, arbitrary-segment "
            "opportunities, and a hard angular crossing guard."
        ),
        controller="dynamic_open_route",
    ),
    "candidate_040_dynamic_open_route_sparse_six": PolicySpec(
        "dynamic_open_route", "center_approach",
        {"grid_step_m": 5.0, "local_channel_limit": 20,
         "orientation_strategy": "sparse_six"},
        parent_id="candidate_039_dynamic_open_route",
        description=(
            "Candidate 039 with a six-vertex sparse radial orientation: all "
            "coverage rays jointly avoid origin bearings before traversal."
        ),
        controller="dynamic_open_route",
    ),
    "candidate_041_dynamic_open_route_deferred_cross_view": PolicySpec(
        "dynamic_open_route", "center_approach",
        {"grid_step_m": 5.0, "local_channel_limit": 20,
         "orientation_strategy": "sparse_six",
         "preplanned_cross_view": True},
        parent_id="candidate_040_dynamic_open_route_sparse_six",
        description=(
            "Candidate 040 plus cancellable midpoint cross-view tasks on the "
            "coverage edge preceding an origin-radial risk vertex."
        ),
        controller="dynamic_open_route",
    ),
}


def select_policy_ids(requested: list[str] | None) -> list[str]:
    if not requested:
        return [
            "B0_two_stage", "B1_enroute", "B2_rolling_hard", "B3_hybrid",
            "A_geometry", "A_e_optimal", "A_expected_diameter",
        ]
    unknown = [policy_id for policy_id in requested if policy_id not in POLICIES]
    if unknown:
        raise ValueError(f"unknown policy IDs: {', '.join(unknown)}")
    return requested
