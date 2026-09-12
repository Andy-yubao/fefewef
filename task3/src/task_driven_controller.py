"""Task-queue controller with committed service and a directional sweep."""

from __future__ import annotations

import time
from dataclasses import replace
from typing import Any

import numpy as np

from .channel_state import ChannelStatus, termination_status
from .config import PhysicalConfig, PlannerConfig
from .controller import ActionClient, RunResult, SearchController
from .opportunistic_observer import OpportunisticObserver
from .opportunity_planner import EmbeddedEventKind
from .route_planner import RoutePlanner
from .short_horizon_sequencer import TaskPreview, choose_short_horizon_sequence
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
        self.macro_backward_move_count = 0
        self.local_leg_retrace_count = 0
        self.local_leg_retrace_m = 0.0
        self.fallback_action_count = 0
        self.fallback_movement_m = 0.0
        self.resolve_ready_count = 0
        self.resolve_waiting_not_ready_count = 0
        self._progress_frontier_rank = -1
        self._leg_progress_fraction = 0.0
        self._final_transverse_attempted: set[int] = set()
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

    def _frontier_rank(self) -> int:
        ring_indices = [index for index in self.coverage_completed if index > 0]
        return max((index - 1 for index in ring_indices), default=-1)

    def _sync_leg_progress(self) -> None:
        frontier_rank = self._frontier_rank()
        if self._progress_frontier_rank != frontier_rank:
            self._progress_frontier_rank = frontier_rank
            self._leg_progress_fraction = 0.0

    def _update_leg_progress_from_point(self, point: np.ndarray) -> None:
        """Monotonically record real forward progress on the current sweep leg."""
        progress = self._route_progress(point)
        if progress is None or self.sweep_planner is None:
            return
        if not self.sweep_planner.is_forward_compatible(point, self._frontier_rank()):
            return
        self._leg_progress_fraction = max(self._leg_progress_fraction, progress[1])

    def _task_snapshot(self) -> dict[str, Any]:
        active = self.task_queue.active
        active_source_rank = None
        if active is not None and active.kind == TaskKind.RESOLVE_SOURCE:
            active_source_rank = active.source_sector_rank
        return {
            "phase": self.phase,
            "active_task_type": active.kind.value if active else None,
            "active_channel": active.channel if active else None,
            "active_vertex": active.vertex if active else None,
            "waiting_order": self.task_queue.labels(),
            "sweep_sector": self._next_vertex(),
            "sweep_direction": self.sweep_direction,
            "completed_sectors": sorted(self.completed_sectors),
            "frontier_rank": self._frontier_rank(),
            "active_source_sector_rank": active_source_rank,
            "active_activation_reason": active.activation_reason if active else None,
            "resolve_ready_count": self.resolve_ready_count,
            "resolve_waiting_not_ready_count": self.resolve_waiting_not_ready_count,
        }

    def _next_action_distance(self, channel: int, current: np.ndarray) -> float:
        state = self.channels[channel]
        safe = state.safe_clear_point()
        if safe is not None:
            return float(np.linalg.norm(safe - current))
        if not state.already_measured(current):
            return 0.0
        return float(np.linalg.norm(state.certificate().center - current))

    def _service_order_fraction(self, channel: int) -> float:
        state = self.channels[channel]
        target = state.safe_clear_point()
        if target is None:
            target = state.certificate().center
        progress = self._route_progress(target)
        return progress[1] if progress is not None else 0.0

    def _available_tasks(self) -> list[Task]:
        assert self.sweep_planner is not None
        current = np.asarray(self.client.position, float)
        next_vertex = self._next_vertex()
        frontier_rank = self._frontier_rank()
        tasks: list[Task] = []
        ready_count = 0
        not_ready_count = 0
        for channel, state in self.channels.items():
            if state.status != ChannelStatus.FOUND:
                continue
            window = self.sweep_planner.service_window(state, frontier_rank)
            activation_reason = self._resolve_activation_reason(channel)
            ready = activation_reason is not None
            ready_count += int(ready)
            not_ready_count += int(not ready)
            # Only READY work in the current/deadline sector precedes Advance.
            group = 0 if window.current_sector else 2
            tasks.append(Task(
                TaskKind.RESOLVE_SOURCE,
                channel=channel,
                order_key=(
                    group,
                    0 if window.deadline else 1,
                    max(0, window.relative_rank),
                    self._service_order_fraction(channel) if window.current_sector else 0.0,
                    self._next_action_distance(channel, current),
                    self.sweep_planner.completion_stage(state),
                    channel,
                ),
                ready=ready,
                activation_reason=activation_reason,
                source_sector_rank=window.source_rank,
            ))
        if next_vertex is not None:
            tasks.append(Task(
                TaskKind.ADVANCE_COVERAGE,
                vertex=next_vertex,
                order_key=(1, next_vertex),
                activation_reason="next_coverage_milestone",
            ))
        self.resolve_ready_count = ready_count
        self.resolve_waiting_not_ready_count = not_ready_count
        return tasks

    def _refresh_waiting(self, event: str) -> None:
        tasks = self._available_tasks()
        tasks = self._sequence_waiting(tasks, event)
        self.task_queue.rebuild(tasks)
        self.diagnostics.append({
            "type": "waiting_rebuilt",
            "event": event,
            **self._task_snapshot(),
        })

    def _resolve_preview(self, task: Task) -> TaskPreview | None:
        """Describe the next action without implying that it completes Resolve."""
        assert task.channel is not None
        action = self._normal_resolve_action(task.channel)
        if action is None:
            return None
        kind, point, reason, certified = action
        point = np.asarray(point, float).copy()
        operation_s = (
            self.physical.measure_s
            if kind == "MEASURE"
            else self.physical.optical_s + self.physical.laser_s
        )
        requires_switch = kind == "MEASURE"
        immediate_cost_s = (
            float(np.linalg.norm(point - np.asarray(self.client.position, float)))
            / self.physical.speed_mps
            + (self.physical.switch_s if requires_switch
               and task.channel != self.client.current_channel else 0.0)
            + operation_s
        )
        completion_known = kind == "CLEAR" and certified
        return TaskPreview(
            task=task,
            immediate_action=kind,
            immediate_reason=reason,
            immediate_operation_time_s=operation_s,
            immediate_end_position=point,
            requires_channel_switch=requires_switch,
            completion_known=completion_known,
            estimated_completion_cost_s=immediate_cost_s if completion_known else None,
            estimated_completion_end_position=point.copy() if completion_known else None,
        )

    def _sequence_waiting(self, tasks: list[Task], event: str) -> list[Task]:
        """Reorder only WAITING; TaskQueue preserves any ACTIVE commitment."""
        if self.sweep_planner is None:
            return tasks
        advance = next((task for task in tasks if task.kind == TaskKind.ADVANCE_COVERAGE), None)
        frontier_rank = self._frontier_rank()
        required_tasks = [
            task for task in tasks
            if task.kind == TaskKind.RESOLVE_SOURCE
            and task.ready
            and task.source_sector_rank is not None
            and task.source_sector_rank <= frontier_rank
        ]
        required_tasks.sort(key=lambda task: task.order_key)
        required = {task.identity for task in required_tasks}
        ordinary_ready = [
            task for task in tasks
            if task.kind == TaskKind.RESOLVE_SOURCE
            and task.ready
            and task.identity not in required
            and task.source_sector_rank is not None
            and task.source_sector_rank in {max(0, frontier_rank), frontier_rank + 1}
        ]
        ordinary_ready.sort(key=lambda task: task.order_key)
        # Required READY obligations bypass the ordinary top-3 prefilter.
        candidate_tasks = required_tasks + ordinary_ready[:max(0, 3 - len(required_tasks))]
        previews = [
            preview for task in candidate_tasks
            if (preview := self._resolve_preview(task)) is not None
        ]
        decision = choose_short_horizon_sequence(
            np.asarray(self.client.position, float),
            self.client.current_channel,
            previews,
            advance,
            self.coverage[advance.vertex] if advance is not None else None,
            required,
            self.physical.speed_mps,
            self.physical.switch_s,
            horizon=1,
        )
        if decision.sequences:
            self.diagnostics.append({
                "type": "route_sequence_decision",
                "event": event,
                "planning_horizon": 1,
                "required_before_advance": [task.label for task in required_tasks],
                "candidate_sequences": [
                    {
                        "sequence": sequence.label,
                        "estimated_immediate_cost_s": sequence.estimated_immediate_cost_s,
                        "decision_end_position": sequence.decision_end_position.tolist(),
                        "immediate_action": sequence.immediate_action,
                        "completion_known": sequence.completion_known,
                        "estimated_completion_cost_s": sequence.estimated_completion_cost_s,
                        "estimated_completion_end_position": (
                            sequence.estimated_completion_end_position.tolist()
                            if sequence.estimated_completion_end_position is not None else None
                        ),
                        "feasible": sequence.feasible,
                        "reason": sequence.reason,
                    }
                    for sequence in decision.sequences
                ],
                "chosen_sequence": (
                    decision.chosen_sequence.label if decision.chosen_sequence else None
                ),
                "chosen_next_task": (
                    decision.chosen_task.label if decision.chosen_task else None
                ),
            })
        if decision.chosen_task is None:
            if required and advance is not None:
                return [
                    replace(task, ready=False)
                    if task.identity == advance.identity else task
                    for task in tasks
                ]
            return tasks
        return [
            replace(task, order_key=(-1,))
            if task.identity == decision.chosen_task.identity else task
            for task in tasks
        ]

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

    def _pause_active(self, reason: str) -> None:
        task = self.task_queue.active
        if task is None:
            return
        self.diagnostics.append({
            "type": "task_paused",
            "pause_reason": reason,
            **self._task_snapshot(),
        })
        self.task_queue.complete_active()
        self._active_start = None
        self._refresh_waiting("active_not_ready")

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
        if (
            len(self.coverage_completed) == len(self.coverage)
            and active is not None
            and active.kind == TaskKind.RESOLVE_SOURCE
            and active.source_sector_rank is not None
            and active.source_sector_rank < self._frontier_rank()
        ):
            self.cleanup_movement_m += movement_m
        completed_return = False
        angular_backward = False
        macro_backward = False
        local_leg_retrace = False
        local_leg_retrace_m = 0.0
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
            active_is_resolve = active is not None and active.kind == TaskKind.RESOLVE_SOURCE
            if active_is_resolve and not opportunistic:
                macro_backward = not self.sweep_planner.is_forward_compatible(
                    end, self._frontier_rank()
                )
                start_projection = self._current_leg_projection(start)
                end_projection = self._current_leg_projection(end)
                if start_projection is not None and end_projection is not None:
                    start_fraction, leg_length_m = start_projection
                    end_fraction, _ = end_projection
                    reference_fraction = max(start_fraction, self._leg_progress_fraction)
                    backward_fraction = reference_fraction - end_fraction
                    fraction_tol = self.planner.numeric_distance_tol_m / leg_length_m
                    if backward_fraction > fraction_tol:
                        local_leg_retrace = True
                        local_leg_retrace_m = backward_fraction * leg_length_m
                        self.local_leg_retrace_count += 1
                        self.local_leg_retrace_m += local_leg_retrace_m
                if movement_m > self.planner.numeric_distance_tol_m:
                    self._update_leg_progress_from_point(end)
            angular_backward = macro_backward
            if angular_backward:
                self.angular_backward_movement_count += 1
                self.macro_backward_move_count += 1
        if reason.startswith("conservative_fallback"):
            self.fallback_action_count += 1
            self.fallback_movement_m += movement_m
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
            "macro_backward_movement": macro_backward,
            "local_leg_retrace": local_leg_retrace,
            "local_leg_retrace_m": local_leg_retrace_m,
            "active_task_type": active.kind.value if active else None,
            "active_channel": active.channel if active else None,
            "active_vertex": active.vertex if active else None,
            "phase": self.phase,
            "sweep_sector": self._next_vertex(),
            "sweep_direction": self.sweep_direction,
            "completed_sectors": sorted(self.completed_sectors),
            "frontier_rank": self._frontier_rank(),
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

    def _measurement_useful_at(self, channel: int, point: np.ndarray) -> bool:
        state = self.channels[channel]
        point = np.asarray(point, float)
        if state.already_measured(point):
            return False
        bearings = [obs for obs in state.history if obs.result == "direction"]
        if not bearings:
            return True
        center = state.certificate().center
        candidate = point - center
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

    def _current_measurement_useful(self, channel: int) -> bool:
        return self._measurement_useful_at(channel, np.asarray(self.client.position, float))

    def _route_progress(self, point: np.ndarray) -> tuple[float, float] | None:
        projection = self._current_leg_projection(point)
        if projection is None:
            return None
        self._sync_leg_progress()
        return self._leg_progress_fraction, projection[0]

    def _current_leg_projection(self, point: np.ndarray) -> tuple[float, float] | None:
        next_vertex = self._next_vertex()
        if next_vertex is None:
            return None
        frontier_rank = self._frontier_rank()
        start_index = max(0, frontier_rank + 1)
        start = self.coverage[start_index]
        end = self.coverage[next_vertex]
        delta = end - start
        length2 = float(np.dot(delta, delta))
        if length2 <= self.planner.numeric_distance_tol_m ** 2:
            return None
        point_fraction = float(np.dot(np.asarray(point, float) - start, delta) / length2)
        return min(1.0, max(0.0, point_fraction)), length2 ** 0.5

    def _is_not_behind_current_leg_progress(self, point: np.ndarray) -> bool:
        progress = self._route_progress(point)
        if progress is None:
            return True
        current_fraction, target_fraction = progress
        projection = self._current_leg_projection(point)
        assert projection is not None
        fraction_tol = self.planner.numeric_distance_tol_m / projection[1]
        return target_fraction + fraction_tol >= current_fraction

    def _forward_route_measurement(
        self, channel: int, stop_before: np.ndarray | None = None
    ) -> np.ndarray | None:
        next_vertex = self._next_vertex()
        if next_vertex is None:
            return None
        self._sync_leg_progress()
        frontier_rank = self._frontier_rank()
        start = self.coverage[max(0, frontier_rank + 1)]
        end = self.coverage[next_vertex]
        delta = end - start
        length2 = float(np.dot(delta, delta))
        if length2 <= self.planner.numeric_distance_tol_m ** 2:
            return None
        fraction_tol = self.planner.numeric_distance_tol_m / length2 ** 0.5
        current_fraction = self._leg_progress_fraction
        stop_fraction = 1.0
        if stop_before is not None:
            stop_fraction = min(1.0, max(
                0.0,
                float(np.dot(np.asarray(stop_before, float) - start, delta) / length2),
            ))
        for fraction in np.linspace(0.0, 1.0, 9):
            if fraction + fraction_tol < current_fraction:
                continue
            if fraction > stop_fraction + fraction_tol:
                break
            point = start + float(fraction) * delta
            if not self.sweep_planner.is_forward_compatible(point, self._frontier_rank()):
                continue
            if self._measurement_useful_at(channel, point):
                return point.copy()
        return None

    def _forward_dedicated_measurement(self, channel: int) -> np.ndarray | None:
        assert self.sweep_planner is not None
        state = self.channels[channel]
        point = state.certificate().center.copy()
        if (
            not self.sweep_planner.is_forward_compatible(point, self._frontier_rank())
            or state.already_measured(point)
        ):
            return None
        return point

    def _normal_resolve_action(
        self, channel: int
    ) -> tuple[str, np.ndarray, str, bool] | None:
        assert self.sweep_planner is not None
        state = self.channels[channel]
        frontier_rank = self._frontier_rank()
        safe = state.safe_clear_point()
        if (
            safe is not None
            and self.sweep_planner.is_forward_compatible(safe, frontier_rank)
        ):
            approach = self._forward_route_measurement(channel, stop_before=safe)
            if approach is not None:
                return "MEASURE", approach, "forward_service_approach", False
            return "CLEAR", safe, "certified_clear_point", True
        current = np.asarray(self.client.position, float)
        if self._current_measurement_useful(channel):
            return "MEASURE", current, "current_position_information", False
        dedicated = self._forward_dedicated_measurement(channel)
        point = self._forward_route_measurement(channel, stop_before=dedicated)
        if point is not None:
            return "MEASURE", point, "forward_route_measurement", False
        if dedicated is not None:
            return "MEASURE", dedicated, "forward_center_measurement", False
        if self._next_vertex() is None and channel not in self._final_transverse_attempted:
            transverse = self.sweep_planner.choose_forward_transverse(
                state, current, frontier_rank
            )
            if transverse is not None:
                return "MEASURE", transverse, "final_transverse_measurement", False
        return None

    def _has_forward_fallback(self, channel: int) -> bool:
        state = self.channels[channel]
        state.activate_fallback(np.asarray(self.client.position, float))
        assert self.sweep_planner is not None
        return any(
            self.sweep_planner.is_forward_compatible(np.asarray(point, float), self._frontier_rank())
            for point in state.fallback_queue
        )

    def _resolve_activation_reason(self, channel: int) -> str | None:
        action = self._normal_resolve_action(channel)
        if action is not None:
            return action[2]
        state = self.channels[channel]
        if (
            state.bearing_count >= self.planner.max_bearings_before_fallback
            and self._has_forward_fallback(channel)
        ):
            return "fallback_after_observation_limit"
        return None

    def is_resolve_ready(self, channel: int) -> bool:
        return self._resolve_activation_reason(channel) is not None

    def _fallback_clear_point(self, channel: int) -> np.ndarray | None:
        state = self.channels[channel]
        if state.bearing_count < self.planner.max_bearings_before_fallback:
            return None
        current = np.asarray(self.client.position, float)
        state.activate_fallback(current)
        if not state.fallback_queue:
            return None
        assert self.sweep_planner is not None
        points = [np.asarray(point, float) for point in state.fallback_queue]
        forward = [
            (index, point) for index, point in enumerate(points)
            if self.sweep_planner.is_forward_compatible(point, self._frontier_rank())
        ]
        if not forward:
            return None
        index, point = min(forward, key=lambda item: float(np.linalg.norm(item[1] - current)))
        state.fallback_queue.pop(index)
        return point

    def _execute_resolve_step(self, task: Task) -> None:
        assert task.channel is not None and self.sweep_planner is not None
        channel = task.channel
        state = self.channels[channel]
        if state.status == ChannelStatus.CLEARED:
            self._complete_active("channel_cleared_opportunistically")
            return
        action = self._normal_resolve_action(channel)
        if action is not None:
            kind, point, reason, certified = action
            self._travel_opportunities(point, channel)
            if kind == "CLEAR":
                self._do_clear(point, channel, reason, certified)
            else:
                self._do_measure(point, channel, reason)
                if reason == "final_transverse_measurement":
                    self._final_transverse_attempted.add(channel)
        else:
            point = self._fallback_clear_point(channel)
            if point is None:
                self._pause_active("no_ready_resolve_action")
                return
            self._travel_opportunities(point, channel)
            self._do_clear(point, channel, "conservative_fallback_after_observation_limit", False)
        self._refresh_waiting("belief_updated")
        if self.channels[channel].status == ChannelStatus.CLEARED:
            self._complete_active("channel_cleared")
        elif not self.is_resolve_ready(channel):
            self._pause_active("resolve_became_not_ready")

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
            "macro_backward_move_count": self.macro_backward_move_count,
            "local_leg_retrace_count": self.local_leg_retrace_count,
            "local_leg_retrace_m": self.local_leg_retrace_m,
            "fallback_action_count": self.fallback_action_count,
            "fallback_movement_m": self.fallback_movement_m,
            "resolve_ready_count": self.resolve_ready_count,
            "resolve_waiting_not_ready_count": self.resolve_waiting_not_ready_count,
            "frontier_rank": self._frontier_rank(),
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
