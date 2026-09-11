"""Task-queue controller with committed service and a directional sweep."""

from __future__ import annotations

import time
from typing import Any

import numpy as np

from .channel_state import ChannelStatus, termination_status
from .config import PhysicalConfig, PlannerConfig
from .controller import ActionClient, RunResult, SearchController
from .opportunistic_observer import OpportunisticObserver
from .opportunity_planner import EmbeddedEventKind, OpportunityPlanner
from .route_planner import RouteLeg, RoutePlanner
from .task_queue import Task, TaskKind, TaskQueue
from .task_sweep_planner import TaskSweepPlanner


class TaskDrivenController(SearchController):
    """Resolve one ACTIVE task to completion while WAITING follows new belief."""

    def __init__(
        self,
        client: ActionClient,
        physical: PhysicalConfig = PhysicalConfig(),
        planner: PlannerConfig = PlannerConfig(),
        known_total: int | None = None,
    ) -> None:
        super().__init__(
            client,
            mode="hybrid",
            local_family="center_approach",
            physical=physical,
            planner=planner,
            known_total=known_total,
        )
        self.task_queue = TaskQueue()
        self.sweep_planner: TaskSweepPlanner | None = None
        self.opportunistic_observer = OpportunisticObserver(physical, planner)
        self.opportunity_planner = OpportunityPlanner(physical, planner)
        self.sweep_direction = "CCW"
        self.phase = "bootstrap"
        self.completed_sectors: set[int] = set()
        self.task_switch_count = 0
        self.resolve_task_count = 0
        self.advance_task_count = 0
        self.opportunistic_measure_count = 0
        self.opportunistic_clear_count = 0
        self.sweep_clear_count = 0
        self.cleanup_movement_m = 0.0
        self.angular_backward_movement_count = 0
        self.completed_sector_return_count = 0
        self._active_start: np.ndarray | None = None

    def _next_vertex(self) -> int | None:
        return next(
            (index for index in range(1, len(self.coverage)) if index not in self.coverage_completed),
            None,
        )

    def _known_source_count(self) -> int:
        return sum(
            state.status in (ChannelStatus.FOUND, ChannelStatus.CLEARED)
            for state in self.channels.values()
        )

    def _task_snapshot(self) -> dict[str, Any]:
        active = self.task_queue.active
        return {
            "phase": self.phase,
            "active_task_type": active.kind.value if active else None,
            "active_channel": active.channel if active else None,
            "active_vertex": active.vertex if active else None,
            "waiting_order": self.task_queue.labels(),
            "sweep_sector": self._next_vertex(),
            "sweep_direction": self.sweep_direction,
            "completed_sectors": sorted(self.completed_sectors),
        }

    def _next_action_distance(self, channel: int, current: np.ndarray) -> float:
        state = self.channels[channel]
        safe = state.safe_clear_point()
        if safe is not None:
            return float(np.linalg.norm(safe - current))
        if not state.already_measured(current):
            return 0.0
        return float(np.linalg.norm(state.certificate().center - current))

    def _available_tasks(self) -> list[Task]:
        assert self.sweep_planner is not None
        current = np.asarray(self.client.position, float)
        next_vertex = self._next_vertex()
        tasks: list[Task] = []
        for channel, state in self.channels.items():
            if state.status != ChannelStatus.FOUND:
                continue
            window = self.sweep_planner.service_window(state, next_vertex)
            # Deadline/current-sector work precedes Advance; future-sector work follows it.
            group = 0 if window.deadline or window.current_sector else 2
            tasks.append(Task(
                TaskKind.RESOLVE_SOURCE,
                channel=channel,
                order_key=(
                    group,
                    0 if window.deadline else 1,
                    max(0, window.relative_sector),
                    self.sweep_planner.completion_stage(state),
                    self._next_action_distance(channel, current),
                    channel,
                ),
            ))
        if next_vertex is not None:
            tasks.append(Task(
                TaskKind.ADVANCE_COVERAGE,
                vertex=next_vertex,
                order_key=(1, next_vertex),
            ))
        return tasks

    def _refresh_waiting(self, event: str) -> None:
        self.task_queue.rebuild(self._available_tasks())
        self.diagnostics.append({
            "type": "waiting_rebuilt",
            "event": event,
            **self._task_snapshot(),
        })

    def _select_active(self) -> Task | None:
        task = self.task_queue.select_active()
        if task is None:
            return None
        self.task_switch_count += 1
        self._active_start = np.asarray(self.client.position, float).copy()
        if task.kind == TaskKind.RESOLVE_SOURCE:
            self.resolve_task_count += 1
        else:
            self.advance_task_count += 1
        self.diagnostics.append({
            "type": "task_started",
            "task_start_position": self._active_start.tolist(),
            **self._task_snapshot(),
        })
        return task

    def _complete_active(self, reason: str) -> None:
        task = self.task_queue.active
        if task is None:
            return
        self.diagnostics.append({
            "type": "task_completed",
            "active_task_type": task.kind.value,
            "active_channel": task.channel,
            "active_vertex": task.vertex,
            "task_start_position": (
                self._active_start.tolist() if self._active_start is not None else None
            ),
            "task_end_position": list(map(float, self.client.position)),
            "task_completion_reason": reason,
            **{key: value for key, value in self._task_snapshot().items()
               if key not in {"active_task_type", "active_channel", "active_vertex"}},
        })
        self.task_queue.complete_active()
        self._active_start = None
        self._refresh_waiting("active_completed")

    def _record_action(
        self,
        action_kind: str,
        channel: int,
        start: np.ndarray,
        end: np.ndarray,
        reason: str,
        opportunistic: bool = False,
    ) -> None:
        active = self.task_queue.active
        movement_m = float(np.linalg.norm(end - start))
        if len(self.coverage_completed) == len(self.coverage):
            self.cleanup_movement_m += movement_m
        completed_return = False
        angular_backward = False
        if self.sweep_planner is not None and movement_m > self.planner.numeric_distance_tol_m:
            completed_return = (
                self.sweep_planner.sector_for_point(end) in self.completed_sectors
                and float(np.linalg.norm(end)) > self.planner.numeric_distance_tol_m
                and reason not in {
                    "forward_route_measurement",
                    "guaranteed_reception_useful_geometry",
                    "coverage_unknown_discovery",
                }
            )
            if completed_return:
                self.completed_sector_return_count += 1
            # Sector-local radial/transverse service may change polar angle in
            # either sign.  Only entry into a completed sector is a macro
            # sweep reversal.
            angular_backward = completed_return
            if angular_backward:
                self.angular_backward_movement_count += 1
        self.diagnostics.append({
            "type": "task_action",
            "action_kind": action_kind,
            "channel": channel,
            "start": start.tolist(),
            "end": end.tolist(),
            "movement_m": movement_m,
            "reason": reason,
            "opportunistic": opportunistic,
            "completed_sector_return": completed_return,
            "angular_backward_movement": angular_backward,
            "active_task_type": active.kind.value if active else None,
            "active_channel": active.channel if active else None,
            "active_vertex": active.vertex if active else None,
            "phase": self.phase,
            "sweep_sector": self._next_vertex(),
            "sweep_direction": self.sweep_direction,
            "completed_sectors": sorted(self.completed_sectors),
        })

    def _do_measure(self, point: np.ndarray, channel: int, reason: str, opportunistic: bool = False,
                    coverage_index: int | None = None) -> None:
        start = np.asarray(self.client.position, float).copy()
        before = self.channels[channel].status
        self._measure(point, channel, coverage_index)
        self._record_action("MEASURE", channel, start, np.asarray(point, float), reason, opportunistic)
        if opportunistic:
            self.opportunistic_measure_count += 1
        if before == ChannelStatus.FOUND and self.channels[channel].status == ChannelStatus.CLEARED:
            self._record_action("CLEAR", channel, np.asarray(point, float), np.asarray(point, float),
                                "near_immediate", opportunistic)
            if opportunistic:
                self.opportunistic_clear_count += 1
            elif self.phase != "bootstrap":
                self.sweep_clear_count += 1

    def _do_clear(self, point: np.ndarray, channel: int, reason: str,
                  certified: bool, opportunistic: bool = False) -> None:
        start = np.asarray(self.client.position, float).copy()
        before = self.channels[channel].status
        self._clear(point, channel, certified, reason)
        self._record_action("CLEAR", channel, start, np.asarray(point, float), reason, opportunistic)
        if before == ChannelStatus.FOUND and self.channels[channel].status == ChannelStatus.CLEARED:
            if opportunistic:
                self.opportunistic_clear_count += 1
            elif self.phase != "bootstrap":
                self.sweep_clear_count += 1

    def _travel_opportunities(self, target: np.ndarray, active_channel: int | None) -> None:
        attempted: set[tuple] = set()
        while not np.allclose(
            np.asarray(self.client.position, float), target,
            atol=self.planner.numeric_distance_tol_m,
        ):
            events = self.opportunistic_observer.events(
                np.asarray(self.client.position, float), target,
                self.channels, active_channel, attempted,
            )
            if not events:
                return
            event = events[0]
            attempted.add((event.kind, event.channel))
            if event.kind == EmbeddedEventKind.CLEAR:
                self._do_clear(event.position, event.channel, event.reason, True, True)
            else:
                self._do_measure(event.position, event.channel, event.reason, True)
            # Belief may reorder WAITING, but TaskQueue.rebuild preserves ACTIVE.
            self._refresh_waiting("opportunistic_observation")

    def _scan_unknown_coverage(self, index: int) -> None:
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
            self._do_measure(point, channel, "coverage_unknown_discovery", False, index)
            measured += 1
        self.coverage_completed.add(index)
        # The sector just reached remains serviceable.  It becomes completed
        # (and therefore forbidden to dedicated service) only after the next
        # milestone is reached.
        if index > 1:
            self.completed_sectors.add(index - 1)
        for state in self.channels.values():
            state.mark_absent_if_covered(len(self.coverage))
        self.diagnostics.append({
            "type": "coverage_unknown_scan",
            "phase": self.phase,
            "coverage_index": index,
            "position": point.tolist(),
            "unknown_measurements": measured,
            "found_channels_measured": 0,
            **self._task_snapshot(),
        })

    def _execute_advance(self, task: Task) -> None:
        assert task.vertex is not None
        target = self.coverage[task.vertex]
        self._travel_opportunities(target, None)
        self._scan_unknown_coverage(task.vertex)
        self._complete_active("coverage_milestone_scanned")

    def _current_measurement_useful(self, channel: int) -> bool:
        state = self.channels[channel]
        current = np.asarray(self.client.position, float)
        if state.already_measured(current):
            return False
        bearings = [obs for obs in state.history if obs.result == "direction"]
        if not bearings:
            return True
        center = state.certificate().center
        candidate = current - center
        candidate_norm = float(np.linalg.norm(candidate))
        if candidate_norm <= self.planner.numeric_distance_tol_m:
            return False
        best_sine = 0.0
        for observation in bearings:
            prior = np.asarray(observation.position, float) - center
            denominator = float(np.linalg.norm(prior)) * candidate_norm
            if denominator <= self.planner.numeric_distance_tol_m:
                continue
            cross = float(prior[0] * candidate[1] - prior[1] * candidate[0])
            best_sine = max(best_sine, abs(cross) / denominator)
        return best_sine >= self.planner.shared_min_sin_angle

    def _forward_route_measurement(self, channel: int) -> np.ndarray | None:
        next_vertex = self._next_vertex()
        if next_vertex is None:
            return None
        start = np.asarray(self.client.position, float)
        end = self.coverage[next_vertex]
        leg = RouteLeg(start, end, "forward_anchor", next_vertex)
        events = self.opportunity_planner.events(leg, {channel: self.channels[channel]})
        state = self.channels[channel]
        minimum_separation = max(self.planner.grid_step_m, self.physical.clear_radius_m)
        for event in events:
            if event.kind != EmbeddedEventKind.MEASURE:
                continue
            if any(
                float(np.linalg.norm(event.position - np.asarray(obs.position, float)))
                < minimum_separation
                for obs in state.history
            ):
                continue
            return event.position
        return None

    def _fallback_clear_point(self, channel: int) -> np.ndarray | None:
        state = self.channels[channel]
        current = np.asarray(self.client.position, float)
        state.activate_fallback(current)
        if not state.fallback_queue:
            return None
        assert self.sweep_planner is not None
        points = [np.asarray(point, float) for point in state.fallback_queue]
        forward = [
            (index, point) for index, point in enumerate(points)
            if self.sweep_planner.is_forward_compatible(point, self.completed_sectors)
        ]
        pool = forward if forward else list(enumerate(points))
        index, point = min(pool, key=lambda item: float(np.linalg.norm(item[1] - current)))
        state.fallback_queue.pop(index)
        return point

    def _execute_resolve_step(self, task: Task) -> None:
        assert task.channel is not None and self.sweep_planner is not None
        channel = task.channel
        state = self.channels[channel]
        if state.status == ChannelStatus.CLEARED:
            self._complete_active("channel_cleared_opportunistically")
            return
        safe = state.safe_clear_point()
        if safe is not None and self.sweep_planner.is_forward_compatible(safe, self.completed_sectors):
            self._travel_opportunities(safe, channel)
            self._do_clear(safe, channel, "certified_clear_point", True)
        elif (
            len(state.history) < self.planner.max_bearings_before_fallback
            and self._current_measurement_useful(channel)
        ):
            self._do_measure(np.asarray(self.client.position, float), channel,
                             "current_position_information")
        elif len(state.history) < self.planner.max_bearings_before_fallback:
            point = self._forward_route_measurement(channel)
            reason = "forward_route_measurement"
            if point is None:
                point = self.sweep_planner.choose_forward_transverse(
                    state,
                    np.asarray(self.client.position, float),
                    self._next_vertex(),
                    self.completed_sectors,
                )
                reason = "forward_transverse_measurement"
            if point is not None:
                self._travel_opportunities(point, channel)
                self._do_measure(point, channel, reason)
            else:
                point = self._fallback_clear_point(channel)
                if point is None:
                    raise RuntimeError(f"no conservative fallback remains for channel {channel}")
                self._travel_opportunities(point, channel)
                self._do_clear(point, channel, "conservative_fallback", False)
        else:
            point = self._fallback_clear_point(channel)
            if point is None:
                raise RuntimeError(f"no conservative fallback remains for channel {channel}")
            self._travel_opportunities(point, channel)
            self._do_clear(point, channel, "conservative_fallback_after_observation_limit", False)
        self._refresh_waiting("belief_updated")
        if self.channels[channel].status == ChannelStatus.CLEARED:
            self._complete_active("channel_cleared")

    def _append_statistics(self, reason: str) -> None:
        movement_m = self.breakdown.movement_s * self.physical.speed_mps
        self.diagnostics.append({
            "type": "task_queue_statistics",
            "termination_reason": reason,
            "phase": self.phase,
            "sweep_direction": self.sweep_direction,
            "sweep_clear_count": self.sweep_clear_count,
            "cleanup_movement_m": self.cleanup_movement_m,
            "cleanup_movement_share": self.cleanup_movement_m / movement_m if movement_m else 0.0,
            "active_task_switch_count": self.task_switch_count,
            "angular_backward_movement_count": self.angular_backward_movement_count,
            "completed_sector_return_count": self.completed_sector_return_count,
            "opportunistic_measure_count": self.opportunistic_measure_count,
            "opportunistic_clear_count": self.opportunistic_clear_count,
            "advance_coverage_count": self.advance_task_count,
            "resolve_source_count": self.resolve_task_count,
            "completed_sectors": sorted(self.completed_sectors),
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
        self.sweep_planner = TaskSweepPlanner(
            self.coverage, self.sweep_direction, self.physical, self.planner
        )
        self.diagnostics.append({
            "type": "sweep_selected",
            "phase": "bootstrap",
            "sweep_direction": self.sweep_direction,
            "first_vertex": route.first_vertex.tolist(),
            "rotation_deg": route.rotation_deg,
        })
        self.phase = "initial_outward_service"
        self._refresh_waiting("bootstrap_complete")

        while self.action_count < self.planner.max_actions:
            coverage_complete = len(self.coverage_completed) == len(self.coverage)
            done, reason = termination_status(self.channels, coverage_complete, self.physical)
            if done or reason == "invalid_below_problem_lower_bound":
                self._append_statistics(reason)
                self.client.exit()
                return self._result(done, reason, wall_start)
            if self.client.real_time_left_s() <= self.planner.real_time_reserve_s:
                self._append_statistics("real_deadline_guard")
                self.client.exit()
                return self._result(False, "real_deadline_guard", wall_start)
            if self.task_queue.active is None:
                self._refresh_waiting("select_active")
                if self._select_active() is None:
                    self._append_statistics("no_available_task")
                    self.client.exit()
                    return self._result(False, "no_available_task", wall_start)
            active = self.task_queue.active
            assert active is not None
            if active.kind == TaskKind.ADVANCE_COVERAGE:
                self._execute_advance(active)
                if 1 in self.coverage_completed:
                    self.phase = "directional_sweep"
            else:
                self._execute_resolve_step(active)

        self._append_statistics("max_actions_exceeded")
        self.client.exit()
        return self._result(False, "max_actions_exceeded", wall_start)
