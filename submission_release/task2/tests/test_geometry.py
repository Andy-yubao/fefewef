import math
import numpy as np
import pytest

from src.config import PhysicalConfig
from src.geometry.regions import (candidate_regions, disk, first_feasible_region,
                                  localization_region, region_area_diameter,
                                  sample_region_random)


CFG = PhysicalConfig()


def test_orthogonal_is_much_better_than_nearly_parallel():
    target = np.array([500.0, 500.0])
    s1 = np.array([0.0, 500.0])
    orth = np.array([500.0, 0.0])
    parallel = np.array([0.0, 490.0])
    a1 = math.atan2(0.0, 500.0)
    ro = localization_region([s1, orth], [a1, math.pi / 2], CFG)
    rp = localization_region([s1, parallel],
                             [a1, math.atan2(10.0, 500.0)], CFG)
    assert region_area_diameter(ro)[1] < 0.35 * region_area_diameter(rp)[1]


def test_left_right_symmetry_of_candidate_diagnostics():
    s1 = np.array([0.0, 0.0])
    targets = np.array([[600.0, y] for y in (-40, -20, 0, 20, 40)])
    c = candidate_regions(s1, targets, CFG, step=200,
                          radius_samples=np.full(len(targets), 1250.0))
    lookup = {tuple(p): i for i, p in enumerate(c["points"])}
    checked = 0
    for i, (x, y) in enumerate(c["points"]):
        j = lookup.get((x, -y))
        if j is not None:
            assert c["detection_probability"][i] == pytest.approx(
                c["detection_probability"][j])
            assert c["median_abs_sin_angle"][i] == pytest.approx(
                c["median_abs_sin_angle"][j])
            checked += 1
    assert checked > 10


def test_target_and_reception_boundaries_are_respected():
    s1 = np.array([1700.0, 0.0])
    reg = first_feasible_region(s1, math.pi, CFG, reception_radius=1000)
    assert not reg.is_empty
    xmin, ymin, xmax, ymax = reg.bounds
    assert xmax <= CFG.target_radius + 1e-6
    assert xmin >= 700.0 - 1e-6
    assert not reg.covers(disk(s1, CFG.near_radius - 0.1).centroid)


def test_random_region_sampling_handles_narrow_sector():
    reg = first_feasible_region(np.array([0.0, 0.0]), 0.0, CFG)
    pts = sample_region_random(reg, 100, np.random.default_rng(3))
    assert pts.shape == (100, 2)
    assert all(reg.covers(__import__("shapely").geometry.Point(*p)) for p in pts)


def test_polygon_resolution_converges():
    s = [np.array([0.0, 0.0]), np.array([600.0, -600.0])]
    a = [0.0, math.pi / 4]
    ds = [region_area_diameter(localization_region(s, a, CFG, resolution=n))[1]
          for n in (24, 48, 96)]
    assert abs(ds[2] - ds[1]) / ds[2] < 0.02

