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
    polygon_resolution: int = 64
    posterior_grid_step: float = 80.0
    min_detection_probability: float = 0.25
    min_median_abs_sin_angle: float = 0.12
    shortlist_size: int = 6
    objective_target_samples: int = 10
    objective_error_samples: int = 3
    eig_bearing_bin_deg: float = 2.0

