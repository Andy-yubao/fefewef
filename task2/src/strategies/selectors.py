"""Second detection point selection strategies.

This module contains optimization only. Dataset generation, Monte Carlo loops,
statistics, and plotting deliberately live under task2/experiments.
"""
from __future__ import annotations

from dataclasses import dataclass, field
import math
import time

import numpy as np
from shapely.geometry import Point

from ..config import PhysicalConfig, SearchConfig
from ..geometry.angles import bearing, intersection_angle
from ..geometry.regions import (candidate_regions, disk, localization_region,
                                region_area_diameter)
from ..localization.metrics import (bearing_fim, bounded_linearized_diameter,
                                    covariance_metrics)
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


def _pool(ctx):
    c = candidate_regions(
        ctx.sensor1, ctx.posterior_points, ctx.physical,
        step=ctx.search.grid_step, radius_samples=ctx.radius_samples,
        min_detection_probability=ctx.search.min_detection_probability,
        min_median_abs_sin_angle=ctx.search.min_median_abs_sin_angle,
    )
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


def select_geometry(ctx):
    start = time.perf_counter()
    c, idx = _pool(ctx)
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
    return _finish("geometry", grid, idx, scores, True, start)


def _fim_surface(ctx, criterion, worst=False):
    c, idx = _pool(ctx)
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
    return c, idx, values, not minimize


def select_gdop_mean(ctx):
    start = time.perf_counter()
    c, idx, values, maximize = _fim_surface(ctx, "gdop", False)
    return _finish("gdop_mean", c["points"], idx, values, maximize, start)


def select_gdop_worst(ctx):
    start = time.perf_counter()
    c, idx, values, maximize = _fim_surface(ctx, "gdop", True)
    return _finish("gdop_worst", c["points"], idx, values, maximize, start)


def select_fim(ctx, criterion):
    start = time.perf_counter()
    c, idx, values, maximize = _fim_surface(ctx, criterion, False)
    label = {"a": "fim_a", "d": "fim_d", "e": "fim_e"}[criterion]
    return _finish(label, c["points"], idx, values, maximize, start,
                   {"gaussian_approximation": True})


def _hypothetical_region(ctx, s2, target, radius, error2):
    cfg = ctx.physical
    outcome = observe(s2, target, radius, error2, cfg.near_radius)
    if outcome["kind"] == "near":
        return ctx.first_region.intersection(
            disk(s2, cfg.near_radius, ctx.search.polygon_resolution))
    if outcome["kind"] == "no_signal":
        # Conditional on a sampled radius. The outer experiment also measures
        # performance when radius is unknown/misspecified.
        return ctx.first_region.difference(
            disk(s2, radius, ctx.search.polygon_resolution))
    return localization_region(
        [ctx.sensor1, s2], [ctx.bearing1, outcome["bearing"]], cfg,
        [cfg.reception_max, radius], ctx.search.polygon_resolution,
    )


def _diameter_surface(ctx, minimax=False):
    c, idx = _pool(ctx)
    grid, targets = c["points"], ctx.posterior_points
    # Proxy is evaluated everywhere, then true set-membership diameter on a
    # shortlist. This is a computational search device, not the final metric.
    proxy = np.full(len(grid), np.inf)
    first_diam = region_area_diameter(ctx.first_region)[1]
    for i in idx:
        ds = []
        for g, r in zip(targets, ctx.radius_samples):
            if np.linalg.norm(g - grid[i]) > r:
                ds.append(first_diam)
            else:
                ds.append(min(first_diam, bounded_linearized_diameter(
                    [ctx.sensor1, grid[i]], g,
                    math.radians(ctx.physical.bearing_error_deg))))
        proxy[i] = max(ds) if minimax else float(np.mean(ds))
    shortlist = idx[np.argsort(proxy[idx])[:min(ctx.search.shortlist_size, len(idx))]]
    rng = np.random.default_rng(ctx.seed + (8101 if minimax else 7103))
    n = min(ctx.search.objective_target_samples, len(targets))
    take = rng.choice(len(targets), n, replace=False)
    errors = np.linspace(-1.0, 1.0, ctx.search.objective_error_samples) * math.radians(
        ctx.physical.bearing_error_deg)
    exact = proxy.copy()
    exact_details = {}
    for i in shortlist:
        ds = []
        for j in take:
            for e in errors:
                reg = _hypothetical_region(ctx, grid[i], targets[j],
                                           ctx.radius_samples[j], e)
                ds.append(region_area_diameter(reg)[1])
        exact[i] = max(ds) if minimax else float(np.mean(ds))
        exact_details[int(i)] = ds
    return c, idx, exact, shortlist, exact_details


def select_expected_diameter(ctx):
    start = time.perf_counter()
    c, idx, values, shortlist, details = _diameter_surface(ctx, False)
    return _finish("expected_diameter", c["points"], shortlist, values, False,
                   start, {"base_candidate_count": len(idx),
                           "exact_shortlist_indices": shortlist.tolist()})


def select_minimax_diameter(ctx):
    start = time.perf_counter()
    c, idx, values, shortlist, details = _diameter_surface(ctx, True)
    return _finish("minimax_diameter", c["points"], shortlist, values, False,
                   start, {"base_candidate_count": len(idx),
                           "exact_shortlist_indices": shortlist.tolist()})


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
