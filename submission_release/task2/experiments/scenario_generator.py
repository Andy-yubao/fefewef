"""Random valid scenarios; not imported by the modeling package."""
from __future__ import annotations

import math
import numpy as np

from src.config import PhysicalConfig
from src.geometry.angles import bearing


RADIUS_MODES = ("fixed_1000", "fixed_1250", "fixed_1500", "random")
ERROR_MODELS = ("uniform", "truncated_gaussian", "worst_bounded")


def sample_error(rng, model, bound_rad):
    if model == "uniform":
        return float(rng.uniform(-bound_rad, bound_rad))
    if model == "truncated_gaussian":
        while True:
            x = float(rng.normal(0.0, bound_rad / 2.0))
            if abs(x) <= bound_rad:
                return x
    if model == "worst_bounded":
        return float(bound_rad if rng.random() < 0.5 else -bound_rad)
    raise ValueError(model)


def sample_radius(rng, mode, cfg):
    if mode == "fixed_1000": return 1000.0
    if mode == "fixed_1250": return 1250.0
    if mode == "fixed_1500": return 1500.0
    if mode == "random": return float(rng.uniform(cfg.reception_min, cfg.reception_max))
    raise ValueError(mode)


def uniform_disk(rng, radius):
    a = rng.uniform(0.0, 2.0 * math.pi)
    r = radius * math.sqrt(rng.random())
    return np.array([r * math.cos(a), r * math.sin(a)])


def generate_base_scenarios(n, seed=20260911, cfg=PhysicalConfig()):
    rng = np.random.default_rng(seed)
    out = []
    bound = math.radians(cfg.bearing_error_deg)
    combos = [(r, e) for r in RADIUS_MODES for e in ERROR_MODELS]
    for i in range(n):
        radius_mode, error_model = combos[i % len(combos)]
        radius = sample_radius(rng, radius_mode, cfg)
        # Rejection enforces: G and S1 in target disk, 5 < |G-S1| <= R.
        for _ in range(10000):
            g = uniform_disk(rng, cfg.target_radius)
            distance = rng.uniform(80.0, radius)
            theta = rng.uniform(0.0, 2.0 * math.pi)
            s1 = g - distance * np.array([math.cos(theta), math.sin(theta)])
            if np.linalg.norm(s1) <= cfg.target_radius:
                break
        e1 = sample_error(rng, error_model, bound)
        y1 = float((bearing(s1, g) + e1) % (2.0 * math.pi))
        out.append({"scenario_id": i, "target_x": g[0], "target_y": g[1],
                    "s1_x": s1[0], "s1_y": s1[1], "radius": radius,
                    "radius_mode": radius_mode, "error_model": error_model,
                    "error1_rad": e1, "bearing1_rad": y1})
    return out

