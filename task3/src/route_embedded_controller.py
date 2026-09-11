"""Independent route-first controller with sensing and clearing on route legs."""

from __future__ import annotations

import time

import numpy as np

from .channel_state import ChannelStatus, termination_status
from .config import PhysicalConfig, PlannerConfig
from .controller import ActionClient, RunResult, SearchController
from .opportunity_planner import (
    EmbeddedEventKind,
    OpportunityPlanner,
)
from .route_planner import RouteLeg, RoutePlanner
from .scheduler import ActionKind


class RouteEmbeddedController(SearchController):
    """Keep discovery monotonic and postpone off-backbone work to cleanup."""

    def __init__(
        self,
        client: ActionClient,
        physical: PhysicalConfig = PhysicalConfig(),
        planner: PlannerConfig = PlannerConfig(),
        known_total: int | None = None,
    ):
        # The inherited scheduler is deliberately used only after the monotonic
        # coverage phase, as a conservative and already validated cleanup path.
        super().__init__(
            client,
            mode="hybrid",
            local_family="center_approach",
            physical=physical,
            planner=planner,
            known_total=known_total,
        )
        self.route_planner = RoutePlanner(planner)
        self.opportunity_planner = OpportunityPlanner(physical, planner)
        self.embedded_measure_count = 0
        self.embedded_clear_count = 0
        self.coverage_unknown_measure_count = 0
        self.off_backbone_cleanup_actions = 0

    def _known_source_count(self) -> int:
        return sum(
            state.status in (ChannelStatus.FOUND, ChannelStatus.CLEARED)
            for state in self.channels.values()
        )

    def _scan_unknown_coverage(self, index: int) -> None:
        """Scan discovery obligations only; FOUND channels are not batch measured."""
        point = self.coverage[index]
        unknown = [
            channel for channel, state in self.channels.items()
            if state.status == ChannelStatus.UNKNOWN
        ]
        if self.client.current_channel in unknown:
            unknown.remove(self.client.current_channel)
            unknown.insert(0, self.client.current_channel)
        measured = 0
        for channel in unknown:
            self._measure(point, channel, index)
            measured += 1
            self.coverage_unknown_measure_count += 1
            # Bootstrap is deliberately a full 20-channel scan. Later
            # milestones may stop once the problem's upper bound is reached.
            if index != 0 and self._known_source_count() == self.physical.max_sources:
                break
        self.coverage_completed.add(index)
        for state in self.channels.values():
            state.mark_absent_if_covered(len(self.coverage))
        self.diagnostics.append({
            "type": "coverage_unknown_scan",
            "phase": "bootstrap" if index == 0 else "sweep",
            "coverage_index": index,
            "position": point.tolist(),
            "unknown_measurements": measured,
        })

    def _execute_leg(self, leg: RouteLeg, direction: str) -> None:
        attempted: set[tuple[EmbeddedEventKind, int]] = set()
        while not np.allclose(
            np.asarray(self.client.position, float), leg.end,
            atol=self.planner.numeric_distance_tol_m,
        ):
            remaining_leg = RouteLeg(
                np.asarray(self.client.position, float),
                leg.end,
                leg.purpose,
                leg.coverage_target,
            )
            events = self.opportunity_planner.events(
                remaining_leg, self.channels, attempted
            )
            if not events:
                break
            event = events[0]
            attempted.add((event.kind, event.channel))
            diagnostic = {
                "type": "embedded_event",
                "phase": "sweep",
                "current_backbone_leg": leg.coverage_target,
                "sweep_direction": direction,
                "kind": event.kind.value,
                "channel": event.channel,
                "position": event.position.tolist(),
                "reason": event.reason,
                "zero_detour": True,
            }
            self.diagnostics.append(diagnostic)
            if event.kind == EmbeddedEventKind.CLEAR:
                self._clear(event.position, event.channel, True, event.reason)
                self.embedded_clear_count += 1
            else:
                was_found = self.channels[event.channel].status == ChannelStatus.FOUND
                self._measure(event.position, event.channel)
                self.embedded_measure_count += 1
                if was_found and self.channels[event.channel].status == ChannelStatus.CLEARED:
                    self.embedded_clear_count += 1
                    self.diagnostics.append({
                        "type": "embedded_event",
                        "phase": "sweep",
                        "current_backbone_leg": leg.coverage_target,
                        "sweep_direction": direction,
                        "kind": EmbeddedEventKind.CLEAR.value,
                        "channel": event.channel,
                        "position": event.position.tolist(),
                        "reason": "near_immediate_on_route",
                        "zero_detour": True,
                    })

        # Movement has no standalone command. The first UNKNOWN measurement at
        # the milestone performs the final leg segment. If none remain, an
        # already-found channel supplies a harmless move-plus-service action.
        if not np.allclose(
            np.asarray(self.client.position, float), leg.end,
            atol=self.planner.numeric_distance_tol_m,
        ):
            unknown = next(
                (state.channel for state in self.channels.values()
                 if state.status == ChannelStatus.UNKNOWN),
                None,
            )
            if unknown is not None:
                # The normal milestone scan will issue this movement.
                return
            found = next(
                (state.channel for state in self.channels.values()
                 if state.status == ChannelStatus.FOUND),
                None,
            )
            if found is not None:
                self._measure(leg.end, found)
                self.diagnostics.append({
                    "type": "embedded_event",
                    "phase": "sweep",
                    "current_backbone_leg": leg.coverage_target,
                    "sweep_direction": direction,
                    "kind": EmbeddedEventKind.MEASURE.value,
                    "channel": found,
                    "position": leg.end.tolist(),
                    "reason": "movement_carrier_after_all_channels_discovered",
                    "zero_detour": True,
                })
                self.embedded_measure_count += 1

    def _append_statistics(self, phase: str, direction: str) -> None:
        self.diagnostics.append({
            "type": "route_embedded_statistics",
            "phase": phase,
            "sweep_direction": direction,
            "embedded_measure_count": self.embedded_measure_count,
            "embedded_clear_count": self.embedded_clear_count,
            "zero_or_near_zero_detour_event_count": (
                self.embedded_measure_count + self.embedded_clear_count
            ),
            "coverage_unknown_measure_count": self.coverage_unknown_measure_count,
            "off_backbone_cleanup_actions": self.off_backbone_cleanup_actions,
        })

    def _cleanup(self, wall_start: float, direction: str) -> RunResult:
        while self.action_count < self.planner.max_actions:
            complete = len(self.coverage_completed) == len(self.coverage)
            done, reason = termination_status(self.channels, complete, self.physical)
            if done:
                self._append_statistics("complete", direction)
                self.client.exit()
                return self._result(True, reason, wall_start)
            if reason == "invalid_below_problem_lower_bound":
                self._append_statistics("cleanup", direction)
                self.client.exit()
                return self._result(False, reason, wall_start)
            if self.client.real_time_left_s() <= self.planner.real_time_reserve_s:
                self.diagnostics.append({
                    "type": "real_deadline_guard",
                    "remaining_s": self.client.real_time_left_s(),
                })
                self._append_statistics("cleanup", direction)
                self.client.exit()
                return self._result(False, "real_deadline_guard", wall_start)
            action = self.scheduler.choose(
                self.channels,
                np.asarray(self.client.position, float),
                self.client.current_channel,
                self.coverage,
                [],
                0,
            )
            self.off_backbone_cleanup_actions += 1
            self.diagnostics.append({
                "type": "off_backbone_cleanup_action",
                "phase": "cleanup",
                "kind": action.kind.value,
                "position": action.position.tolist(),
                "channel": action.channel,
                "source": action.source,
            })
            if action.kind == ActionKind.LOCALIZE:
                assert action.channel is not None
                self._measure(action.position, action.channel)
            elif action.kind == ActionKind.CLEAR:
                assert action.channel is not None
                self._clear(action.position, action.channel, action.certified, action.source)
            else:
                raise RuntimeError("cleanup scheduler returned a coverage action")
        self._append_statistics("cleanup", direction)
        self.client.exit()
        return self._result(False, "max_actions_exceeded", wall_start)

    def run(self) -> RunResult:
        wall_start = time.perf_counter()
        self.client.enter()

        # Phase 1: the origin is both bootstrap and the central coverage point.
        self._scan_unknown_coverage(0)
        origin_bearings = [
            float(observation.bearing_deg)
            for state in self.channels.values()
            for observation in state.history
            if observation.coverage_index == 0
            and observation.result == "direction"
            and observation.bearing_deg is not None
        ]
        route = self.route_planner.plan(origin_bearings)
        self.coverage = route.coverage.copy()
        self.diagnostics.append({
            "type": "route_selected",
            "phase": "bootstrap",
            "first_vertex": route.first_vertex.tolist(),
            "rotation_deg": route.rotation_deg,
            "sweep_direction": route.sweep_direction,
        })

        # Phase 2: execute each directed leg exactly once in its chosen order.
        for leg in route.legs():
            if self._known_source_count() == self.physical.max_sources:
                break
            self.diagnostics.append({
                "type": "backbone_leg",
                "phase": "sweep",
                "current_backbone_leg": leg.coverage_target,
                "sweep_direction": route.sweep_direction,
                "start": leg.start.tolist(),
                "end": leg.end.tolist(),
            })
            self._execute_leg(leg, route.sweep_direction)
            self._scan_unknown_coverage(leg.coverage_target)

        # Phase 3: no discovery detours; only remaining FOUND channels are served.
        return self._cleanup(wall_start, route.sweep_direction)
