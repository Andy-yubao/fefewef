"""End-to-end search, localization, clear, and certified termination loop."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
import time
from typing import Any, Protocol

import numpy as np

from .channel_state import (ChannelState, ChannelStatus, Observation,
                            initialize_channels, termination_status)
from .config import PhysicalConfig, PlannerConfig
from .coverage import analytic_certificate, choose_orientation, ordered_points
from .geometry import CellGrid
from .scheduler import ActionKind, Scheduler


class ActionClient(Protocol):
    position: tuple[float, float]
    current_channel: int
    last_virtual_time_s: float
    def enter(self) -> dict[str, Any]: ...
    def measure(self, position: tuple[float, float] | list[float], channel: int) -> dict[str, Any]: ...
    def clear(self, position: tuple[float, float] | list[float], channel: int) -> dict[str, Any]: ...
    def exit(self) -> dict[str, Any]: ...
    def real_time_left_s(self) -> float: ...


@dataclass
class TimeBreakdown:
    movement_s: float = 0.0
    switching_s: float = 0.0
    measurement_s: float = 0.0
    optical_s: float = 0.0
    laser_s: float = 0.0


@dataclass
class RunResult:
    success: bool
    termination_reason: str
    cleared_count: int
    known_total: int | None
    clear_ratio: float | None
    virtual_time_s: float
    average_localize_clear_s: float | None
    wall_runtime_s: float
    coverage_completed: list[int]
    action_count: int
    diagnostics: list[dict[str, Any]]
    time_breakdown: TimeBreakdown
    channel_status: dict[int, str]
    first_discovery_time_s: float | None
    mean_found_to_clear_s: float | None
    per_channel_timing: dict[int, dict[str, float | None]]

    def to_dict(self) -> dict[str, Any]:
        value = asdict(self)
        value["time_breakdown"] = asdict(self.time_breakdown)
        return value


class SearchController:
    def __init__(self, client: ActionClient, mode: str = "hybrid",
                 local_family: str = "shortlist",
                 physical: PhysicalConfig = PhysicalConfig(),
                 planner: PlannerConfig = PlannerConfig(),
                 known_total: int | None = None):
        self.client = client
        self.physical = physical
        self.planner = planner
        self.known_total = known_total
        cert = analytic_certificate(physical, planner)
        if not cert.valid:
            raise ValueError("configured seven-point layout lacks a coverage certificate")
        self.grid = CellGrid.target_disk(physical.target_radius_m, planner.grid_step_m)
        self.channels = initialize_channels(self.grid, physical, planner)
        self.scheduler = Scheduler(mode, local_family, physical, planner)
        self.coverage = cert.centers.copy()
        self.coverage_completed: set[int] = set()
        self.consecutive_local = 0
        self.action_count = 0
        self.breakdown = TimeBreakdown()
        self.diagnostics: list[dict[str, Any]] = []

    def _account_move(self, point: np.ndarray) -> None:
        old = np.asarray(self.client.position, float)
        self.breakdown.movement_s += float(np.linalg.norm(point - old)) / self.physical.speed_mps

    def _measure(self, point: np.ndarray, channel: int, coverage_index: int | None = None) -> None:
        state = self.channels[channel]
        if state.already_measured(point):
            return
        self._account_move(point)
        if channel != self.client.current_channel:
            self.breakdown.switching_s += self.physical.switch_s
        response = self.client.measure(tuple(map(float, point)), channel)
        self.action_count += 1
        self.breakdown.measurement_s += self.physical.measure_s
        result = response.get("measure_result")
        bearing = response.get("svd_deg") if result == "direction" else None
        was_unknown = state.status == ChannelStatus.UNKNOWN
        near = state.apply_observation(Observation(tuple(map(float, point)), result, bearing, coverage_index))
        if was_unknown and state.status == ChannelStatus.FOUND:
            state.first_found_virtual_time_s = float(self.client.last_virtual_time_s)
        if state.diagnostic_count:
            self.diagnostics.append({"type": "empty_update_preserved", "channel": channel,
                                     "position": point.tolist(), "result": result,
                                     "count": state.diagnostic_count})
        if near:
            self._clear(point, channel, certified=True, source="near_immediate")

    def _clear(self, point: np.ndarray, channel: int, certified: bool, source: str) -> None:
        state = self.channels[channel]
        self._account_move(point)
        response = self.client.clear(tuple(map(float, point)), channel)
        self.action_count += 1
        self.breakdown.optical_s += self.physical.optical_s
        if response.get("clear_result") == "success":
            self.breakdown.laser_s += self.physical.laser_s
            state.mark_cleared(float(self.client.last_virtual_time_s))
        else:
            state.handle_failed_clear(point, certified)
            self.diagnostics.append({"type": "unexpected_clear_failure" if certified else "fallback_miss",
                                     "channel": channel, "position": point.tolist(), "source": source,
                                     "expanded_bearing_tolerance_deg": state.bearing_tolerance_extra_deg})

    def _scan_coverage(self, index: int) -> None:
        point = self.coverage[index]
        unknown = [c for c, s in self.channels.items() if s.status == ChannelStatus.UNKNOWN]
        if self.client.current_channel in unknown:
            unknown.remove(self.client.current_channel)
            unknown.insert(0, self.client.current_channel)
        for channel in unknown:
            self._measure(point, channel, index)
        # Found channels may reuse a mandatory stop for a free movement leg.
        if self.scheduler.mode != "two_stage":
            found = [s for s in self.channels.values()
                     if s.status == ChannelStatus.FOUND and not s.already_measured(point)]
            # The most likely next local target is the closest hard-set center.
            # Measure it last so its channel remains selected after the batch.
            found.sort(
                key=lambda state: float(np.linalg.norm(state.certificate().center - point)),
                reverse=True,
            )
            for state in found:
                self._measure(point, state.channel, None)
        self.coverage_completed.add(index)
        for state in self.channels.values():
            state.mark_absent_if_covered(len(self.coverage))
        self.consecutive_local = 0

    def _result(self, success: bool, reason: str, wall_start: float) -> RunResult:
        cleared = sum(s.status == ChannelStatus.CLEARED for s in self.channels.values())
        ratio = cleared / self.known_total if self.known_total else None
        average = self.client.last_virtual_time_s / cleared if cleared else None
        found_times = [s.first_found_virtual_time_s for s in self.channels.values()
                       if s.first_found_virtual_time_s is not None]
        delays = [s.cleared_virtual_time_s - s.first_found_virtual_time_s
                  for s in self.channels.values()
                  if s.first_found_virtual_time_s is not None and s.cleared_virtual_time_s is not None]
        return RunResult(
            success=success,
            termination_reason=reason,
            cleared_count=cleared,
            known_total=self.known_total,
            clear_ratio=ratio,
            virtual_time_s=float(self.client.last_virtual_time_s),
            average_localize_clear_s=average,
            wall_runtime_s=time.perf_counter() - wall_start,
            coverage_completed=sorted(self.coverage_completed),
            action_count=self.action_count,
            diagnostics=self.diagnostics,
            time_breakdown=self.breakdown,
            channel_status={c: s.status.value for c, s in self.channels.items()},
            first_discovery_time_s=min(found_times) if found_times else None,
            mean_found_to_clear_s=float(np.mean(delays)) if delays else None,
            per_channel_timing={
                c: {
                    "first_found_virtual_time_s": s.first_found_virtual_time_s,
                    "cleared_virtual_time_s": s.cleared_virtual_time_s,
                    "found_to_clear_s": (
                        s.cleared_virtual_time_s - s.first_found_virtual_time_s
                        if s.first_found_virtual_time_s is not None and s.cleared_virtual_time_s is not None
                        else None
                    ),
                }
                for c, s in self.channels.items()
                if s.first_found_virtual_time_s is not None
            },
        )

    def run(self) -> RunResult:
        wall_start = time.perf_counter()
        self.client.enter()
        self._scan_coverage(0)
        bearings = [float(o.bearing_deg) for s in self.channels.values() for o in s.history
                    if o.coverage_index == 0 and o.result == "direction" and o.bearing_deg is not None]
        rotation, reverse = choose_orientation(bearings, self.planner.rotation_deg)
        self.coverage = ordered_points(rotation, reverse, self.planner.ring_radius_m)

        while self.action_count < self.planner.max_actions:
            complete = len(self.coverage_completed) == len(self.coverage)
            done, reason = termination_status(self.channels, complete, self.physical)
            if done:
                self.client.exit()
                return self._result(True, reason, wall_start)
            if reason == "invalid_below_problem_lower_bound":
                self.diagnostics.append({"type": reason})
                self.client.exit()
                return self._result(False, reason, wall_start)
            if self.client.real_time_left_s() <= self.planner.real_time_reserve_s:
                self.diagnostics.append({"type": "real_deadline_guard", "remaining_s": self.client.real_time_left_s()})
                self.client.exit()
                return self._result(False, "real_deadline_guard", wall_start)
            remaining = [i for i in range(1, len(self.coverage)) if i not in self.coverage_completed]
            action = self.scheduler.choose(
                self.channels,
                np.asarray(self.client.position, float),
                self.client.current_channel,
                self.coverage,
                remaining,
                self.consecutive_local,
            )
            self.diagnostics.append({
                "type": "decision", "kind": action.kind.value,
                "position": action.position.tolist(), "channel": action.channel,
                "score_s": action.score_s, "source": action.source,
                "certified": action.certified,
            })
            if action.kind == ActionKind.SEARCH:
                index = next(i for i in remaining if np.allclose(self.coverage[i], action.position))
                self._scan_coverage(index)
            elif action.kind == ActionKind.LOCALIZE:
                assert action.channel is not None
                self._measure(action.position, action.channel)
                self.consecutive_local += 1
            else:
                assert action.channel is not None
                self._clear(action.position, action.channel, action.certified, action.source)
                self.consecutive_local += 1
        self.diagnostics.append({"type": "max_actions_exceeded", "limit": self.planner.max_actions})
        self.client.exit()
        return self._result(False, "max_actions_exceeded", wall_start)
