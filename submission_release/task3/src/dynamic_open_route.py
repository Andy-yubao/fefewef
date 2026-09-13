"""Dynamic open-route planning with ordered coverage anchors and angular guards.

This module deliberately has no dependency on the candidate-038 task queue or
its sector/group vocabulary.  Coverage vertices are precedence constraints;
all physical routes start at the robot's actual position.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import math

import numpy as np

from .channel_state import ChannelState, ChannelStatus
from .config import PhysicalConfig, PlannerConfig
from .opportunity_planner import EmbeddedEvent, EmbeddedEventKind, OpportunityPlanner
from .route_planner import RouteLeg


TAU = 2.0 * math.pi


class RouteNodeKind(str, Enum):
    COVERAGE = "CoverageTask"
    SOURCE = "SourceServiceTask"
    GUARD = "GuardMeasurement"


class LocalizationStage(str, Enum):
    BROAD = "BROAD"
    EDGE_LOCALIZING = "EDGE_LOCALIZING"
    ROUGH = "ROUGH"
    CLEARABLE = "CLEARABLE"


def localization_stage(state: ChannelState, planner: PlannerConfig) -> LocalizationStage:
    """Derived routing quality; lifecycle status remains independent."""
    safe = getattr(state, "safe_clear_point", lambda: None)()
    if safe is not None:
        return LocalizationStage.CLEARABLE
    radius = float(state.certificate().radius_m)
    diameter = 2.0 * radius
    if diameter <= planner.rough_localization_diameter_m:
        return LocalizationStage.ROUGH
    directions = [obs for obs in state.history if obs.result == "direction"]
    origin_no_signal = any(
        obs.coverage_index == 0 and obs.result == "no_signal" for obs in state.history
    )
    has_non_origin_direction = any(
        obs.coverage_index != 0
        and float(np.linalg.norm(np.asarray(obs.position, float)))
            > planner.numeric_distance_tol_m
        for obs in directions
    )
    if (
        (
            bool(getattr(state, "localization_debt", False))
            or diameter <= planner.edge_localization_diameter_m
        )
        and origin_no_signal
        and has_non_origin_direction
    ):
        return LocalizationStage.EDGE_LOCALIZING
    return LocalizationStage.BROAD


@dataclass(frozen=True)
class RouteNode:
    kind: RouteNodeKind
    point: np.ndarray
    channel: int | None = None
    vertex: int | None = None
    action: str = "MEASURE"
    reason: str = ""
    operation_cost_s: float = 0.0

    @property
    def label(self) -> str:
        if self.kind == RouteNodeKind.COVERAGE:
            return f"V{self.vertex}"
        prefix = "Guard" if self.kind == RouteNodeKind.GUARD else "S"
        return f"{prefix}{self.channel}"


@dataclass(frozen=True)
class OpenRoute:
    nodes: tuple[RouteNode, ...]
    cost_s: float
    distance_m: float
    exact: bool

    @property
    def first_target(self) -> RouteNode | None:
        return self.nodes[0] if self.nodes else None


def _angle(point: np.ndarray) -> float:
    p = np.asarray(point, float)
    if float(np.linalg.norm(p)) <= 1e-12:
        return 0.0
    return math.atan2(float(p[1]), float(p[0]))


@dataclass
class DirectedSweepProgress:
    """Directed, unwrapped progress whose historical maximum never decreases."""

    reference_angle_rad: float
    direction: str
    maximum: float = 0.0

    @property
    def sign(self) -> float:
        return -1.0 if self.direction == "CW" else 1.0

    def raw(self, point: np.ndarray) -> float:
        return (self.sign * (_angle(point) - self.reference_angle_rad)) % TAU

    def unwrapped(self, point: np.ndarray, near: float | None = None) -> float:
        value = self.raw(point)
        reference = self.maximum if near is None else float(near)
        value += round((reference - value) / TAU) * TAU
        return value

    def update(self, point: np.ndarray) -> float:
        self.maximum = max(self.maximum, self.unwrapped(point))
        return self.maximum

    def segment_new_max(self, start: np.ndarray, end: np.ndarray, samples: int = 129) -> float:
        """Conservatively sample the polar progress reached by a straight segment."""
        a, b = np.asarray(start, float), np.asarray(end, float)
        previous = self.unwrapped(a)
        reached = self.maximum
        for fraction in np.linspace(0.0, 1.0, samples):
            point = a + float(fraction) * (b - a)
            if float(np.linalg.norm(point)) <= 1e-9:
                continue
            value = self.unwrapped(point, previous)
            previous = value
            reached = max(reached, value)
        return reached


@dataclass(frozen=True)
class ServiceTarget:
    point: np.ndarray
    action: str
    reason: str
    operation_cost_s: float


class SourceResolver:
    """Expose exactly one current service target for each source."""

    def __init__(self, physical: PhysicalConfig, planner: PlannerConfig):
        self.physical = physical
        self.planner = planner

    def current_service_target(
        self,
        state: ChannelState,
        current_position: np.ndarray,
        coverage: np.ndarray,
        remaining_vertices: list[int],
    ) -> ServiceTarget | None:
        if state.status != ChannelStatus.FOUND:
            return None
        safe = state.safe_clear_point()
        if safe is not None:
            return ServiceTarget(
                safe, "CLEAR", "certified_clear_point",
                self.physical.optical_s + self.physical.laser_s,
            )
        stage = localization_stage(state, self.planner)
        if (
            bool(getattr(state, "cross_view_armed", False))
            and getattr(state, "cross_view_point", None) is not None
            and stage not in {LocalizationStage.ROUGH, LocalizationStage.CLEARABLE}
        ):
            point = np.asarray(state.cross_view_point, float)
            if not state.already_measured(point):
                return ServiceTarget(
                    point, "MEASURE", "preplanned_cross_view",
                    self.physical.measure_s,
                )
        if state.bearing_count >= self.planner.max_bearings_before_fallback:
            state.activate_fallback(np.asarray(current_position, float))
            if state.fallback_queue:
                points = np.asarray(state.fallback_queue, float)
                index = int(np.argmin(np.linalg.norm(points - current_position, axis=1)))
                return ServiceTarget(
                    points[index].copy(), "CLEAR", "conservative_fallback",
                    self.physical.optical_s,
                )
        # A deliberately small resolver: choose one transverse, guaranteed-
        # reception point from the current certificate.  The route planner
        # never sees the alternative sign, preserving the single-target API.
        circle = state.certificate()
        bearings = [obs for obs in state.history if obs.result == "direction"]
        raw: list[tuple[np.ndarray, str]] = []
        if bearings and stage in {LocalizationStage.BROAD, LocalizationStage.EDGE_LOCALIZING}:
            sensor = np.asarray(bearings[0].position, float)
            ray = circle.center - sensor
            norm = float(np.linalg.norm(ray))
            reception_slack = max(0.0, self.physical.reception_min_m - circle.radius_m)
            offset = min(self.planner.local_offset_m, reception_slack)
            if norm > self.planner.numeric_distance_tol_m and offset > self.planner.numeric_distance_tol_m:
                if stage == LocalizationStage.EDGE_LOCALIZING:
                    # A 45-degree crossing is the dedicated-localization target.
                    # Generate sufficient
                    # crossings at progressively shorter radii instead of aiming
                    # for 90 degrees and clipping them onto the arena boundary.
                    prior = (sensor - circle.center) / norm
                    theta = math.radians(self.planner.edge_target_angle_deg)
                    for scale in (1.0, 0.75, 0.50, 0.25):
                        distance = offset * scale
                        for sign in (-1.0, 1.0):
                            cosine = math.cos(sign * theta)
                            sine = math.sin(sign * theta)
                            rotated = np.array([
                                cosine * prior[0] - sine * prior[1],
                                sine * prior[0] + cosine * prior[1],
                            ])
                            raw.append((circle.center + distance * rotated, "edge_cross_bearing"))
                else:
                    normal = np.array([-ray[1], ray[0]], float) / norm
                    raw.extend([
                        (circle.center + offset * normal, "transverse"),
                        (circle.center - offset * normal, "transverse"),
                    ])
        if stage == LocalizationStage.ROUGH:
            raw.insert(0, (circle.center.copy(), "rough_certificate_center"))
        elif stage == LocalizationStage.EDGE_LOCALIZING:
            # The center is on (or close to) the first bearing ray and is a
            # poor second viewpoint.  Use it only as a degenerate fallback
            # when no guaranteed transverse point can be constructed.
            if not raw:
                raw.append((circle.center.copy(), "edge_center_fallback"))
        else:
            raw.append((circle.center.copy(), "broad_localization_center"))
        candidates: list[tuple[tuple[float, ...], np.ndarray, str]] = []
        next_anchor = (
            np.asarray(coverage[remaining_vertices[0]], float)
            if remaining_vertices else None
        )
        for point, reason in raw:
            length = float(np.linalg.norm(point))
            if length > self.physical.target_radius_m:
                if stage == LocalizationStage.EDGE_LOCALIZING:
                    continue
                point = point * (self.physical.target_radius_m / length)
            if state.already_measured(point):
                continue
            travel = float(np.linalg.norm(point - current_position))
            if stage == LocalizationStage.EDGE_LOCALIZING:
                # Prefer a tangential insertion: first minimize radial motion,
                # then the detour before the next mandatory coverage vertex.
                radial_change = abs(float(np.linalg.norm(point)) - float(np.linalg.norm(current_position)))
                detour = 0.0 if next_anchor is None else (
                    travel + float(np.linalg.norm(next_anchor - point))
                    - float(np.linalg.norm(next_anchor - current_position))
                )
                score = (radial_change, detour, travel)
            else:
                score = (travel,)
            candidates.append((score, point, reason))
        if candidates:
            _score, chosen, reason = min(candidates, key=lambda item: (item[0], item[2]))
            return ServiceTarget(
                chosen.copy(), "MEASURE", f"service_{reason}", self.physical.measure_s,
            )
        return None

    def is_actionable(self, state: ChannelState, *args: object) -> bool:
        return self.current_service_target(state, *args) is not None

    def estimated_service_cost(self, target: ServiceTarget) -> float:
        return target.operation_cost_s

    @staticmethod
    def needs_second_bearing(state: ChannelState) -> bool:
        return state.status == ChannelStatus.FOUND and state.bearing_count == 1


def build_candidate_nodes(
    *,
    current_position: np.ndarray,
    progress: DirectedSweepProgress,
    coverage: np.ndarray,
    completed_vertices: set[int],
    channels: dict[int, ChannelState],
    resolver: SourceResolver,
    epsilon: float = 1e-9,
) -> tuple[list[RouteNode], list[int]]:
    remaining = [index for index in range(1, len(coverage)) if index not in completed_vertices]
    # Every unfinished coverage vertex is always visible to the open TSP.
    # Their fixed order remains a hard precedence constraint.
    anchors = remaining
    unknown_count = sum(state.status == ChannelStatus.UNKNOWN for state in channels.values())
    nodes = [
        RouteNode(
            RouteNodeKind.COVERAGE, coverage[index].copy(), vertex=index,
            operation_cost_s=unknown_count * resolver.physical.measure_s,
        )
        for index in anchors
    ]
    for channel in sorted(channels):
        state = channels[channel]
        target = resolver.current_service_target(state, current_position, coverage, remaining)
        if target is None:
            continue
        # While coverage remains, a source may enter the macro TSP only after
        # its reliable angular support has intersected the local search window.
        # Measurements remain independent of this admission gate.  At the end
        # of coverage every unresolved source is released for final cleanup.
        is_cross_view = target.reason == "preplanned_cross_view"
        if anchors and not (
            bool(getattr(state, "tsp_window_armed", False))
            or (is_cross_view and bool(getattr(state, "cross_view_armed", False)))
        ):
            continue
        nodes.append(RouteNode(
            RouteNodeKind.SOURCE, target.point.copy(), channel=channel,
            action=target.action, reason=target.reason,
            operation_cost_s=target.operation_cost_s,
        ))
    return nodes, anchors


class DynamicOpenRoutePlanner:
    def __init__(self, physical: PhysicalConfig, planner: PlannerConfig):
        self.physical = physical
        self.planner = planner

    def _step_cost(self, start: np.ndarray, node: RouteNode, channel: int) -> float:
        movement = float(np.linalg.norm(node.point - start)) / self.physical.speed_mps
        switch = self.physical.switch_s if node.channel is not None and node.channel != channel else 0.0
        return movement + switch + node.operation_cost_s

    @staticmethod
    def _allowed(index: int, mask: int, nodes: list[RouteNode]) -> bool:
        if nodes[index].kind != RouteNodeKind.COVERAGE:
            return True
        earlier = [
            i for i, node in enumerate(nodes)
            if node.kind == RouteNodeKind.COVERAGE and (node.vertex or 0) < (nodes[index].vertex or 0)
        ]
        return all(mask & (1 << i) for i in earlier)

    def plan(self, start: np.ndarray, current_channel: int, nodes: list[RouteNode]) -> OpenRoute:
        if not nodes:
            return OpenRoute((), 0.0, 0.0, True)
        if len(nodes) <= self.planner.open_route_exact_node_limit:
            return self._exact(start, current_channel, nodes)
        return self._deterministic_fallback(start, current_channel, nodes)

    def _exact(self, start: np.ndarray, current_channel: int, nodes: list[RouteNode]) -> OpenRoute:
        count = len(nodes)
        # (mask,last,current-channel) -> (cost, distance, order).  Channel is
        # carried explicitly because switching is part of the stated cost.
        states: dict[tuple[int, int, int], tuple[float, float, tuple[int, ...]]] = {}
        for index, node in enumerate(nodes):
            if not self._allowed(index, 0, nodes):
                continue
            channel = node.channel if node.channel is not None else current_channel
            distance = float(np.linalg.norm(node.point - start))
            states[(1 << index, index, channel)] = (
                self._step_cost(start, node, current_channel), distance, (index,)
            )
        full = (1 << count) - 1
        for size in range(1, count):
            for (mask, last, channel), (cost, distance, order) in list(states.items()):
                if mask.bit_count() != size:
                    continue
                for index, node in enumerate(nodes):
                    if mask & (1 << index) or not self._allowed(index, mask, nodes):
                        continue
                    new_channel = node.channel if node.channel is not None else channel
                    leg_distance = float(np.linalg.norm(node.point - nodes[last].point))
                    new = (
                        cost + self._step_cost(nodes[last].point, node, channel),
                        distance + leg_distance,
                        order + (index,),
                    )
                    key = (mask | (1 << index), index, new_channel)
                    old = states.get(key)
                    if old is None or (new[0], new[2]) < (old[0], old[2]):
                        states[key] = new
        winner = min(
            (value for (mask, _last, _channel), value in states.items() if mask == full),
            key=lambda item: (item[0], item[2]),
        )
        return OpenRoute(tuple(nodes[index] for index in winner[2]), winner[0], winner[1], True)

    def _deterministic_fallback(
        self, start: np.ndarray, current_channel: int, nodes: list[RouteNode]
    ) -> OpenRoute:
        """Greedy all-node fallback; anchors become available in precedence order."""
        remaining = set(range(len(nodes)))
        order: list[int] = []
        point = np.asarray(start, float)
        channel = current_channel
        cost = distance = 0.0
        while remaining:
            allowed = [index for index in remaining if self._allowed(index, sum(1 << i for i in order), nodes)]
            index = min(
                allowed,
                key=lambda i: (self._step_cost(point, nodes[i], channel), nodes[i].label),
            )
            node = nodes[index]
            leg = float(np.linalg.norm(node.point - point))
            cost += self._step_cost(point, node, channel)
            distance += leg
            point = node.point
            if node.channel is not None:
                channel = node.channel
            order.append(index)
            remaining.remove(index)
        return OpenRoute(tuple(nodes[index] for index in order), cost, distance, False)


class GuardLevel(str, Enum):
    NONE = "none"
    ZERO_DETOUR = "zero_detour"
    SMALL_DETOUR = "small_detour"
    FORCED = "forced"


@dataclass(frozen=True)
class GuardDecision:
    level: GuardLevel
    channel: int | None
    target: RouteNode
    event: EmbeddedEvent | None
    guard_angle: float | None
    segment_new_max: float
    detour_m: float | None = None


class AngularCrossingGuard:
    def __init__(self, physical: PhysicalConfig, planner: PlannerConfig):
        self.physical = physical
        self.planner = planner
        self.opportunities = OpportunityPlanner(physical, planner)
        self._historical_deadlines: dict[int, float] = {}
        self._last_guard_bearing: dict[int, int] = {}

    @staticmethod
    def needs_second_bearing(state: ChannelState) -> bool:
        return (
            state.status == ChannelStatus.FOUND
            and state.bearing_count == 1
            and bool(getattr(state, "tsp_window_armed", False))
        )

    def needs_localization_guard(self, state: ChannelState) -> bool:
        return (
            state.status == ChannelStatus.FOUND
            and bool(getattr(state, "tsp_window_armed", False))
            and localization_stage(state, self.planner) == LocalizationStage.BROAD
            and state.bearing_count >= 2
        )

    def _angular_support(self, state: ChannelState, progress: DirectedSweepProgress) -> tuple[float, float] | None:
        circle = state.certificate()
        distance = float(np.linalg.norm(circle.center))
        if distance <= circle.radius_m + self.planner.numeric_distance_tol_m:
            return None
        half = math.asin(min(1.0, circle.radius_m / distance))
        center = progress.raw(circle.center)
        return center - half, center + half

    def _forward_frontier(self, state: ChannelState, progress: DirectedSweepProgress) -> float:
        """Most advanced possible source angle in directed sweep coordinates."""
        support = self._angular_support(state, progress)
        raw = support[1] if support is not None else progress.raw(state.certificate().center)
        # Map to the nearest revolution.  A frontier just behind the historical
        # maximum is intentionally retained as overdue, not postponed by 2*pi.
        return raw + round((progress.maximum - raw) / TAU) * TAU

    def note_observation(self, state: ChannelState, progress: DirectedSweepProgress) -> None:
        """Refresh the guard deadline whenever a bearing changes the belief."""
        if self.needs_second_bearing(state) or self.needs_localization_guard(state):
            self._historical_deadlines[state.channel] = self._forward_frontier(state, progress)
        else:
            self._historical_deadlines.pop(state.channel, None)

    def is_overdue(self, state: ChannelState, progress: DirectedSweepProgress) -> bool:
        if not (self.needs_second_bearing(state) or self.needs_localization_guard(state)):
            return False
        deadline = self._historical_deadlines.get(
            state.channel, self._forward_frontier(state, progress)
        )
        return (
            deadline <= progress.maximum + 1e-9
            and self._last_guard_bearing.get(state.channel) != state.bearing_count
        )

    def mark_no_bearing_guard_complete(self, state: ChannelState) -> None:
        self._last_guard_bearing[state.channel] = state.bearing_count

    def guard_progress(self, state: ChannelState, progress: DirectedSweepProgress) -> float:
        return self._historical_deadlines.get(
            state.channel, self._forward_frontier(state, progress)
        )

    def _valid_points(self, state: ChannelState, guard_angle: float, progress: DirectedSweepProgress) -> list[np.ndarray]:
        circle = state.certificate()
        radius = max(0.0, self.physical.reception_min_m - circle.radius_m)
        raw = [circle.center.copy()]
        if radius > self.planner.numeric_distance_tol_m:
            raw.extend(
                circle.center + radius * np.array([math.cos(a), math.sin(a)])
                for a in np.linspace(0.0, TAU, self.planner.guard_candidate_count, endpoint=False)
            )
        result = []
        minimum_quality = max(
            self.planner.shared_min_sin_angle,
            math.sin(math.radians(self.planner.edge_target_angle_deg)),
        )
        for point in raw:
            norm = float(np.linalg.norm(point))
            if norm > self.physical.target_radius_m:
                # Projecting an infeasible candidate onto the boundary creates
                # artificial 1800 m waypoints and changes its crossing angle.
                continue
            if state.already_measured(point):
                continue
            if progress.unwrapped(point, guard_angle) > guard_angle + 1e-8:
                continue
            quality = self.opportunities._measurement_quality(state, point)
            baseline, _gain = self.opportunities.measurement_geometry(state, point)
            if (
                quality + 1e-12 >= minimum_quality
                and baseline >= self.planner.minimum_view_baseline_m
            ):
                result.append(point.copy())
        return result

    def check(
        self,
        start: np.ndarray,
        target: RouteNode,
        historical: DirectedSweepProgress,
        channels: dict[int, ChannelState],
    ) -> GuardDecision:
        segment_max = historical.segment_new_max(start, target.point)
        risks: list[tuple[float, ChannelState]] = []
        for state in channels.values():
            if not (self.needs_second_bearing(state) or self.needs_localization_guard(state)):
                continue
            guard_angle = self.guard_progress(state, historical)
            overdue = guard_angle <= historical.maximum + 1e-9
            if overdue and self._last_guard_bearing.get(state.channel) == state.bearing_count:
                continue
            if overdue:
                guard_angle = historical.maximum
            if overdue or (historical.maximum + 1e-9 < guard_angle <= segment_max + 1e-9):
                risks.append((guard_angle, state))
        if not risks:
            return GuardDecision(GuardLevel.NONE, None, target, None, None, segment_max)
        guard_angle, state = min(risks, key=lambda item: (item[0], item[1].channel))
        leg = RouteLeg(np.asarray(start, float), target.point, "guard_check", -1)
        zero = next(
            (event for event in self.opportunities.events(
                leg, {state.channel: state}, allow_possible=True
            )
             if event.kind == EmbeddedEventKind.MEASURE),
            None,
        )
        if zero is not None:
            self._historical_deadlines[state.channel] = max(
                self._historical_deadlines.get(state.channel, guard_angle), guard_angle
            )
            return GuardDecision(
                GuardLevel.ZERO_DETOUR, state.channel, target, zero,
                guard_angle, segment_max, 0.0,
            )
        points = self._valid_points(state, guard_angle, historical)
        if not points:
            # The certificate center is the most conservative last-resort
            # target even when the finite candidate geometry is degenerate.
            points = [state.certificate().center.copy()]
        scored = [
            (
                float(np.linalg.norm(point - start))
                + float(np.linalg.norm(target.point - point))
                - float(np.linalg.norm(target.point - start)),
                float(np.linalg.norm(point - start)), point,
            )
            for point in points
        ]
        detour, _travel, point = min(scored, key=lambda item: (item[0], item[1]))
        level = GuardLevel.SMALL_DETOUR if detour <= self.planner.max_small_detour_m + 1e-9 else GuardLevel.FORCED
        self._historical_deadlines[state.channel] = max(
            self._historical_deadlines.get(state.channel, guard_angle), guard_angle
        )
        guard_node = RouteNode(
            RouteNodeKind.GUARD, point.copy(), channel=state.channel,
            action="MEASURE", reason=f"angular_crossing_{level.value}",
            operation_cost_s=self.physical.measure_s,
        )
        return GuardDecision(level, state.channel, guard_node, None, guard_angle, segment_max, detour)
