"""Controller for candidate 039's dynamic open-route architecture."""

from __future__ import annotations

import math
import time
from typing import Any

import numpy as np

from .channel_state import ChannelStatus, termination_status
from .config import PhysicalConfig, PlannerConfig
from .controller import ActionClient, RunResult, SearchController
from .dynamic_open_route import (
    AngularCrossingGuard,
    DirectedSweepProgress,
    DynamicOpenRoutePlanner,
    GuardDecision,
    GuardLevel,
    LocalizationStage,
    RouteNode,
    RouteNodeKind,
    SourceResolver,
    build_candidate_nodes,
    localization_stage,
)
from .opportunity_planner import EmbeddedEvent, EmbeddedEventKind, OpportunityPlanner
from .route_planner import RouteLeg, RoutePlanner


class DynamicOpenRouteController(SearchController):
    """Plan from the physical position, commit one node, observe, and replan."""

    def __init__(
        self,
        client: ActionClient,
        physical: PhysicalConfig = PhysicalConfig(),
        planner: PlannerConfig = PlannerConfig(),
        known_total: int | None = None,
    ) -> None:
        super().__init__(
            client, mode="hybrid", local_family="center_approach",
            physical=physical, planner=planner, known_total=known_total,
        )
        self.sweep_direction = "CCW"
        self.progress: DirectedSweepProgress | None = None
        self.resolver = SourceResolver(physical, planner)
        self.open_route_planner = DynamicOpenRoutePlanner(physical, planner)
        self.crossing_guard = AngularCrossingGuard(physical, planner)
        self.opportunity_planner = OpportunityPlanner(physical, planner)
        self.replan_count = 0
        self.guard_measurement_count = 0
        self.opportunistic_measure_count = 0
        self.opportunistic_clear_count = 0
        self.coverage_revisit_count = 0
        self.coverage_revisit_direction_count = 0
        self.preplanned_cross_view_count = 0
        self._coverage_revisit_directions_by_channel: dict[int, int] = {}
        self._possible_opportunity_attempts: dict[int, int] = {}
        self.source_resolution_order: dict[int, int] = {}
        self._last_embedded_causes_replan = False

    def _state_signature(self, channel: int) -> tuple[str, int, int, float]:
        state = self.channels[channel]
        radius = state.certificate().radius_m if state.status == ChannelStatus.FOUND else float("inf")
        return state.status.value, state.bearing_count, state.possible_count, float(radius)

    def _certificate_is_ahead(self, state: Any) -> bool:
        """Whether the certificate center remains inside the unfinished sweep."""
        if self.progress is None:
            return False
        remaining = [
            index for index in range(1, len(self.coverage))
            if index not in self.coverage_completed
        ]
        if not remaining:
            return False
        current = self.progress.maximum
        source = self.progress.unwrapped(state.certificate().center, current)
        while source < current - 1e-9:
            source += 2.0 * math.pi
        horizon = self.progress.unwrapped(self.coverage[remaining[-1]], current)
        while horizon < current - 1e-9:
            horizon += 2.0 * math.pi
        return source <= horizon + 1e-9

    def _refresh_localization_debt(self, state: Any) -> None:
        if state.status != ChannelStatus.FOUND or state.localization_debt:
            return
        origin_no_signal = any(
            obs.coverage_index == 0 and obs.result == "no_signal"
            for obs in state.history
        )
        non_origin_direction = any(
            obs.result == "direction" and obs.coverage_index != 0
            for obs in state.history
        )
        if not (origin_no_signal and non_origin_direction):
            return
        diameter = 2.0 * float(state.certificate().radius_m)
        ahead = self._certificate_is_ahead(state)
        threshold = (
            self.planner.edge_localization_forward_diameter_m
            if ahead else self.planner.edge_localization_diameter_m
        )
        if diameter <= threshold:
            state.localization_debt = True
            state.localization_debt_direction = "forward" if ahead else "reverse"

    def _refresh_tsp_window(self, state: Any) -> None:
        """Latch admission once reliable angular support meets [-30, +90]."""
        if (
            self.progress is None
            or state.status != ChannelStatus.FOUND
            or state.tsp_window_armed
        ):
            return
        circle = state.certificate()
        distance = float(np.linalg.norm(circle.center))
        if distance <= circle.radius_m + self.planner.numeric_distance_tol_m:
            # A circle containing the origin has no reliable polar interval.
            return
        half = math.asin(min(1.0, circle.radius_m / distance))
        center = self.progress.unwrapped(circle.center, self.progress.maximum)
        support_low = center - half
        support_high = center + half
        window_low = self.progress.maximum - math.radians(self.planner.tsp_window_backward_deg)
        window_high = self.progress.maximum + math.radians(self.planner.tsp_window_forward_deg)
        if support_high >= window_low - 1e-9 and support_low <= window_high + 1e-9:
            state.tsp_window_armed = True
            state.tsp_window_entry_progress = self.progress.maximum

    def _initialize_cross_view_tasks(self) -> None:
        """Schedule one edge observation for each origin-radial risk source."""
        if not self.planner.preplanned_cross_view or self.progress is None:
            return
        vertex_angles = np.asarray([
            math.atan2(float(point[1]), float(point[0]))
            for point in self.coverage[1:]
        ])
        limit = math.radians(self.planner.preplanned_collinear_angle_deg)
        fraction = self.planner.preplanned_cross_view_fraction
        for state in self.channels.values():
            origin = next((
                obs for obs in state.history
                if obs.coverage_index == 0 and obs.result == "direction"
                and obs.bearing_deg is not None
            ), None)
            if origin is None:
                continue
            bearing = math.radians(float(origin.bearing_deg))
            separation = np.abs((vertex_angles - bearing + math.pi) % (2.0 * math.pi) - math.pi)
            vertex = int(np.argmin(separation)) + 1
            if vertex <= 1 or float(separation[vertex - 1]) > limit:
                continue
            estimate = state.certificate().center
            ray = np.array([math.cos(bearing), math.sin(bearing)])
            projected = float(np.dot(estimate, ray))
            if not (0.0 < projected <= self.planner.ring_radius_m + 1e-9):
                continue
            point = (
                (1.0 - fraction) * self.coverage[vertex - 1]
                + fraction * self.coverage[vertex]
            )
            state.cross_view_point = tuple(map(float, point))
            state.cross_view_edge = vertex
            state.cross_view_armed = False

    def _refresh_cross_view_window(self, state: Any) -> None:
        if self.progress is None or state.cross_view_point is None:
            return
        if (
            state.status != ChannelStatus.FOUND
            or localization_stage(state, self.planner) in {
                LocalizationStage.ROUGH, LocalizationStage.CLEARABLE,
            }
            or state.already_measured(np.asarray(state.cross_view_point, float))
        ):
            state.cross_view_point = None
            state.cross_view_edge = None
            state.cross_view_armed = False
            return
        point = np.asarray(state.cross_view_point, float)
        task_progress = self.progress.unwrapped(point, self.progress.maximum)
        backward = math.radians(self.planner.tsp_window_backward_deg)
        forward = math.radians(self.planner.tsp_window_forward_deg)
        if (
            task_progress <= self.progress.maximum + forward + 1e-9
            and task_progress >= self.progress.maximum - backward - 1e-9
        ):
            state.cross_view_armed = True

    def _record_measure(
        self, point: np.ndarray, channel: int, reason: str,
        *, opportunistic: bool = False, guard: bool = False,
        coverage_index: int | None = None,
        reception_class: str = "unknown",
        baseline_m: float | None = None,
        view_angle_gain_deg: float | None = None,
    ) -> bool:
        point = np.asarray(point, float)
        start = np.asarray(self.client.position, float)
        before = self._state_signature(channel)
        history_before = len(self.channels[channel].history)
        self._measure(point, channel, coverage_index)
        if self.progress is not None:
            self.progress.maximum = max(
                self.progress.maximum,
                self.progress.segment_new_max(start, point),
            )
        after = self._state_signature(channel)
        state = self.channels[channel]
        self._refresh_localization_debt(state)
        self._refresh_tsp_window(state)
        self._refresh_cross_view_window(state)
        if self.progress is not None and state.status == ChannelStatus.FOUND:
            self.crossing_guard.note_observation(state, self.progress)
            # A guard that returned no new bearing has still consumed its
            # current debt.  A successful direction increments bearing_count,
            # naturally creating a fresh deadline for the refined belief.
            if guard and after[1] == before[1]:
                self.crossing_guard.mark_no_bearing_guard_complete(state)
        result = state.history[-1].result if len(state.history) > history_before else "skipped_duplicate"
        certificate = state.certificate() if state.status == ChannelStatus.FOUND else None
        self.diagnostics.append({
            "type": "dynamic_action",
            "action_kind": "MEASURE",
            "channel": channel,
            "start": start.tolist(),
            "end": point.tolist(),
            "reason": reason,
            "opportunistic": opportunistic,
            "guard": guard,
            "belief_changed": before != after,
            "measure_result": result,
            "measurement_reason": reason,
            "reception_class": reception_class,
            "baseline_m": baseline_m,
            "view_angle_gain_deg": view_angle_gain_deg,
            "localization_stage": localization_stage(state, self.planner).value if certificate is not None else None,
            "certificate_center": certificate.center.tolist() if certificate is not None else None,
            "certificate_radius_m": float(certificate.radius_m) if certificate is not None else None,
            "certificate_diameter_m": 2.0 * float(certificate.radius_m) if certificate is not None else None,
            "localization_debt": bool(getattr(state, "localization_debt", False)),
            "localization_debt_direction": getattr(state, "localization_debt_direction", None),
            "tsp_window_armed": bool(getattr(state, "tsp_window_armed", False)),
        })
        if opportunistic:
            self.opportunistic_measure_count += 1
        if guard:
            self.guard_measurement_count += 1
        if reason == "preplanned_cross_view":
            self.preplanned_cross_view_count += 1
            state.cross_view_point = None
            state.cross_view_edge = None
            state.cross_view_armed = False
        return after[1] > before[1]

    def _origin_revisit_vertices(self, state: Any) -> set[int]:
        """Two coverage vertices immediately before the origin-bearing deadline."""
        if self.progress is None:
            return set()
        origin = next(
            (obs for obs in state.history if obs.coverage_index == 0
             and obs.result == "direction" and obs.bearing_deg is not None),
            None,
        )
        if origin is None:
            return set()
        angle = math.radians(float(origin.bearing_deg))
        bearing_progress = (
            self.progress.sign * (angle - self.progress.reference_angle_rad)
        ) % (2.0 * math.pi)
        candidates = sorted(
            (self.progress.raw(self.coverage[index]), index)
            for index in range(1, len(self.coverage))
            if self.progress.raw(self.coverage[index]) <= bearing_progress + 1e-9
        )
        return {index for _value, index in candidates[-2:]}

    def _origin_localization_window_allows(self, state: Any, point: np.ndarray) -> bool:
        """Delay speculative POSSIBLE sensing until the origin-bearing window."""
        if self.progress is None:
            return True
        vertices = self._origin_revisit_vertices(state)
        if not vertices:
            return True
        origin = next(
            obs for obs in state.history
            if obs.coverage_index == 0 and obs.result == "direction"
            and obs.bearing_deg is not None
        )
        bearing_progress = (
            self.progress.sign
            * (math.radians(float(origin.bearing_deg)) - self.progress.reference_angle_rad)
        ) % (2.0 * math.pi)
        window_start = min(self.progress.raw(self.coverage[index]) for index in vertices)
        candidate_progress = self.progress.raw(np.asarray(point, float))
        return window_start - 1e-9 <= candidate_progress <= bearing_progress + 1e-9

    def _record_clear(
        self, point: np.ndarray, channel: int, reason: str,
        *, opportunistic: bool = False, certified: bool = True,
    ) -> None:
        point = np.asarray(point, float)
        start = np.asarray(self.client.position, float)
        self._clear(point, channel, certified, reason)
        resolution_order = None
        if self.channels[channel].status == ChannelStatus.CLEARED:
            if channel not in self.source_resolution_order:
                self.source_resolution_order[channel] = len(self.source_resolution_order) + 1
            resolution_order = self.source_resolution_order[channel]
        self.diagnostics.append({
            "type": "dynamic_action",
            "action_kind": "CLEAR",
            "channel": channel,
            "start": start.tolist(),
            "end": point.tolist(),
            "reason": reason,
            "opportunistic": opportunistic,
            "guard": False,
            "belief_changed": True,
            "resolution_order": resolution_order,
        })
        if opportunistic:
            self.opportunistic_clear_count += 1

    def _scan_unknown_coverage(self, index: int) -> None:
        point = self.coverage[index]
        unknown = [channel for channel, state in self.channels.items() if state.status == ChannelStatus.UNKNOWN]
        if self.client.current_channel in unknown:
            unknown.remove(self.client.current_channel)
            unknown.insert(0, self.client.current_channel)
        for channel in unknown:
            self._record_measure(
                point, channel, "coverage_unknown_scan",
                coverage_index=index,
                reception_class="guaranteed",
            )
        # Active revisit is deliberately capped and ranks broad certificates
        # ahead of rough ones; it is not a second unconditional full scan.
        revisit: list[tuple[int, float, float, int, str, float, float]] = []
        for channel, state in self.channels.items():
            if state.status != ChannelStatus.FOUND or state.safe_clear_point() is not None:
                continue
            if index not in self._origin_revisit_vertices(state):
                continue
            reception = self.opportunity_planner.reception_class(state, point)
            baseline, gain = self.opportunity_planner.measurement_geometry(state, point)
            if state.already_measured(point):
                continue
            if reception == "impossible" or (
                reception == "possible"
                and (baseline < self.planner.minimum_view_baseline_m
                     or gain < self.planner.minimum_view_angle_gain_deg)
            ):
                continue
            stage = localization_stage(state, self.planner)
            priority = 0 if stage == LocalizationStage.BROAD else 1
            revisit.append((priority, -gain, -baseline, channel, reception, baseline, gain))
        for _priority, _neg_gain, _neg_baseline, channel, reception, baseline, gain in sorted(revisit)[: self.planner.coverage_revisit_limit]:
            gained_direction = self._record_measure(
                point, channel, "coverage_found_revisit", coverage_index=index,
                reception_class=reception, baseline_m=baseline,
                view_angle_gain_deg=gain,
            )
            self.coverage_revisit_count += 1
            if gained_direction:
                self.coverage_revisit_direction_count += 1
                self._coverage_revisit_directions_by_channel[channel] = (
                    self._coverage_revisit_directions_by_channel.get(channel, 0) + 1
                )
        self.coverage_completed.add(index)
        for state in self.channels.values():
            state.mark_absent_if_covered(len(self.coverage))
        self.diagnostics.append({
            "type": "coverage_completed",
            "coverage_index": index,
            "position": point.tolist(),
            "completion_order": [
                vertex for vertex in range(1, len(self.coverage))
                if vertex in self.coverage_completed
            ],
        })

    def _opportunity_events(
        self, start: np.ndarray, target: RouteNode, guard: GuardDecision,
        excluded_measure_channels: set[int] | None = None,
    ) -> list[EmbeddedEvent]:
        excluded_measure_channels = excluded_measure_channels or set()
        excluded_channel = target.channel if target.kind != RouteNodeKind.COVERAGE else None
        eligible = {
            channel: state for channel, state in self.channels.items()
            if state.status == ChannelStatus.FOUND
            and channel != excluded_channel
            and channel not in excluded_measure_channels
            and state.bearing_count < self.planner.max_bearings_before_fallback
            and self._possible_opportunity_attempts.get(channel, 0)
                < self.planner.possible_opportunity_limit_per_source
        }
        leg = RouteLeg(start.copy(), target.point.copy(), "dynamic_segment", -1)
        try:
            candidate_events = self.opportunity_planner.events(leg, eligible, allow_possible=True)
        except TypeError:  # compatibility with narrow test doubles
            candidate_events = self.opportunity_planner.events(leg, eligible)
        events = [
            event for event in candidate_events
            if float(np.linalg.norm(event.position - start))
            >= self.planner.min_opportunistic_event_distance_m
            and (
                event.reception_class != "possible"
                or self._origin_localization_window_allows(
                    self.channels[event.channel], event.position
                )
            )
        ]
        if guard.event is not None:
            events.append(guard.event)
        unique: dict[tuple[str, int, float], EmbeddedEvent] = {}
        for event in events:
            key = (event.kind.value, event.channel, round(float(event.leg_fraction), 9))
            unique[key] = event
        return sorted(unique.values(), key=lambda event: (event.leg_fraction, event.channel))

    def _execute_embedded(self, event: EmbeddedEvent, guard_channel: int | None) -> str:
        is_guard = event.kind == EmbeddedEventKind.MEASURE and event.channel == guard_channel
        self._last_embedded_causes_replan = is_guard
        if event.kind == EmbeddedEventKind.CLEAR:
            self._record_clear(
                event.position, event.channel, event.reason,
                opportunistic=True, certified=True,
            )
            self._last_embedded_causes_replan = True
            return "source_cleared_opportunistically"
        before_signature = self._state_signature(event.channel)
        before = before_signature[1]
        before_stage = (
            localization_stage(self.channels[event.channel], self.planner)
            if self.channels[event.channel].status == ChannelStatus.FOUND else None
        )
        self._record_measure(
            event.position, event.channel, event.reason,
            opportunistic=not is_guard, guard=is_guard,
            reception_class=event.reception_class,
            baseline_m=event.baseline_m,
            view_angle_gain_deg=event.view_angle_gain_deg,
        )
        if event.reception_class == "possible":
            self._possible_opportunity_attempts[event.channel] = (
                self._possible_opportunity_attempts.get(event.channel, 0) + 1
            )
        after_signature = self._state_signature(event.channel)
        after = after_signature[1]
        after_stage = (
            localization_stage(self.channels[event.channel], self.planner)
            if self.channels[event.channel].status == ChannelStatus.FOUND else None
        )
        if before < 2 <= after:
            self._last_embedded_causes_replan = True
            return "second_bearing_obtained"
        radius_drop = before_signature[3] - after_signature[3]
        status_changed = before_signature[0] != after_signature[0]
        self._last_embedded_causes_replan = (
            self._last_embedded_causes_replan
            or status_changed
            or before_stage != after_stage
            or after_stage == LocalizationStage.CLEARABLE
            or radius_drop >= self.planner.opportunistic_replan_radius_m
            or (
                self.progress is not None
                and self.crossing_guard.is_overdue(
                    self.channels[event.channel], self.progress
                )
            )
        )
        return "opportunistic_belief_change"

    def _move_and_act(self, original_target: RouteNode, guard: GuardDecision) -> str:
        start = np.asarray(self.client.position, float)
        segment_origin = start.copy()
        target = guard.target
        pending_guard = guard
        embedded: list[EmbeddedEvent] = []
        embedded_measure_channels: set[int] = set()
        while True:
            segment_start = np.asarray(self.client.position, float)
            events = self._opportunity_events(
                segment_start, target, pending_guard, embedded_measure_channels
            )
            if not events:
                break
            event = events[0]
            embedded.append(event)
            if event.kind == EmbeddedEventKind.MEASURE:
                embedded_measure_channels.add(event.channel)
            reason = self._execute_embedded(
                event,
                pending_guard.channel if pending_guard.level == GuardLevel.ZERO_DETOUR else None,
            )
            stop = np.asarray(self.client.position, float)
            # A guard event or a route-relevant belief change must stop the
            # old plan immediately.  Low-impact extra bearings stay on the
            # same straight segment and are consumed without a route switch.
            if self._last_embedded_causes_replan:
                finish_nearby_coverage = (
                    target.kind == RouteNodeKind.COVERAGE
                    and float(np.linalg.norm(target.point - stop))
                        <= self.planner.min_opportunistic_event_distance_m
                )
                if finish_nearby_coverage:
                    # Do not abandon a coverage vertex at its doorstep merely
                    # because an embedded bearing changed localization stage.
                    self._last_embedded_causes_replan = False
                    pending_guard = GuardDecision(
                        GuardLevel.NONE, None, target, None, None, 0.0
                    )
                    break
                self.diagnostics.append({
                    "type": "movement_segment",
                    "segment_start": segment_origin.tolist(),
                    "segment_target": target.point.tolist(),
                    "target_type": target.kind.value,
                    "straight_distance": float(np.linalg.norm(target.point - segment_origin)),
                    "opportunistic_events": [
                        {"channel": item.channel, "kind": item.kind.value, "position": item.position.tolist()}
                        for item in embedded
                    ],
                    "guard_events": [guard.level.value] if guard.level != GuardLevel.NONE else [],
                    "actual_stop_position": stop.tolist(),
                    "interrupted_for_replan": True,
                })
                assert self.progress is not None
                self.progress.maximum = max(
                    self.progress.maximum,
                    self.progress.segment_new_max(segment_origin, stop),
                )
                return reason
            # The guard event has been consumed; subsequent opportunity
            # searches must not re-insert it.
            pending_guard = GuardDecision(GuardLevel.NONE, None, target, None, None, 0.0)

        if embedded:
            # Non-significant events were embedded without changing route
            # geometry; continue to the original target.
            start = np.asarray(self.client.position, float)

        if target.kind == RouteNodeKind.COVERAGE:
            assert target.vertex is not None
            self._scan_unknown_coverage(target.vertex)
            reason = "coverage_vertex_completed"
        elif target.action == "CLEAR":
            assert target.channel is not None
            if target.reason == "conservative_fallback":
                state = self.channels[target.channel]
                state.fallback_queue = [
                    item for item in state.fallback_queue
                    if not np.allclose(np.asarray(item, float), target.point)
                ]
            self._record_clear(
                target.point, target.channel, target.reason,
                certified=target.reason == "certified_clear_point",
            )
            reason = "source_cleared"
        else:
            assert target.channel is not None
            self._record_measure(
                target.point, target.channel, target.reason,
                guard=target.kind == RouteNodeKind.GUARD,
            )
            state = self.channels[target.channel]
            safe = state.safe_clear_point() if state.status == ChannelStatus.FOUND else None
            if safe is not None:
                self._record_clear(
                    safe, target.channel, "immediate_clear_after_service_measurement",
                    certified=True,
                )
                reason = "source_became_clearable_and_cleared"
            else:
                reason = "guard_measurement_completed" if target.kind == RouteNodeKind.GUARD else "source_action_completed"

        stop = np.asarray(self.client.position, float)
        self.diagnostics.append({
            "type": "movement_segment",
            "segment_start": segment_origin.tolist(),
            "segment_target": target.point.tolist(),
            "target_type": target.kind.value,
            "straight_distance": float(np.linalg.norm(target.point - segment_origin)),
            "opportunistic_events": [],
            "guard_events": [guard.level.value] if guard.level != GuardLevel.NONE else [],
            "actual_stop_position": stop.tolist(),
            "interrupted_for_replan": False,
        })
        assert self.progress is not None
        self.progress.maximum = max(
            self.progress.maximum,
            self.progress.segment_new_max(segment_origin, stop),
        )
        return reason

    def _plan(self, reason: str) -> tuple[RouteNode | None, GuardDecision | None]:
        assert self.progress is not None
        position = np.asarray(self.client.position, float)
        self.progress.update(position)
        for state in self.channels.values():
            self._refresh_tsp_window(state)
            self._refresh_cross_view_window(state)
        nodes, anchors = build_candidate_nodes(
            current_position=position,
            progress=self.progress,
            coverage=self.coverage,
            completed_vertices=self.coverage_completed,
            channels=self.channels,
            resolver=self.resolver,
            epsilon=self.planner.numeric_angle_tol_deg * math.pi / 180.0,
        )
        route = self.open_route_planner.plan(position, self.client.current_channel, nodes)
        first = route.first_target
        self.replan_count += 1
        self.diagnostics.append({
            "type": "dynamic_replan",
            "robot_position": position.tolist(),
            "historical_max_sweep_progress": self.progress.maximum,
            "next_two_vertices": anchors,
            "remaining_coverage_vertices": anchors,
            "candidate_sources": [node.channel for node in nodes if node.kind == RouteNodeKind.SOURCE],
            "source_service_targets": {
                str(node.channel): node.point.tolist() for node in nodes if node.kind == RouteNodeKind.SOURCE
            },
            "resolution_order": dict(self.source_resolution_order),
            "source_diagnostics": {
                str(channel): {
                    "status": state.status.value,
                    "bearing_count": state.bearing_count,
                    "certificate_center": state.certificate().center.tolist() if state.status == ChannelStatus.FOUND else None,
                    "certificate_radius_m": float(state.certificate().radius_m) if state.status == ChannelStatus.FOUND else None,
                    "certificate_diameter_m": 2.0 * float(state.certificate().radius_m) if state.status == ChannelStatus.FOUND else None,
                    "localization_stage": localization_stage(state, self.planner).value if state.status == ChannelStatus.FOUND else None,
                    "localization_debt": bool(getattr(state, "localization_debt", False)),
                    "localization_debt_direction": getattr(state, "localization_debt_direction", None),
                    "tsp_window_armed": bool(getattr(state, "tsp_window_armed", False)),
                    "cross_view_armed": bool(getattr(state, "cross_view_armed", False)),
                    "cross_view_edge": getattr(state, "cross_view_edge", None),
                    "cross_view_point": list(state.cross_view_point) if getattr(state, "cross_view_point", None) is not None else None,
                    "service_target": next((node.point.tolist() for node in nodes if node.kind == RouteNodeKind.SOURCE and node.channel == channel), None),
                    "service_target_reason": next((node.reason for node in nodes if node.kind == RouteNodeKind.SOURCE and node.channel == channel), None),
                }
                for channel, state in self.channels.items()
            },
            "planned_route": [node.label for node in route.nodes],
            "chosen_first_target": first.label if first else None,
            "predicted_route_distance": route.distance_m,
            "predicted_route_cost": route.cost_s,
            "solver": "exact" if route.exact else "deterministic_all_node_fallback",
            "replan_reason": reason,
        })
        if first is None:
            return None, None
        guard = self.crossing_guard.check(position, first, self.progress, self.channels)
        self.diagnostics.append({
            "type": "angular_crossing_guard",
            "channel": guard.channel,
            "source_guard_angle": guard.guard_angle,
            "historical_max_progress": self.progress.maximum,
            "segment_new_max_progress": guard.segment_new_max,
            "crossing_detected": guard.level != GuardLevel.NONE,
            "zero_detour_found": guard.level == GuardLevel.ZERO_DETOUR,
            "small_detour_distance": guard.detour_m,
            "forced_measurement": guard.level == GuardLevel.FORCED,
            "response_level": guard.level.value,
        })
        return first, guard

    def _statistics(self, reason: str) -> None:
        assert self.progress is not None
        self.diagnostics.append({
            "type": "dynamic_open_route_statistics",
            "termination_reason": reason,
            "sweep_direction": self.sweep_direction,
            "historical_max_sweep_progress": self.progress.maximum,
            "replan_count": self.replan_count,
            "guard_measurement_count": self.guard_measurement_count,
            "opportunistic_measure_count": self.opportunistic_measure_count,
            "opportunistic_clear_count": self.opportunistic_clear_count,
            "coverage_revisit_count": self.coverage_revisit_count,
            "coverage_revisit_direction_count": self.coverage_revisit_direction_count,
            "coverage_revisit_directions_by_channel": dict(self._coverage_revisit_directions_by_channel),
            "preplanned_cross_view_count": self.preplanned_cross_view_count,
        })

    def run(self) -> RunResult:
        wall_start = time.perf_counter()
        self.client.enter()
        self._scan_unknown_coverage(0)
        origin_bearings = [
            float(observation.bearing_deg)
            for state in self.channels.values()
            for observation in state.history
            if observation.coverage_index == 0
            and observation.result == "direction"
            and observation.bearing_deg is not None
        ]
        route = RoutePlanner(self.planner).plan(origin_bearings)
        self.coverage = route.coverage.copy()
        self.sweep_direction = route.sweep_direction
        self.progress = DirectedSweepProgress(
            math.atan2(float(self.coverage[1, 1]), float(self.coverage[1, 0])),
            self.sweep_direction,
        )
        self._initialize_cross_view_tasks()
        self.diagnostics.append({
            "type": "dynamic_sweep_selected",
            "sweep_direction": self.sweep_direction,
            "first_vertex": route.first_vertex.tolist(),
            "rotation_deg": route.rotation_deg,
            "orientation_strategy": self.planner.orientation_strategy,
        })

        # Frozen bootstrap: origin -> V1 -> scan, before the dynamic core.
        bootstrap = RouteNode(RouteNodeKind.COVERAGE, self.coverage[1].copy(), vertex=1)
        no_guard = GuardDecision(
            GuardLevel.NONE, None, bootstrap, None, None,
            self.progress.segment_new_max(np.asarray(self.client.position, float), bootstrap.point),
        )
        replan_reason = "bootstrap_first_vertex_completed"
        while 1 not in self.coverage_completed:
            replan_reason = self._move_and_act(bootstrap, no_guard)
        self.progress.update(np.asarray(self.client.position, float))

        while self.action_count < self.planner.max_actions:
            complete = len(self.coverage_completed) == len(self.coverage)
            done, reason = termination_status(self.channels, complete, self.physical)
            if done or reason == "invalid_below_problem_lower_bound":
                self._statistics(reason)
                self.client.exit()
                return self._result(done, reason, wall_start)
            if self.client.real_time_left_s() <= self.planner.real_time_reserve_s:
                self._statistics("real_deadline_guard")
                self.client.exit()
                return self._result(False, "real_deadline_guard", wall_start)
            target, guard = self._plan(replan_reason)
            if target is None or guard is None:
                self._statistics("no_actionable_route_node")
                self.client.exit()
                return self._result(False, "no_actionable_route_node", wall_start)
            replan_reason = self._move_and_act(target, guard)
            self.progress.update(np.asarray(self.client.position, float))

        self._statistics("max_actions_exceeded")
        self.client.exit()
        return self._result(False, "max_actions_exceeded", wall_start)
