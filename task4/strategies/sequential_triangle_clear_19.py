from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
import math
import time

from task4.client import RobotAPI
from task4.geometry import (
    Point,
    angle_delta_deg,
    bearing_deg,
    clip_convex,
    distance,
    enclosing_center_radius,
    polygon_centroid,
)

from .base import BaseStrategy, ChannelBelief, StrategyResult
from .triangle_cells import (
    TriangleCell,
    cells_closed_at,
    fixed_start_end_route,
    main_points,
    triangle_cells,
)


SAFE_CLEAR_RADIUS_M = 19.5
EARLY_CLEAR_RADIUS_M = 30.0
FAILED_TARGET_SHIFT_M = 5.0
SINGLE_VISIBLE_MAX_CHECKS = 3
CROSS_VIEW_MAX_CHECKS = 2
RESIDUAL_MAX_CHECKS = 4
MIN_CHECK_SEPARATION_M = 20.0


@dataclass(frozen=True)
class LocalTask:
    kind: str  # clear, single_visible, cross_view, residual
    channel: int
    cell_id: int
    point: Point

    @property
    def key(self) -> tuple[str, int, int, float, float]:
        return (self.kind, self.channel, self.cell_id, round(self.point[0], 6), round(self.point[1], 6))


@dataclass(frozen=True)
class CellAssessment:
    channel: int
    cell_id: int
    positive_count: int
    signature_complete: bool
    outcome: str
    local_polygon: tuple[Point, ...]


class SequentialTriangleClear19Strategy(BaseStrategy):
    """Fixed P1..P19 search with immediate settlement of newly closed cells.

    Cell membership is never assigned permanently.  Every settlement intersects the
    channel's global, all-history bearing region with the cell that just closed.
    The six circular caps outside the inner hexagonal triangulation are handled by a
    final residual pass over already discovered channels.  Consequently ordinary
    discovered boundary sources are not forgotten, while an unseen, nearly outward-
    facing directional source in a cap remains an explicit evidence-boundary risk.
    """

    name = "sequential_triangle_clear_19"

    def __init__(
        self,
        grid_spacing: float = 600.0,
        grid_half_extent: float = 1800.0,
        *,
        early_clear_radius_m: float = EARLY_CLEAR_RADIUS_M,
    ):
        super().__init__(grid_spacing, grid_half_extent)
        if early_clear_radius_m < SAFE_CLEAR_RADIUS_M:
            raise ValueError("early_clear_radius_m must be at least 19.5")
        self.early_clear_radius_m = early_clear_radius_m
        self.points = main_points()
        self.cells = triangle_cells()
        self._cell_by_id = {cell.cell_id: cell for cell in self.cells}
        self._vertex_results: dict[tuple[int, int], str] = {}
        self._excluded_cells: dict[int, set[int]] = defaultdict(set)
        self._local_checks: Counter[tuple[int, int, str]] = Counter()
        self._residual_checks: Counter[int] = Counter()
        self._failed_optical_targets: dict[int, list[Point]] = defaultdict(list)
        self._signature_recorded: set[tuple[int, int]] = set()
        self._current_main_index = 0
        self._measuring_main = False
        self._movement_distance_m = 0.0
        self._stats: dict[str, object] = {
            "visited_main_points": 0,
            "closed_cells": 0,
            "cell_settlements": 0,
            "channel_cell_assessments": 0,
            "main_grid_measurements": 0,
            "active_channel_measurements": 0,
            "unseen_channel_measurements": 0,
            "local_check_count": 0,
            "single_visible_check_count": 0,
            "cross_view_check_count": 0,
            "clear_attempts": 0,
            "early_optical_failures": 0,
            "main_skeleton_distance_m": 0.0,
            "local_detour_distance_m": 0.0,
            "total_movement_distance_m": 0.0,
            "cleared_before_p7": 0,
            "cleared_before_p19": 0,
            "residual_active_channels_after_p19": 0,
            "positive_signature_distribution": {"0": 0, "1": 0, "2": 0, "3": 0},
            "per_cell_local_task_count": {},
        }

    def _measure(self, api: RobotAPI, position: Point, channel: int) -> dict:
        before = self.position
        prior_status = self.beliefs[channel].status
        response = super()._measure(api, position, channel)
        self._movement_distance_m += distance(before, position)
        if self._measuring_main:
            self._stats["main_grid_measurements"] = int(self._stats["main_grid_measurements"]) + 1
            key = "unseen_channel_measurements" if prior_status == "unseen" else "active_channel_measurements"
            self._stats[key] = int(self._stats[key]) + 1
        return response

    def _clear(self, api: RobotAPI, position: Point, channel: int) -> bool:
        before = self.position
        self._stats["clear_attempts"] = int(self._stats["clear_attempts"]) + 1
        success = super()._clear(api, position, channel)
        self._movement_distance_m += distance(before, position)
        if success:
            if self._current_main_index < 7:
                self._stats["cleared_before_p7"] = int(self._stats["cleared_before_p7"]) + 1
            if self._current_main_index < 19:
                self._stats["cleared_before_p19"] = int(self._stats["cleared_before_p19"]) + 1
        else:
            self._failed_optical_targets[channel].append(position)
            self._stats["early_optical_failures"] = int(self._stats["early_optical_failures"]) + 1
        return success

    def _global_region(self, belief: ChannelBelief) -> list[Point]:
        return belief.polygon() if belief.observations else []

    def _local_region(self, belief: ChannelBelief, cell: TriangleCell) -> list[Point]:
        global_region = self._global_region(belief)
        return clip_convex(global_region, list(cell.polygon)) if global_region else []

    def _record_signature(self, assessment: CellAssessment) -> None:
        key = (assessment.channel, assessment.cell_id)
        if key in self._signature_recorded or not assessment.signature_complete:
            return
        self._signature_recorded.add(key)
        distribution = self._stats["positive_signature_distribution"]
        assert isinstance(distribution, dict)
        count_key = str(assessment.positive_count)
        distribution[count_key] = int(distribution[count_key]) + 1

    def assess_cell(self, channel: int, cell_id: int) -> CellAssessment:
        """Classify one global-belief/cell intersection without simulator truth."""
        belief = self.beliefs[channel]
        cell = self._cell_by_id[cell_id]
        results = [self._vertex_results.get((vertex, channel)) for vertex in cell.vertex_ids]
        positives = sum(result in {"direction", "near"} for result in results)
        complete = all(result is not None for result in results)
        if belief.status == "cleared" or cell_id in self._excluded_cells[channel]:
            return CellAssessment(channel, cell_id, positives, complete, "settled", ())
        local = self._local_region(belief, cell)
        if not local:
            return CellAssessment(channel, cell_id, positives, complete, "outside", ())
        if complete and positives == 0:
            self._excluded_cells[channel].add(cell_id)
            result = CellAssessment(channel, cell_id, 0, True, "excluded", tuple(local))
            self._record_signature(result)
            return result
        if belief.status == "located" and belief.clear_target is not None:
            outcome = "clearable"
        elif positives == 1:
            outcome = "single_visible"
        elif positives >= 2:
            outcome = "multi_visible"
        else:
            outcome = "incomplete"
        result = CellAssessment(channel, cell_id, positives, complete, outcome, tuple(local))
        self._record_signature(result)
        return result

    def _clear_candidate(self, belief: ChannelBelief) -> Point | None:
        if belief.status == "located" and belief.clear_target is not None:
            return belief.clear_target
        region = self._global_region(belief)
        if len(belief.observations) < 2 or not region:
            return None
        center, radius = enclosing_center_radius(region)
        limit = SAFE_CLEAR_RADIUS_M if radius <= SAFE_CLEAR_RADIUS_M else self.early_clear_radius_m
        if radius > limit:
            return None
        if any(
            distance(center, old) < FAILED_TARGET_SHIFT_M
            for old in self._failed_optical_targets[belief.channel]
        ):
            return None
        return center

    @staticmethod
    def _point_in_cell(point: Point, cell: TriangleCell) -> bool:
        for a, b in zip(cell.polygon, cell.polygon[1:] + cell.polygon[:1]):
            if (b[0] - a[0]) * (point[1] - a[1]) - (b[1] - a[1]) * (point[0] - a[0]) < -1e-7:
                return False
        return True

    def _crossing_value(self, point: Point, target: Point, belief: ChannelBelief) -> float:
        proposed = bearing_deg(point, target)
        return max(
            (
                abs(math.sin(math.radians(angle_delta_deg(proposed, theta))))
                for _, theta in belief.observations
            ),
            default=0.0,
        )

    def _cell_check_point(
        self,
        belief: ChannelBelief,
        assessment: CellAssessment,
        next_fixed: Point,
    ) -> Point | None:
        cell = self._cell_by_id[assessment.cell_id]
        local = list(assessment.local_polygon)
        if not local:
            return None
        center, _ = enclosing_center_radius(local)
        centroid = polygon_centroid(local)
        vertices = list(cell.polygon)
        candidates: list[Point] = [center, centroid]
        candidates.extend(((a[0] + b[0]) / 2.0, (a[1] + b[1]) / 2.0) for a, b in zip(vertices, vertices[1:] + vertices[:1]))
        if assessment.positive_count == 1:
            positive_vertex = next(
                self.points[vertex - 1]
                for vertex in cell.vertex_ids
                if self._vertex_results.get((vertex, belief.channel)) in {"direction", "near"}
            )
            candidates.extend(
                (
                    positive_vertex[0] * weight + centroid[0] * (1.0 - weight),
                    positive_vertex[1] * weight + centroid[1] * (1.0 - weight),
                )
                for weight in (0.35, 0.55, 0.75)
            )
        attempted = belief.attempted_positions
        candidates = [
            point
            for point in candidates
            if all(distance(point, old) >= MIN_CHECK_SEPARATION_M for old in attempted)
        ]
        if not candidates:
            return None
        return max(
            candidates,
            key=lambda point: (
                1200.0 * self._crossing_value(point, center, belief)
                - distance(self.position, point)
                - distance(point, next_fixed),
                -point[0],
                -point[1],
            ),
        )

    def _build_cell_tasks(self, cell_ids: tuple[int, ...], next_fixed: Point) -> list[LocalTask]:
        tasks: list[LocalTask] = []
        for belief in self.beliefs.values():
            if belief.status in {"unseen", "cleared"}:
                continue
            assessments = [self.assess_cell(belief.channel, cell_id) for cell_id in cell_ids]
            clear_target = self._clear_candidate(belief)
            clearable_here = [
                assessment
                for assessment in assessments
                if assessment.local_polygon
                and assessment.outcome != "excluded"
                and (assessment.positive_count > 0 or not assessment.signature_complete)
            ]
            located_cells = [
                cell_id
                for cell_id in cell_ids
                if clear_target is not None
                and belief.status == "located"
                and self._point_in_cell(clear_target, self._cell_by_id[cell_id])
            ]
            if clear_target is not None and (clearable_here or located_cells):
                cell_id = (
                    min(clearable_here, key=lambda item: (-item.positive_count, item.cell_id)).cell_id
                    if clearable_here
                    else min(located_cells)
                )
                tasks.append(LocalTask("clear", belief.channel, cell_id, clear_target))
                continue
            relevant = [a for a in assessments if a.outcome in {"single_visible", "multi_visible"}]
            if not relevant:
                continue
            assessment = min(relevant, key=lambda item: (-item.positive_count, item.cell_id))
            if assessment.outcome == "single_visible":
                kind = "single_visible"
                maximum = SINGLE_VISIBLE_MAX_CHECKS
            else:
                kind = "cross_view"
                maximum = CROSS_VIEW_MAX_CHECKS
            if self._local_checks[(belief.channel, assessment.cell_id, kind)] >= maximum:
                continue
            point = self._cell_check_point(belief, assessment, next_fixed)
            if point is not None:
                tasks.append(LocalTask(kind, belief.channel, assessment.cell_id, point))
        return tasks

    def _execute_task(self, api: RobotAPI, task: LocalTask) -> None:
        if task.kind == "clear":
            belief = self.beliefs[task.channel]
            if not self._clear(api, task.point, task.channel):
                belief.status = "active"
                belief.clear_target = None
            return
        belief = self.beliefs[task.channel]
        belief.attempted_positions.append(task.point)
        self._local_checks[(task.channel, task.cell_id, task.kind)] += 1
        self._stats["local_check_count"] = int(self._stats["local_check_count"]) + 1
        if task.kind == "single_visible":
            self._stats["single_visible_check_count"] = int(self._stats["single_visible_check_count"]) + 1
        elif task.kind == "cross_view":
            self._stats["cross_view_check_count"] = int(self._stats["cross_view_check_count"]) + 1
        per_cell = self._stats["per_cell_local_task_count"]
        assert isinstance(per_cell, dict)
        key = str(task.cell_id)
        per_cell[key] = int(per_cell.get(key, 0)) + 1
        response = self._measure(api, task.point, task.channel)
        if response["measure_result"] == "near":
            belief.status = "located"
            belief.clear_target = task.point

    def _settle_cells(self, api: RobotAPI, cell_ids: tuple[int, ...], next_fixed: Point) -> None:
        if not cell_ids:
            return
        self._stats["closed_cells"] = int(self._stats["closed_cells"]) + len(cell_ids)
        assessed_pairs: set[tuple[int, int]] = set()
        for _ in range(80):
            tasks = self._build_cell_tasks(cell_ids, next_fixed)
            for belief in self.beliefs.values():
                if belief.status != "unseen":
                    assessed_pairs.update((belief.channel, cell_id) for cell_id in cell_ids)
            if not tasks:
                break
            route = fixed_start_end_route(
                tasks,
                self.position,
                next_fixed,
                point=lambda task: task.point,
                tie_key=lambda task: task.key,
            )
            self._execute_task(api, route[0])
        self._stats["cell_settlements"] = int(self._stats["cell_settlements"]) + len(cell_ids)
        self._stats["channel_cell_assessments"] = int(self._stats["channel_cell_assessments"]) + len(assessed_pairs)

    def _point_relevant_to_active(self, point_id: int, belief: ChannelBelief) -> bool:
        if belief.status != "active" or not belief.observations:
            return False
        for cell in self.cells:
            if point_id in cell.vertex_ids and cell.closed_at >= point_id and cell.cell_id not in self._excluded_cells[belief.channel]:
                if self._local_region(belief, cell):
                    return True
        return False

    def _main_scan_channels(self, point_id: int) -> list[int]:
        discovered = sum(belief.status != "unseen" for belief in self.beliefs.values())
        channels = []
        for channel, belief in self.beliefs.items():
            if belief.status == "unseen" and discovered < 16:
                channels.append(channel)
            elif self._point_relevant_to_active(point_id, belief):
                channels.append(channel)
        order = self._channel_scan_order({"located", "cleared"})
        return [channel for channel in order if channel in channels]

    def _residual_check_point(self, belief: ChannelBelief, anchor: Point) -> Point | None:
        region = self._global_region(belief)
        if not region:
            return None
        center, radius = enclosing_center_radius(region)
        candidates: list[Point] = []
        # After a guarded optical miss, approach the failed center from a station
        # that definitely received this directional source.  The segment from the
        # source toward that station remains in the visible half-plane and is much
        # safer than an arbitrary ring sample.
        if self._failed_optical_targets[belief.channel]:
            failed = self._failed_optical_targets[belief.channel][-1]
            for station, _ in reversed(belief.observations):
                span = distance(station, failed)
                if span <= 1e-9:
                    continue
                approach = (
                    failed[0] + 100.0 * (station[0] - failed[0]) / span,
                    failed[1] + 100.0 * (station[1] - failed[1]) / span,
                )
                if all(
                    distance(approach, old) >= MIN_CHECK_SEPARATION_M
                    for old in belief.attempted_positions
                ):
                    return approach
        if belief.observations:
            station, theta = belief.observations[-1]
            angle = math.radians(theta)
            forward = (math.cos(angle), math.sin(angle))
            lateral = (-forward[1], forward[0])
            for advance, offset in ((300.0, 0.0), (520.0, 0.0), (300.0, 260.0), (300.0, -260.0), (520.0, 320.0), (520.0, -320.0)):
                candidates.append(
                    (
                        station[0] + advance * forward[0] + offset * lateral[0],
                        station[1] + advance * forward[1] + offset * lateral[1],
                    )
                )
        ring = min(420.0, max(140.0, radius * 0.3))
        for index in range(8):
            angle = 2.0 * math.pi * index / 8.0
            candidates.append((center[0] + ring * math.cos(angle), center[1] + ring * math.sin(angle)))
        bounded: list[Point] = []
        for point in candidates:
            norm = math.hypot(*point)
            if norm > self.grid_half_extent:
                point = (point[0] * self.grid_half_extent / norm, point[1] * self.grid_half_extent / norm)
            if all(distance(point, old) >= MIN_CHECK_SEPARATION_M for old in belief.attempted_positions):
                bounded.append(point)
        if not bounded:
            return None
        return max(
            bounded,
            key=lambda point: (
                1200.0 * self._crossing_value(point, center, belief)
                - distance(self.position, point)
                - distance(point, anchor),
                -point[0],
                -point[1],
            ),
        )

    def _build_residual_tasks(self, anchor: Point) -> list[LocalTask]:
        tasks = []
        for belief in self.beliefs.values():
            if belief.status in {"unseen", "cleared"}:
                continue
            target = self._clear_candidate(belief)
            if target is not None:
                tasks.append(LocalTask("clear", belief.channel, 0, target))
            elif belief.status == "active" and self._residual_checks[belief.channel] < RESIDUAL_MAX_CHECKS:
                point = self._residual_check_point(belief, anchor)
                if point is not None:
                    tasks.append(LocalTask("residual", belief.channel, 0, point))
        return tasks

    def _settle_residual(self, api: RobotAPI, anchor: Point) -> None:
        for _ in range(100):
            tasks = self._build_residual_tasks(anchor)
            if not tasks:
                break
            route = fixed_start_end_route(
                tasks,
                self.position,
                anchor,
                point=lambda task: task.point,
                tie_key=lambda task: task.key,
            )
            task = route[0]
            if task.kind == "residual":
                self._residual_checks[task.channel] += 1
            self._execute_task(api, task)

    def _diagnostics(self) -> dict[str, object]:
        self._stats["total_movement_distance_m"] = self._movement_distance_m
        self._stats["local_detour_distance_m"] = max(
            0.0,
            self._movement_distance_m - float(self._stats["main_skeleton_distance_m"]),
        )
        self._stats["residual_active_channels_after_p19"] = sum(
            belief.status in {"active", "located"} for belief in self.beliefs.values()
        )
        return dict(self._stats)

    def run(self, api: RobotAPI) -> StrategyResult:
        started = time.perf_counter()
        api.enter()
        visited = 0
        for point_id, point in enumerate(self.points, start=1):
            self._current_main_index = point_id
            if point_id > 1:
                self._stats["main_skeleton_distance_m"] = float(self._stats["main_skeleton_distance_m"]) + distance(self.points[point_id - 2], point)
            channels = self._main_scan_channels(point_id)
            self._measuring_main = True
            for channel in channels:
                response = self._measure(api, point, channel)
                self._vertex_results[(point_id, channel)] = response["measure_result"]
                belief = self.beliefs[channel]
                if response["measure_result"] == "near":
                    belief.status = "located"
                    belief.clear_target = point
            self._measuring_main = False
            visited = point_id
            self._stats["visited_main_points"] = visited
            next_fixed = self.points[point_id] if point_id < len(self.points) else point
            closed = tuple(cell.cell_id for cell in cells_closed_at(point_id))
            self._settle_cells(api, closed, next_fixed)
            if sum(belief.status == "cleared" for belief in self.beliefs.values()) == 16:
                break

        if visited == len(self.points):
            self._settle_residual(api, self.points[-1])
        result = self._finish(api, started)
        result.diagnostics = self._diagnostics()
        return result
