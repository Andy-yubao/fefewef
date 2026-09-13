"""Single source of truth for the Q2 hard-bound observation update."""
from __future__ import annotations

from dataclasses import dataclass
import math

from ..config import PhysicalConfig
from ..geometry.regions import bearing_sector, disk, region_area_diameter


@dataclass(frozen=True)
class UpdateResult:
    outcome: str
    region: object | None
    area: float
    diameter: float


def update_region_from_observation(first_region, sensor2, observation,
                                   cfg=PhysicalConfig(), resolution=64,
                                   *, observable_information=True,
                                   hidden_radius=None):
    """Apply a second outcome using only information available to the robot.

    ``hidden_radius`` exists solely for the explicitly labelled legacy ablation.
    The formal model uses the guaranteed 1000 m exclusion for no signal and the
    conservative 1500 m range cap for a bearing. Near triggers optical
    localization, so its Q2 area and diameter are zero.
    """
    kind = observation["kind"]
    if kind == "near":
        return UpdateResult(kind, None, 0.0, 0.0)
    if kind == "no_signal":
        radius = (float(hidden_radius) if not observable_information
                  else cfg.reception_min)
        region = first_region.difference(disk(sensor2, radius, resolution)).buffer(0)
    elif kind == "bearing":
        radius = (float(hidden_radius) if not observable_information
                  else cfg.reception_max)
        sector = bearing_sector(sensor2, observation["bearing"],
                                math.radians(cfg.bearing_error_deg), radius,
                                cfg.near_radius, resolution // 2)
        region = first_region.intersection(sector).buffer(0)
    else:
        raise ValueError(f"unknown observation kind: {kind}")
    area, diameter = region_area_diameter(region)
    return UpdateResult(kind, region, area, diameter)
