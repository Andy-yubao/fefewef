"""论文第 5、6 节的保证层与滚动路线原语。

本文件不绑定比赛网络接口。控制器只需把接口响应依次传给 ChannelGrid；
软路线函数不得直接修改 possible，也不得签发清除或终止证书。
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
import math
from typing import Iterable

import numpy as np

from geometry import (Circle, DiskClippedRegion, Observation as BearingObservation,
                      cell_corners, clip_polygon_with_disk, intersect_bearings,
                      minimum_enclosing_circle)

ARENA_RADIUS = 1800.0
RECEIVE_MIN = 1000.0
RECEIVE_MAX = 1500.0
NEAR_RADIUS = 5.0
CLEAR_RADIUS = 20.0
GRID_STEP = 5.0
CLEAR_MARGIN = 0.25
MAX_SOURCES = 16
CHANNELS = 20


def q3_coverage_points(ring_radius: float = 1200.0) -> np.ndarray:
    angles = np.arange(6) * math.pi / 3.0
    return np.vstack((np.zeros((1, 2)),
                      np.column_stack((ring_radius * np.cos(angles),
                                       ring_radius * np.sin(angles)))))


def q3_worst_coverage_distance(ring_radius: float = 1200.0) -> float:
    """一个 60° 扇区内比较中心点与相邻环点的 Voronoi 交点。"""
    # x^2+y^2=(x-r)^2+y^2 且 y=x*tan(30°)，并取目标圆边界。
    x = ring_radius / 2.0
    y = min(x / math.sqrt(3.0), math.sqrt(ARENA_RADIUS**2 - x**2))
    candidates = [math.hypot(x, y)]
    # 外边界上到中心/环点最近距离的最大值出现在角平分线上。
    boundary = ARENA_RADIUS * np.array([math.cos(math.pi / 6), math.sin(math.pi / 6)])
    candidates.append(min(np.linalg.norm(boundary),
                          np.linalg.norm(boundary - np.array([ring_radius, 0.0])),
                          np.linalg.norm(boundary - ring_radius * np.array([.5, math.sqrt(3)/2]))))
    return float(max(candidates))


def q4_double_ring(inner_radius: float = 980.0, margin: float = 0.25) -> np.ndarray:
    """25 点定向发现结构：原点、旋转 15° 的内环、外接十二边形。"""
    half, step = math.pi / 12.0, math.pi / 6.0
    outer_radius = ARENA_RADIUS / math.cos(half) + margin
    edges = (inner_radius, 2 * inner_radius * math.sin(half),
             2 * outer_radius * math.sin(half),
             math.sqrt(outer_radius**2 + inner_radius**2
                       - 2 * outer_radius * inner_radius * math.cos(half)))
    if max(edges) >= RECEIVE_MIN:
        raise ValueError("triangulation edge must be below the guaranteed receive radius")
    inner = [[inner_radius * math.cos(half + i * step),
              inner_radius * math.sin(half + i * step)] for i in range(12)]
    outer = [[outer_radius * math.cos(i * step),
              outer_radius * math.sin(i * step)] for i in range(12)]
    return np.asarray([[0.0, 0.0], *inner, *outer])


def q4_positive_region(observations: Iterable[BearingObservation]) -> DiskClippedRegion:
    """Q4 只用正示向构造区域，并统一加入 ±1.01° 数值余量。"""
    widened = [BearingObservation(obs.station, obs.bearing_deg, 1.01)
               for obs in observations]
    return clip_polygon_with_disk(intersect_bearings(widened), ARENA_RADIUS)


def optical_cover(center: np.ndarray, radius: float = 36.0,
                  count: int = 10) -> np.ndarray:
    """Q4 的圆心失败后，返回半径 36 m 的十点环。"""
    angles = TAU * np.arange(count) / count
    return np.asarray(center) + radius * np.column_stack((np.cos(angles), np.sin(angles)))


TAU = 2.0 * math.pi


def optical_cover_bound(certified_radius: float = 50.0,
                        ring_radius: float = 36.0, count: int = 10) -> float:
    """目标距圆心在 [20,R] 时，到最近环点距离的严格上界。"""
    def distance(rho: float) -> float:
        return math.sqrt(rho**2 + ring_radius**2
                         - 2 * rho * ring_radius * math.cos(math.pi / count))
    return max(distance(CLEAR_RADIUS), distance(certified_radius))


def optical_cover_time_bound() -> float:
    points = optical_cover(np.zeros(2))
    route_distance = np.linalg.norm(points[0])
    route_distance += sum(np.linalg.norm(b - a) for a, b in zip(points[:-1], points[1:]))
    # 圆心光学 3 s；最坏十个环点各光学 3 s；最后一次激光 2 s。
    return route_distance / 5.0 + 11 * 3.0 + 2.0


def _min_distance_to_cells(point: np.ndarray, centers: np.ndarray, half: float) -> np.ndarray:
    delta = np.maximum(np.abs(centers - point) - half, 0.0)
    return np.hypot(delta[:, 0], delta[:, 1])


def _max_distance_to_cells(point: np.ndarray, centers: np.ndarray, half: float) -> np.ndarray:
    delta = np.abs(centers - point) + half
    return np.hypot(delta[:, 0], delta[:, 1])


def target_grid(step: float = GRID_STEP) -> np.ndarray:
    """保留所有与目标圆相交的闭方格中心，故为连续区域的外包。"""
    n = math.ceil(2 * ARENA_RADIUS / step)
    values = -n * step / 2 + (np.arange(n) + 0.5) * step
    xx, yy = np.meshgrid(values, values)
    centers = np.column_stack((xx.ravel(), yy.ravel()))
    return centers[_min_distance_to_cells(np.zeros(2), centers, step / 2) <= ARENA_RADIUS]


class Status(str, Enum):
    UNKNOWN = "unknown"
    FOUND = "found"
    CLEARED = "cleared"
    ABSENT = "absent"


@dataclass
class ChannelGrid:
    """Q3 单频道硬状态；每次删除都要求整个方格不可能包含真值。"""
    channel: int
    centers: np.ndarray
    step: float = GRID_STEP
    possible: np.ndarray = field(init=False)
    status: Status = Status.UNKNOWN
    covered_at: set[int] = field(default_factory=set)
    positive_count: int = 0

    def __post_init__(self) -> None:
        self.possible = np.ones(len(self.centers), dtype=bool)

    def update(self, position: Iterable[float], result: str,
               bearing_deg: float | None = None, coverage_index: int | None = None,
               directional: bool = False) -> None:
        position = np.asarray(position, dtype=float)
        half = self.step / 2.0
        centers = self.centers
        if coverage_index is not None:
            self.covered_at.add(coverage_index)
        if result == "direction":
            if bearing_deg is None:
                raise ValueError("direction response requires bearing_deg")
            delta = centers - position
            distance = np.linalg.norm(delta, axis=1)
            pad = np.full(len(centers), math.pi)
            outside = distance > self.step / math.sqrt(2.0)
            pad[outside] = np.arcsin(np.minimum(1.0,
                self.step / math.sqrt(2.0) / distance[outside]))
            measured = math.radians(bearing_deg)
            angle = (np.arctan2(delta[:, 1], delta[:, 0]) - measured + math.pi) % TAU - math.pi
            keep = np.abs(angle) <= math.radians(1.01 if directional else 1.000001) + pad
            keep &= _min_distance_to_cells(position, centers, half) <= RECEIVE_MAX
            keep &= _max_distance_to_cells(position, centers, half) > NEAR_RADIUS
            self.positive_count += 1
            self.status = Status.FOUND
        elif result == "no_signal":
            # 定向源的负观测没有空间排除力。
            keep = np.ones(len(centers), dtype=bool) if directional else (
                _max_distance_to_cells(position, centers, half) > RECEIVE_MIN)
        elif result == "near":
            keep = _min_distance_to_cells(position, centers, half) <= NEAR_RADIUS
            self.status = Status.FOUND
        else:
            raise ValueError(f"unknown response: {result}")
        proposed = self.possible & keep
        if np.any(proposed) or (self.status == Status.UNKNOWN and result == "no_signal"):
            self.possible = proposed

    def certificate(self) -> Circle:
        return minimum_enclosing_circle(cell_corners(self.centers[self.possible], self.step),
                                        seed=self.channel)

    def clear_point(self, limit: float = CLEAR_RADIUS - CLEAR_MARGIN) -> np.ndarray | None:
        circle = self.certificate()
        return circle.center if circle.radius <= limit else None

    def fallback_clear_points(self) -> np.ndarray:
        """有限无缝兜底：5 m 方格中心覆盖整个方格（半对角线 < 20 m）。"""
        if self.step / math.sqrt(2.0) > CLEAR_RADIUS:
            raise ValueError("grid is too coarse for the optical fallback certificate")
        return self.centers[self.possible].copy()

    def mark_absent(self, required_points: int = 7) -> bool:
        if self.status == Status.UNKNOWN and len(self.covered_at) == required_points:
            self.status = Status.ABSENT
            return True
        return False


def termination(states: Iterable[ChannelGrid], coverage_complete: bool) -> tuple[bool, str]:
    states = list(states)
    cleared = sum(s.status == Status.CLEARED for s in states)
    if cleared == MAX_SOURCES:
        return True, "known upper bound reached"
    if coverage_complete and all(s.status in {Status.CLEARED, Status.ABSENT} for s in states):
        return True, "coverage certificate and every found source cleared"
    return False, "unfinished"


@dataclass(frozen=True)
class Task:
    kind: str
    point: np.ndarray
    channel: int | None = None
    operation_seconds: float = 0.0
    completion_seconds: float = 0.0


def task_cost(task: Task, current: np.ndarray, speed: float = 5.0) -> float:
    """C_preview=C_now+C_localize+C_coverage+C_clear。"""
    return float(np.linalg.norm(task.point - current) / speed
                 + task.operation_seconds + task.completion_seconds)


def open_route(tasks: list[Task], start: np.ndarray) -> list[Task]:
    """确定性最近邻 + 开放路径 2-opt；滚动控制器只执行首节点。"""
    remaining, route, current = list(tasks), [], np.asarray(start, dtype=float)
    while remaining:
        chosen = min(remaining, key=lambda t: (task_cost(t, current), t.kind,
                                                -1 if t.channel is None else t.channel))
        remaining.remove(chosen)
        route.append(chosen)
        current = chosen.point
    while True:
        improved = False
        for i in range(len(route) - 1):
            before = np.asarray(start) if i == 0 else route[i - 1].point
            for j in range(i + 1, len(route)):
                old = np.linalg.norm(before - route[i].point)
                new = np.linalg.norm(before - route[j].point)
                if j + 1 < len(route):
                    old += np.linalg.norm(route[j].point - route[j + 1].point)
                    new += np.linalg.norm(route[i].point - route[j + 1].point)
                if new + 1e-9 < old:
                    route[i:j + 1] = reversed(route[i:j + 1])
                    improved = True
                    break
            if improved:
                break
        if not improved:
            return route
