"""Physical constants and numerical configuration."""
from dataclasses import dataclass


@dataclass(frozen=True)
class PhysicalConfig:
    target_radius: float = 1800.0
    bearing_error_deg: float = 1.0
    reception_min: float = 1000.0
    reception_max: float = 1500.0
    near_radius: float = 5.0
    clear_radius: float = 20.0
    speed: float = 5.0


@dataclass(frozen=True)
class SearchConfig:
    grid_step: float = 250.0
    refine_steps: tuple[float, ...] = (100.0, 50.0)
    refine_top_k: int = 3
    refine_radius_factor: float = 1.25
    polygon_resolution: int = 64
    posterior_grid_step: float = 80.0
    posterior_samples: int = 80
    posterior_sampling: str = 'random'
    radius_prior: str = 'conditional_uniform'
    candidate_domain: str = 'target_disk'
    pruning_mode: str = 'reachable_only'
    min_detection_probability: float = 0.0
    min_median_abs_sin_angle: float = 0.0
    shortlist_size: int = 10
    objective_target_samples: int = 80
    objective_error_samples: int = 5
    objective_error_model: str = 'uniform'
    coarse_to_fine: bool = True
    observable_update: bool = True
    eig_bearing_bin_deg: float = 2.0
