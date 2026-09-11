"""Configuration shared by the HTTP controller and offline simulator."""

from __future__ import annotations

from dataclasses import asdict, dataclass


@dataclass(frozen=True)
class PhysicalConfig:
    target_radius_m: float = 1800.0
    reception_min_m: float = 1000.0
    reception_max_m: float = 1500.0
    bearing_error_deg: float = 1.0
    near_radius_m: float = 5.0
    clear_radius_m: float = 20.0
    speed_mps: float = 5.0
    measure_s: float = 5.0
    switch_s: float = 1.0
    optical_s: float = 3.0
    laser_s: float = 2.0
    max_sources: int = 16
    min_sources: int = 10
    channels: int = 20


@dataclass(frozen=True)
class PlannerConfig:
    ring_radius_m: float = 1200.0
    grid_step_m: float = 20.0
    numeric_distance_tol_m: float = 1e-7
    numeric_angle_tol_deg: float = 1e-6
    clear_margin_m: float = 0.25
    local_action_limit: int = 3
    max_bearings_before_fallback: int = 6
    local_offset_m: float = 500.0
    candidate_ring_count: int = 12
    particle_count: int = 80
    tail_weight: float = 0.20
    risk_quantile: float = 0.90
    route_insert_limit_m: float = 300.0
    rotation_deg: float = 0.0
    seed: int = 20260911
    real_time_reserve_s: float = 10.0
    max_actions: int = 30_000


@dataclass(frozen=True)
class ClientConfig:
    base_url: str = "http://127.0.0.1:2026"
    arena_id: str = "default"
    robot_id: str = ""
    timeout_s: float = 5.0
    retries: int = 3
    retry_backoff_s: float = 0.20


def config_dict(*configs: object) -> dict:
    result: dict = {}
    for cfg in configs:
        result[type(cfg).__name__] = asdict(cfg)
    return result
