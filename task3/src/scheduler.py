"""Finite-candidate receding-horizon scheduler with coverage anti-starvation."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

import numpy as np

from .channel_state import ChannelState, ChannelStatus
from .config import PhysicalConfig, PlannerConfig
from .local_planner import LocalCandidate, generate_local_candidates, select_by_family


class ActionKind(str, Enum):
    SEARCH = "SEARCH"
    LOCALIZE = "LOCALIZE"
    CLEAR = "CLEAR"


@dataclass(frozen=True)
class Action:
    kind: ActionKind
    position: np.ndarray
    channel: int | None
    score_s: float
    source: str
    certified: bool = False


class Scheduler:
    MODES = {"two_stage", "enroute", "rolling_hard", "hybrid"}
    FAMILIES = {
        "geometry", "e_optimal", "expected_diameter", "shortlist",
        "route_geometry", "multi_geometry", "center_approach",
        "centroid_approach", "mec_approach", "chebyshev_approach",
    }

    def __init__(self, mode: str, local_family: str, physical: PhysicalConfig,
                 planner: PlannerConfig):
        if mode not in self.MODES:
            raise ValueError(f"unknown scheduler mode {mode}")
        if local_family not in self.FAMILIES:
            raise ValueError(f"unknown local family {local_family}")
        self.mode = mode
        self.local_family = local_family
        self.physical = physical
        self.planner = planner
        self.last_audit: dict[str, object] | None = None

    def _search_defer_regret(
        self,
        position: np.ndarray,
        coverage_point: np.ndarray,
        local_actions: list[Action],
    ) -> float:
        """Return the largest one-step cost of deferring an available local action."""
        return max(
            (
                max(
                    0.0,
                    float(np.linalg.norm(coverage_point - action.position))
                    - float(np.linalg.norm(position - action.position)),
                ) / self.physical.speed_mps
                for action in local_actions
            ),
            default=0.0,
        )

    def _audit(
        self,
        actions: list[Action],
        chosen: Action,
        position: np.ndarray,
        current_channel: int,
        remaining_coverage_count: int,
        found_count: int,
        original_search_score_s: float | None = None,
    ) -> None:
        """Save a read-only summary of the candidates considered by ``choose``."""
        best = {
            kind: min(
                (action for action in actions if action.kind == kind),
                key=lambda action: action.score_s,
                default=None,
            )
            for kind in ActionKind
        }
        search = best[ActionKind.SEARCH]
        localize = best[ActionKind.LOCALIZE]
        clear = best[ActionKind.CLEAR]
        local_actions = [action for action in actions if action.kind != ActionKind.SEARCH]
        best_local = min(
            local_actions,
            key=lambda action: (action.score_s, action.kind != ActionKind.CLEAR),
            default=None,
        )
        defer_regret_s = (
            self._search_defer_regret(position, search.position, local_actions)
            if search is not None else 0.0
        )
        original_search_score_s = (
            search.score_s
            if search is not None and original_search_score_s is None
            else original_search_score_s
        )
        shadow_adjusted_search_score_s = (
            original_search_score_s + defer_regret_s
            if original_search_score_s is not None else None
        )
        would_flip = bool(
            search is not None
            and best_local is not None
            and shadow_adjusted_search_score_s is not None
            and best_local.score_s < shadow_adjusted_search_score_s
        )
        audit: dict[str, object] = {
            "type": "scheduler_audit",
            "current_position": np.asarray(position, float).tolist(),
            "current_channel": current_channel,
            "remaining_coverage_count": remaining_coverage_count,
            "found_count": found_count,
            "coverage_next_position": search.position.tolist() if search is not None else None,
            "coverage_next_distance_m": (
                float(np.linalg.norm(search.position - position)) if search is not None else None
            ),
            "coverage_next_score_s": search.score_s if search is not None else None,
            "best_localize_channel": localize.channel if localize is not None else None,
            "best_localize_position": localize.position.tolist() if localize is not None else None,
            "best_localize_distance_m": (
                float(np.linalg.norm(localize.position - position)) if localize is not None else None
            ),
            "best_localize_score_s": localize.score_s if localize is not None else None,
            "best_localize_source": localize.source if localize is not None else None,
            "best_clear_channel": clear.channel if clear is not None else None,
            "best_clear_position": clear.position.tolist() if clear is not None else None,
            "best_clear_distance_m": (
                float(np.linalg.norm(clear.position - position)) if clear is not None else None
            ),
            "best_clear_score_s": clear.score_s if clear is not None else None,
            "best_clear_source": clear.source if clear is not None else None,
            "chosen_kind": chosen.kind.value,
            "chosen_channel": chosen.channel,
            "chosen_score_s": chosen.score_s,
            "chosen_source": chosen.source,
            "defer_regret_s": defer_regret_s,
            "original_search_score_s": original_search_score_s,
            "adjusted_search_score_s": shadow_adjusted_search_score_s,
            "original_best_local_score_s": best_local.score_s if best_local is not None else None,
            "would_flip": would_flip,
            "would_flip_to_kind": best_local.kind.value if would_flip else None,
            "would_flip_to_channel": best_local.channel if would_flip else None,
        }
        if chosen.kind == ActionKind.SEARCH:
            audit["search_minus_best_localize_s"] = (
                chosen.score_s - localize.score_s if localize is not None else None
            )
            audit["search_minus_best_clear_s"] = (
                chosen.score_s - clear.score_s if clear is not None else None
            )
        self.last_audit = audit

    def _remaining_search_cost(self, position: np.ndarray, coverage: np.ndarray,
                               remaining: list[int], unknown_count: int) -> float:
        if not remaining:
            return 0.0
        route = [np.asarray(position, float), *(coverage[i] for i in remaining)]
        distance = sum(float(np.linalg.norm(b - a)) for a, b in zip(route, route[1:]))
        scan = len(remaining) * unknown_count * self.physical.measure_s
        switch = len(remaining) * max(0, unknown_count - 1) * self.physical.switch_s
        return distance / self.physical.speed_mps + scan + switch

    def _found_cost(self, found: list[ChannelState],
                    radius_override: dict[int, float] | None = None,
                    removed: set[int] | None = None) -> float:
        """Common finite-horizon proxy applied to every action on equal footing."""
        radius_override = {} if radius_override is None else radius_override
        removed = set() if removed is None else removed
        total = 0.0
        threshold = self.physical.clear_radius_m - self.planner.clear_margin_m
        for state in found:
            if state.channel in removed:
                continue
            radius = radius_override.get(state.channel, state.certificate().radius_m)
            if radius <= threshold:
                total += self.physical.optical_s + self.physical.laser_s
                continue
            measurements = max(1, min(
                self.planner.max_bearings_before_fallback - state.bearing_count,
                int(math.ceil(math.log(max(radius / threshold, 1.0), 2.0))),
            ))
            total += measurements * (self.physical.measure_s + self.physical.switch_s)
            total += radius / self.physical.speed_mps
            total += self.physical.optical_s + self.physical.laser_s
        return total

    def choose(
        self,
        channels: dict[int, ChannelState],
        position: np.ndarray,
        current_channel: int,
        coverage: np.ndarray,
        remaining_coverage: list[int],
        consecutive_local: int,
    ) -> Action:
        unknown_count = sum(s.status == ChannelStatus.UNKNOWN for s in channels.values())
        found = [s for s in channels.values() if s.status == ChannelStatus.FOUND]
        # Hard clear/fallback status is checked for every found channel. Expensive
        # local candidate construction is restricted to a rolling nearest-three
        # shortlist; after one is cleared, downstream channels enter the list.
        local_channel_ids = {
            s.channel for s in sorted(
                found,
                key=lambda state: float(np.linalg.norm(state.certificate().center - position)),
            )[:self.planner.local_channel_limit]
        }
        if remaining_coverage and (self.mode == "two_stage" or consecutive_local >= self.planner.local_action_limit):
            p = coverage[remaining_coverage[0]]
            score = self._remaining_search_cost(position, coverage, remaining_coverage, unknown_count)
            chosen = Action(ActionKind.SEARCH, p, None, score, "coverage_forced")
            self._audit(
                [chosen], chosen, position, current_channel, len(remaining_coverage), len(found)
            )
            return chosen

        actions: list[Action] = []
        found_tail = self._found_cost(found)
        if remaining_coverage:
            p = coverage[remaining_coverage[0]]
            immediate = (float(np.linalg.norm(p - position)) / self.physical.speed_mps
                         + unknown_count * self.physical.measure_s
                         + max(0, unknown_count - 1) * self.physical.switch_s)
            residual_search = self._remaining_search_cost(
                p, coverage, remaining_coverage[1:], unknown_count
            )
            # Opportunistic bearings at the mandatory stop are useful but their
            # geometry is scenario-dependent; do not credit an unobserved gain.
            actions.append(Action(ActionKind.SEARCH, p, None,
                                  immediate + residual_search + found_tail,
                                  "coverage_next"))

        for state in found:
            safe = state.safe_clear_point()
            if safe is not None:
                travel = float(np.linalg.norm(safe - position)) / self.physical.speed_mps
                detour = 0.0
                if remaining_coverage:
                    nxt = coverage[remaining_coverage[0]]
                    detour = (np.linalg.norm(safe - position) + np.linalg.norm(nxt - safe)
                              - np.linalg.norm(nxt - position))
                if self.mode != "enroute" or detour <= self.planner.route_insert_limit_m:
                    actions.append(Action(ActionKind.CLEAR, safe, state.channel,
                                          travel + self.physical.optical_s + self.physical.laser_s
                                          + self._remaining_search_cost(safe, coverage, remaining_coverage, unknown_count)
                                          + self._found_cost(found, removed={state.channel}),
                                          "mec_certificate", True))
                continue
            if (
                state.bearing_count >= self.planner.max_bearings_before_fallback
                or (
                    self.planner.fallback_cell_threshold > 0
                    and state.possible_count <= self.planner.fallback_cell_threshold
                )
            ):
                state.activate_fallback(position)
                point = state.next_fallback_point(position)
                if point is not None:
                    travel = float(np.linalg.norm(point - position)) / self.physical.speed_mps
                    actions.append(Action(ActionKind.CLEAR, point, state.channel,
                                          travel + self.physical.optical_s
                                          + self._remaining_search_cost(point, coverage, remaining_coverage, unknown_count)
                                          + 0.5 * self._found_cost(found),
                                          "finite_cell_cover", False))
                continue
            if self.mode in ("two_stage", "enroute") and remaining_coverage:
                continue
            if state.channel not in local_channel_ids:
                continue
            candidates = generate_local_candidates(
                state, position, coverage, remaining_coverage,
                use_particles=self.mode == "hybrid",
            )
            if candidates:
                next_points = [
                    other.certificate().center for other in found
                    if other.channel != state.channel
                ]
                chosen = select_by_family(
                    candidates, self.local_family, position, self.planner, next_points
                )
                travel = float(np.linalg.norm(chosen.point - position)) / self.physical.speed_mps
                switch = self.physical.switch_s if state.channel != current_channel else 0.0
                score = (travel + switch + self.physical.measure_s
                         + self._remaining_search_cost(chosen.point, coverage, remaining_coverage, unknown_count)
                         + self._found_cost(found, {state.channel: chosen.expected_radius_m})
                         + self.planner.tail_weight * chosen.p90_radius_m / self.physical.speed_mps)
                actions.append(Action(ActionKind.LOCALIZE, chosen.point, state.channel, score, chosen.source))

        if not actions:
            raise RuntimeError("no finite action while task is incomplete")
        original_search_score_s = None
        if remaining_coverage and self.planner.search_defer_regret_weight != 0.0:
            search_index = next(
                (index for index, action in enumerate(actions)
                 if action.kind == ActionKind.SEARCH),
                None,
            )
            local_actions = [
                action for action in actions if action.kind != ActionKind.SEARCH
            ]
            if search_index is not None and local_actions:
                search = actions[search_index]
                original_search_score_s = search.score_s
                regret_s = self._search_defer_regret(
                    position, search.position, local_actions
                )
                actions[search_index] = Action(
                    search.kind,
                    search.position,
                    search.channel,
                    search.score_s
                    + self.planner.search_defer_regret_weight * regret_s,
                    search.source,
                    search.certified,
                )
        chosen = min(actions, key=lambda a: (a.score_s, a.kind != ActionKind.CLEAR))
        self._audit(
            actions,
            chosen,
            position,
            current_channel,
            len(remaining_coverage),
            len(found),
            original_search_score_s,
        )
        return chosen
