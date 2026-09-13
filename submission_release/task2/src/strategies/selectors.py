"""Second detection point selection strategies.

This module contains optimization only. Dataset generation, Monte Carlo loops,
statistics, and plotting deliberately live under task2/experiments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import time

import numpy as np
from ..config import PhysicalConfig, SearchConfig
from ..geometry.angles import bearing, intersection_angle
from ..geometry.regions import (candidate_diagnostics, candidate_regions,
                                region_area_diameter)
from ..localization.metrics import bearing_fim, covariance_metrics
from ..localization.observation import observe


@dataclass
class StrategyContext:
    sensor1: np.ndarray
    bearing1: float
    first_region: object
    posterior_points: np.ndarray
    radius_samples: np.ndarray
    physical: PhysicalConfig = field(default_factory=PhysicalConfig)
    search: SearchConfig = field(default_factory=SearchConfig)
    seed: int = 0


@dataclass
class SelectionResult:
    strategy: str
    point: np.ndarray
    objective: float
    runtime_s: float
    candidate_count: int
    diagnostics: dict = field(default_factory=dict)


def _pool(ctx, points=None):
    kwargs = dict(
        radius_samples=ctx.radius_samples,
        min_detection_probability=ctx.search.min_detection_probability,
        min_median_abs_sin_angle=ctx.search.min_median_abs_sin_angle,
        pruning_mode=ctx.search.pruning_mode)
    if points is None:
        c = candidate_regions(
            ctx.sensor1, ctx.posterior_points, ctx.physical,
            step=ctx.search.grid_step, domain=ctx.search.candidate_domain,
            **kwargs)
    else:
        points = np.asarray(points, dtype=float)
        if ctx.search.candidate_domain == "target_disk":
            points = points[np.sum(points * points, axis=1) <=
                            ctx.physical.target_radius ** 2 + 1e-9]
        c = candidate_diagnostics(
            points, ctx.sensor1, ctx.posterior_points, ctx.physical, **kwargs)
    idx = np.flatnonzero(c["recommended"])
    return c, idx


def _finish(name, grid, idx, values, maximize, start, extra=None):
    local = int(np.nanargmax(values[idx]) if maximize else np.nanargmin(values[idx]))
    chosen = idx[local]
    diag = {"grid_points": grid.tolist(), "objective_surface": values.tolist(),
            "maximize": maximize}
    if extra:
        diag.update(extra)
    return SelectionResult(name, grid[chosen].copy(), float(values[chosen]),
                           time.perf_counter() - start, len(idx), diag)


def select_random(ctx):
    start = time.perf_counter()
    c, idx = _pool(ctx)
    rng = np.random.default_rng(ctx.seed + 1009)
    chosen = int(rng.choice(idx))
    values = np.zeros(len(c["points"]))
    return SelectionResult("random", c["points"][chosen].copy(), 0.0,
                           time.perf_counter() - start, len(idx),
                           {"grid_points": c["points"].tolist(),
                            "objective_surface": values.tolist(),
                            "maximize": True})


def _geometry_surface(ctx, c, idx):
    grid, targets = c["points"], ctx.posterior_points
    scores = np.full(len(grid), -np.inf)
    for i in idx:
        d1 = np.linalg.norm(targets - ctx.sensor1, axis=1)
        d2 = np.linalg.norm(targets - grid[i], axis=1)
        ang = intersection_angle(ctx.sensor1, grid[i], targets)
        # Intersection sensitivity is proportional to sin(angle), while bearing
        # lateral error grows with range. A 100 m floor avoids near singularity.
        quality = np.abs(np.sin(ang)) / np.sqrt(np.maximum(d1 * d2, 10000.0))
        detected = d2 <= ctx.radius_samples
        scores[i] = np.mean(quality * detected)
    return scores


def _generic_coarse_to_fine(ctx, name, surface_fn, maximize):
    start = time.perf_counter()
    steps = [ctx.search.grid_step]
    if ctx.search.coarse_to_fine:
        steps.extend(ctx.search.refine_steps)
    centres, previous_step = None, ctx.search.grid_step
    levels, all_points, all_values = [], [], []
    chosen_point, chosen_value, total = None, None, 0
    for level, step in enumerate(steps, start=1):
        level_start = time.perf_counter()
        if centres is None:
            c, idx = _pool(ctx)
        else:
            points = _refinement_points(
                centres, previous_step, step, ctx.search.refine_radius_factor)
            c, idx = _pool(ctx, points)
        values = surface_fn(c, idx)
        order = idx[np.argsort(values[idx])]
        if maximize:
            order = order[::-1]
        centres = c["points"][order[:min(ctx.search.refine_top_k, len(order))]]
        chosen = int(order[0])
        chosen_point = c["points"][chosen].copy()
        chosen_value = float(values[chosen])
        total += len(idx)
        levels.append({"level": level, "step_m": float(step),
                       "candidate_count": int(len(idx)),
                       "best_x": float(chosen_point[0]),
                       "best_y": float(chosen_point[1]),
                       "best_objective": chosen_value,
                       "runtime_s": time.perf_counter() - level_start})
        all_points.extend(c["points"].tolist())
        all_values.extend(values.tolist())
        previous_step = step
    return SelectionResult(
        name, chosen_point, chosen_value, time.perf_counter() - start, total,
        {"grid_points": all_points, "objective_surface": all_values,
         "maximize": maximize, "search_levels": levels,
         "exact_objective_evaluation_count": 0})


def select_geometry(ctx):
    return _generic_coarse_to_fine(
        ctx, "geometry", lambda c, idx: _geometry_surface(ctx, c, idx), True)


def _fim_values(ctx, c, idx, criterion, worst=False):
    grid, targets = c["points"], ctx.posterior_points
    values = np.full(len(grid), np.inf if criterion in ("a", "gdop") else -np.inf)
    minimize = criterion in ("a", "gdop")
    first_diam = region_area_diameter(ctx.first_region)[1]
    for i in idx:
        per = []
        for g, r in zip(targets, ctx.radius_samples):
            if np.linalg.norm(g - grid[i]) > r:
                # No bearing: use an explicit finite lack-of-information penalty.
                per.append(first_diam ** 2 if criterion == "a" else
                           first_diam if criterion == "gdop" else
                           (-1.0e6 if criterion == "d" else 0.0))
                continue
            m = covariance_metrics(bearing_fim([ctx.sensor1, grid[i]], g))[criterion]
            if not np.isfinite(m):
                m = first_diam ** 2 if criterion == "a" else (
                    first_diam if criterion == "gdop" else
                    (-1.0e6 if criterion == "d" else 0.0))
            per.append(m)
        if worst:
            values[i] = max(per) if minimize else min(per)
        else:
            values[i] = float(np.mean(per))
    return values


def select_gdop_mean(ctx):
    return _generic_coarse_to_fine(
        ctx, "gdop_mean",
        lambda c, idx: _fim_values(ctx, c, idx, "gdop", False), False)


def select_gdop_worst(ctx):
    return _generic_coarse_to_fine(
        ctx, "gdop_worst",
        lambda c, idx: _fim_values(ctx, c, idx, "gdop", True), False)


def select_fim(ctx, criterion):
    label = {"a": "fim_a", "d": "fim_d", "e": "fim_e"}[criterion]
    maximize = criterion not in ("a", "gdop")
    result = _generic_coarse_to_fine(
        ctx, label,
        lambda c, idx: _fim_values(ctx, c, idx, criterion, False), maximize)
    result.diagnostics["gaussian_approximation"] = True
    return result


def _refinement_points(centres, previous_step, step, factor):
    radius = previous_step * factor
    offsets = np.arange(-radius, radius + 1e-9, step)
    pts = np.array([c + (dx, dy) for c in centres
                    for dx in offsets for dy in offsets], dtype=float)
    return np.unique(np.round(pts, 8), axis=0)


def _entropy_from_counts(counts):
    counts = np.asarray(counts, float)
    p = counts[counts > 0] / np.sum(counts)
    return float(-np.sum(p * np.log(p)))


def select_eig(ctx):
    """Discrete mutual information including bearing/no-signal/near outcomes."""
    start = time.perf_counter()
    c, idx = _pool(ctx)
    grid, targets = c["points"], ctx.posterior_points
    values = np.full(len(grid), -np.inf)
    errors = np.linspace(-1.0, 1.0, max(3, ctx.search.objective_error_samples)) * math.radians(
        ctx.physical.bearing_error_deg)
    bin_rad = math.radians(ctx.search.eig_bearing_bin_deg)
    for i in idx:
        all_outcomes = []
        conditional_entropies = []
        for g, r in zip(targets, ctx.radius_samples):
            outs = []
            for e in errors:
                o = observe(grid[i], g, r, e, ctx.physical.near_radius)
                if o["kind"] == "bearing":
                    key = ("b", int(math.floor(o["bearing"] / bin_rad)))
                else:
                    key = (o["kind"], 0)
                outs.append(key)
                all_outcomes.append(key)
            _, counts = np.unique(np.array([str(x) for x in outs]), return_counts=True)
            conditional_entropies.append(_entropy_from_counts(counts))
        _, total_counts = np.unique(np.array([str(x) for x in all_outcomes]),
                                    return_counts=True)
        values[i] = _entropy_from_counts(total_counts) - np.mean(conditional_entropies)
    return _finish("eig", grid, idx, values, True, start,
                   {"prior": "uniform_grid_in_first_feasible_region",
                    "radius_prior": "samples_supplied_by_context",
                    "outcomes": ["bearing_bin", "no_signal", "near"]})


def select_all(ctx, names=None):
    funcs = {
        "random": select_random,
        "geometry": select_geometry,
        "gdop_mean": select_gdop_mean,
        "gdop_worst": select_gdop_worst,
        "fim_a": lambda c: select_fim(c, "a"),
        "fim_d": lambda c: select_fim(c, "d"),
        "fim_e": lambda c: select_fim(c, "e"),
        "eig": select_eig,
    }
    names = list(funcs) if names is None else names
    return {name: funcs[name](ctx) for name in names}
