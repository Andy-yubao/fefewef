import math
import numpy as np
from shapely.geometry import Point

from src.config import PhysicalConfig, SearchConfig
from src.geometry.regions import first_feasible_region
from src.localization.observation import observe
from src.localization.update import update_region_from_observation
from src.strategies.selectors import StrategyContext, _hypothetical_update

CFG = PhysicalConfig()


def first_case():
    s1 = np.array([0.0, 0.0])
    target = np.array([800.0, 0.0])
    return s1, target, first_feasible_region(s1, 0.0, CFG, resolution=64)


def test_no_signal_removes_only_guaranteed_1000m_disk():
    _, _, f1 = first_case()
    s2, obs = np.array([0.0, 500.0]), {"kind": "no_signal"}
    a = update_region_from_observation(f1, s2, obs, CFG, hidden_radius=1490.0)
    b = update_region_from_observation(f1, s2, obs, CFG, hidden_radius=1100.0)
    assert a.region.equals_exact(b.region, 1e-8)
    assert not a.region.covers(Point(800.0, 0.0))
    assert a.region.covers(Point(1200.0, 0.0))


def test_bearing_update_does_not_use_hidden_radius():
    _, _, f1 = first_case()
    s2 = np.array([800.0, -600.0])
    obs = {"kind": "bearing", "bearing": math.pi / 2}
    a = update_region_from_observation(f1, s2, obs, CFG, hidden_radius=1000.0)
    b = update_region_from_observation(f1, s2, obs, CFG, hidden_radius=1500.0)
    assert a.region.equals_exact(b.region, 1e-8)


def test_near_has_zero_q2_localization_diameter():
    _, _, f1 = first_case()
    result = update_region_from_observation(
        f1, np.array([800.0, 0.0]), {"kind": "near"}, CFG)
    assert result.region is None and result.area == 0.0 and result.diameter == 0.0


def test_truth_containment_for_bearing_and_no_signal():
    _, target, f1 = first_case()
    cases = [(np.array([800.0, -600.0]), 1250.0, math.radians(0.7)),
             (np.array([-500.0, 600.0]), 1000.0, math.radians(-0.4))]
    for s2, radius, error in cases:
        obs = observe(s2, target, radius, error, CFG.near_radius)
        update = update_region_from_observation(f1, s2, obs, CFG)
        assert obs["kind"] != "near" and update.region.covers(Point(*target))


def test_planner_and_evaluator_share_update_semantics():
    s1, target, f1 = first_case()
    s2 = np.array([800.0, -600.0])
    search = SearchConfig(polygon_resolution=48, coarse_to_fine=False)
    ctx = StrategyContext(s1, 0.0, f1, np.array([target]),
                          np.array([1250.0]), CFG, search, 3)
    error = math.radians(0.3)
    planned = _hypothetical_update(ctx, s2, target, 1250.0, error)
    obs = observe(s2, target, 1250.0, error, CFG.near_radius)
    evaluated = update_region_from_observation(f1, s2, obs, CFG, 48)
    assert planned.outcome == evaluated.outcome
    assert planned.diameter == evaluated.diameter
    assert planned.area == evaluated.area
