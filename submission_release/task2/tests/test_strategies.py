import numpy as np

from src.config import PhysicalConfig, SearchConfig
from src.geometry.regions import first_feasible_region, sample_region_random
from src.strategies.selectors import StrategyContext, select_all, select_geometry


def context(step, n=80):
    cfg = PhysicalConfig()
    s1 = np.array([0.0, 0.0])
    reg = first_feasible_region(s1, 0.0, cfg)
    pts = sample_region_random(reg, n, np.random.default_rng(17))
    return StrategyContext(s1, 0.0, reg, pts, np.full(n, 1250.0), cfg,
                           SearchConfig(grid_step=step, polygon_resolution=40,
                                        shortlist_size=3,
                                        objective_target_samples=5,
                                        coarse_to_fine=False), 17)


def test_nested_grid_search_objective_converges():
    vals = [select_geometry(context(step)).objective for step in (400, 200, 100)]
    assert vals[1] >= vals[0] - 1e-12
    assert vals[2] >= vals[1] - 1e-12
    assert (vals[2] - vals[1]) / vals[2] < 0.08


def test_every_required_strategy_returns_a_finite_candidate():
    results = select_all(context(400, 32))
    assert set(results) == {"random", "geometry", "gdop_mean", "gdop_worst",
                            "fim_a", "fim_d", "fim_e", "eig"}
    for result in results.values():
        assert np.all(np.isfinite(result.point))
        assert result.candidate_count > 0
