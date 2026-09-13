"""论文第 4 节：四类第二检测点策略与 250→100→50 m 搜索。"""
from __future__ import annotations

from dataclasses import dataclass
import math
from typing import Callable

import numpy as np


@dataclass(frozen=True)
class ActiveContext:
    first_station: np.ndarray
    target_samples: np.ndarray
    receive_radius_samples: np.ndarray
    first_region_diameter: float
    arena_radius: float = 1800.0
    bearing_sigma_rad: float = math.radians(1.0) / math.sqrt(3.0)

    def __post_init__(self) -> None:
        n = len(self.target_samples)
        if self.target_samples.shape != (n, 2) or len(self.receive_radius_samples) != n:
            raise ValueError("target_samples must be (n,2), with one radius per sample")


@dataclass(frozen=True)
class Selection:
    strategy: str
    point: np.ndarray
    objective: float
    evaluated_candidates: int


def bearing_fim(stations: np.ndarray, target: np.ndarray, sigma: float) -> np.ndarray:
    """纯方位局部 FIM；只用于软排序，不作为硬可行域。"""
    delta = target - np.asarray(stations, dtype=float)
    r2 = np.sum(delta * delta, axis=1)
    if np.any(r2 < 1e-12):
        return np.zeros((2, 2))
    jacobian = np.column_stack((-delta[:, 1] / r2, delta[:, 0] / r2))
    return (jacobian.T @ jacobian) / sigma**2


def _intersection_sine(s1: np.ndarray, s2: np.ndarray, targets: np.ndarray) -> np.ndarray:
    first, second = s1 - targets, s2 - targets
    numerator = np.abs(first[:, 0] * second[:, 1] - first[:, 1] * second[:, 0])
    denominator = np.linalg.norm(first, axis=1) * np.linalg.norm(second, axis=1)
    return numerator / np.maximum(denominator, 1e-12)


def strategy_scores(ctx: ActiveContext, candidates: np.ndarray, strategy: str) -> np.ndarray:
    """返回待最小化的分数；Geometry/E-optimal 在内部取负号。"""
    candidates = np.asarray(candidates, dtype=float)
    values = np.empty(len(candidates), dtype=float)
    targets = ctx.target_samples
    d1 = np.linalg.norm(targets - ctx.first_station, axis=1)
    for i, point in enumerate(candidates):
        d2 = np.linalg.norm(targets - point, axis=1)
        received = d2 <= ctx.receive_radius_samples
        if strategy == "geometry":
            quality = _intersection_sine(ctx.first_station, point, targets)
            quality /= np.sqrt(np.maximum(d1 * d2, 10_000.0))
            values[i] = -float(np.mean(quality * received))
            continue
        metrics = []
        for target, visible in zip(targets, received):
            if not visible:
                metrics.append(ctx.first_region_diameter if strategy == "gdop_mean" else 0.0)
                continue
            fim = bearing_fim(np.vstack((ctx.first_station, point)), target,
                              ctx.bearing_sigma_rad)
            eig = np.linalg.eigvalsh(fim)
            if strategy == "fim_e":
                metrics.append(-float(eig[0]))
            elif strategy == "gdop_mean":
                metrics.append(ctx.first_region_diameter if eig[0] <= 1e-12
                               else math.sqrt(float(np.trace(np.linalg.inv(fim)))))
            else:
                raise ValueError(f"unknown deterministic strategy: {strategy}")
        values[i] = float(np.mean(metrics))
    return values


def _disk_grid(radius: float, step: float, center: np.ndarray | None = None,
               window: float | None = None) -> np.ndarray:
    if center is None:
        low_x = low_y = -radius
        high_x = high_y = radius
    else:
        half = float(window)
        low_x, low_y = center - half
        high_x, high_y = center + half
    xs = np.arange(math.floor(low_x / step) * step,
                   math.ceil(high_x / step) * step + 0.5 * step, step)
    ys = np.arange(math.floor(low_y / step) * step,
                   math.ceil(high_y / step) * step + 0.5 * step, step)
    xx, yy = np.meshgrid(xs, ys)
    points = np.column_stack((xx.ravel(), yy.ravel()))
    return points[np.sum(points * points, axis=1) <= radius**2 + 1e-9]


def select_second_point(ctx: ActiveContext, strategy: str, seed: int = 0,
                        steps: tuple[float, ...] = (250.0, 100.0, 50.0),
                        top_k: int = 3) -> Selection:
    """确定性策略作粗到细搜索；Random 在同一 250 m 候选域抽样。"""
    coarse = _disk_grid(ctx.arena_radius, steps[0])
    if strategy == "random":
        rng = np.random.default_rng(seed + 1009)
        point = coarse[int(rng.integers(len(coarse)))]
        return Selection(strategy, point, 0.0, len(coarse))

    candidates, evaluated = coarse, 0
    best_points = np.empty((0, 2))
    best_value = math.inf
    for level, step in enumerate(steps):
        if level:
            pools = [_disk_grid(ctx.arena_radius, step, p, 1.25 * steps[level - 1])
                     for p in best_points]
            candidates = np.unique(np.vstack(pools), axis=0)
        values = strategy_scores(ctx, candidates, strategy)
        order = np.argsort(values, kind="stable")
        best_points = candidates[order[:min(top_k, len(order))]]
        best_value = float(values[order[0]])
        evaluated += len(candidates)
    return Selection(strategy, best_points[0], best_value, evaluated)


STRATEGIES: dict[str, Callable[..., Selection]] = {
    name: (lambda ctx, seed=0, name=name: select_second_point(ctx, name, seed))
    for name in ("gdop_mean", "geometry", "fim_e", "random")
}
