import numpy as np


def test_monte_carlo_mean_stabilizes_with_sample_size():
    rng = np.random.default_rng(20260911)
    # Known bounded-error statistic: E|U|=0.5 for U~Uniform[-1,1].
    x = np.abs(rng.uniform(-1, 1, 100_000))
    err_1k = abs(np.mean(x[:1_000]) - 0.5)
    err_100k = abs(np.mean(x) - 0.5)
    assert err_100k < 0.004
    assert err_100k < err_1k

