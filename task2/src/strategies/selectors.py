"""Second detection point selection strategies.

This module contains optimization only. Dataset generation, Monte Carlo loops,
statistics, and plotting deliberately live under task2/experiments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import time

import numpy as np
from scipy.stats import truncnorm

from ..config import PhysicalConfig, SearchConfig
from ..geometry.angles import bearing, intersection_angle
from ..geometry.regions import (candidate_diagnostics, candidate_regions,
                                region_area_diameter)
from ..localization.metrics import (bearing_fim, bounded_linearized_diameter,
                                    covariance_metrics)
from ..localization.observation import observe
from ..localization.update import update_region_from_observation


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


def _error_quadrature(ctx):
    """Deterministic bounded-error nodes and weights for action comparison."""
    n = max(1, ctx.search.objective_error_samples)
    bound = math.radians(ctx.physical.bearing_error_deg)
    model = ctx.search.objective_error_model
    if model == "uniform":
        nodes = np.linspace(-1 + 1 / n, 1 - 1 / n, n) * bound
    elif model == "truncated_gaussian":
        q = (np.arange(n) + 0.5) / n
        nodes = truncnorm.ppf(q, -2.0, 2.0, loc=0.0, scale=bound / 2.0)
    elif model in ("endpoint", "worst_bounded"):
        nodes = np.array([-bound, bound]) if n > 1 else np.array([bound])
    else:
        raise ValueError(f"unknown objective error model: {model}")
    return np.asarray(nodes, float), np.full(len(nodes), 1.0 / len(nodes))


def _hypothetical_update(ctx, s2, target, radius, error2):
    outcome = observe(s2, target, radius, error2, ctx.physical.near_radius)
    return update_region_from_observation(
        ctx.first_region, s2, outcome, ctx.physical,
        ctx.search.polygon_resolution,
        observable_information=ctx.search.observable_update,
        hidden_radius=radius)


def _proxy_surface(ctx, grid, idx, minimax):
    values = np.full(len(grid), np.inf)
    first_diam = region_area_diameter(ctx.first_region)[1]
    half_width = math.radians(ctx.physical.bearing_error_deg)
    for i in idx:
        no_signal = update_region_from_observation(
            ctx.first_region, grid[i], {"kind": "no_signal"}, ctx.physical,
            ctx.search.polygon_resolution,
            observable_information=ctx.search.observable_update,
            hidden_radius=float(np.mean(ctx.radius_samples))).diameter
        ds = []
        for g, r in zip(ctx.posterior_points, ctx.radius_samples):
            distance = np.linalg.norm(g - grid[i])
            if distance <= ctx.physical.near_radius:
                ds.append(0.0)
            elif distance > r:
                ds.append(no_signal)
            else:
                ds.append(min(first_diam, bounded_linearized_diameter(
                    [ctx.sensor1, grid[i]], g, half_width)))
        values[i] = max(ds) if minimax else float(np.mean(ds))
    return values


def _exact_surface(ctx, grid, shortlist, target_indices, errors, weights,
                   minimax):
    values = np.full(len(grid), np.inf)
    for i in shortlist:
        ds, ws = [], []
        for j in target_indices:
            for e, w in zip(errors, weights):
                update = _hypothetical_update(
                    ctx, grid[i], ctx.posterior_points[j],
                    ctx.radius_samples[j], e)
                ds.append(update.diameter)
                ws.append(w)
        values[i] = max(ds) if minimax else float(np.average(ds, weights=ws))
    return values


def _refinement_points(centres, previous_step, step, factor):
    radius = previous_step * factor
    offsets = np.arange(-radius, radius + 1e-9, step)
    pts = np.array([c + (dx, dy) for c in centres
                    for dx in offsets for dy in offsets], dtype=float)
    return np.unique(np.round(pts, 8), axis=0)


def _diameter_search(ctx, minimax=False):
    rng = np.random.default_rng(ctx.seed + (8101 if minimax else 7103))
    n = min(ctx.search.objective_target_samples, len(ctx.posterior_points))
    target_indices = np.sort(rng.choice(len(ctx.posterior_points), n,
                                        replace=False))
    errors, weights = _error_quadrature(ctx)
    levels, all_points, all_values = [], [], []
    steps = [ctx.search.grid_step]
    if ctx.search.coarse_to_fine:
        steps.extend(ctx.search.refine_steps)
    centres = None
    previous_step = ctx.search.grid_step
    exact_count = 0
    for level, step in enumerate(steps, start=1):
        level_start = time.perf_counter()
        if centres is None:
            candidates, idx = _pool(ctx)
        else:
            points = _refinement_points(
                centres, previous_step, step, ctx.search.refine_radius_factor)
            candidates, idx = _pool(ctx, points)
        grid = candidates["points"]
        proxy = _proxy_surface(ctx, grid, idx, minimax)
        shortlist = idx[np.argsort(proxy[idx])[:min(ctx.search.shortlist_size,
                                                    len(idx))]]
        exact = _exact_surface(ctx, grid, shortlist, target_indices,
                               errors, weights, minimax)
        exact_count += len(shortlist) * len(target_indices) * len(errors)
        order = shortlist[np.argsort(exact[shortlist])]
        centres = grid[order[:min(ctx.search.refine_top_k, len(order))]]
        best = int(order[0])
        levels.append({"level": level, "step_m": float(step),
                       "candidate_count": int(len(idx)),
                       "exact_candidate_count": int(len(shortlist)),
                       "best_x": float(grid[best, 0]),
                       "best_y": float(grid[best, 1]),
                       "best_objective": float(exact[best]),
                       "runtime_s": time.perf_counter() - level_start})
        all_points.extend(grid.tolist())
        all_values.extend(exact.tolist())
        previous_step = step
    final = levels[-1]
    diagnostics = {"grid_points": all_points,
                   "objective_surface": all_values,
                   "maximize": False, "search_levels": levels,
                   "exact_objective_evaluation_count": exact_count,
                   "target_sample_count": len(target_indices),
                   "error_sample_count": len(errors),
                   "observable_information_update": ctx.search.observable_update}
    return np.array([final["best_x"], final["best_y"]]), \
        final["best_objective"], sum(x["candidate_count"] for x in levels), diagnostics


def select_expected_diameter(ctx):
    start = time.perf_counter()
    point, objective, count, diagnostics = _diameter_search(ctx, False)
    return SelectionResult("expected_diameter", point, objective,
                           time.perf_counter() - start, count, diagnostics)


def select_minimax_diameter(ctx):
    start = time.perf_counter()
    point, objective, count, diagnostics = _diameter_search(ctx, True)
    return SelectionResult("minimax_diameter", point, objective,
                           time.perf_counter() - start, count, diagnostics)


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
        "expected_diameter": select_expected_diameter,
        "minimax_diameter": select_minimax_diameter,
        "eig": select_eig,
    }
    names = list(funcs) if names is None else names
    return {name: funcs[name](ctx) for name in names}
