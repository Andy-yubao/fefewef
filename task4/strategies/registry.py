from __future__ import annotations

from collections.abc import Callable

from .active import ActiveStrategy
from .base import BaseStrategy
from .coverage import CoverageStrategy
from .clear_probe import ClearProbeStrategy
from .deferred import DeferredCoverageStrategy
from .early_stop import EarlyStopStrategy
from .belief import BeliefSearchStrategy
from .lattice import LatticeDeferredStrategy
from .local_eig import LocalEIGStrategy
from .integrated_route import IntegratedRouteStrategy
from .opportunistic import OpportunisticClearStrategy
from .reacquire import ReacquireStrategy
from .route_optimized import RouteOptimizedStrategy
from .rejoin_clear import RejoinClearStrategy


STRATEGIES: dict[str, Callable[..., BaseStrategy]] = {
    "coverage": CoverageStrategy,
    "active": ActiveStrategy,
    "reacquire": ReacquireStrategy,
    "deferred": DeferredCoverageStrategy,
    "lattice": LatticeDeferredStrategy,
    "opportunistic": OpportunisticClearStrategy,
    "belief": BeliefSearchStrategy,
    "route_optimized": RouteOptimizedStrategy,
    "local_eig": LocalEIGStrategy,
    "rejoin_clear": RejoinClearStrategy,
    "early_stop": EarlyStopStrategy,
    "integrated_route": IntegratedRouteStrategy,
    "clear_probe": ClearProbeStrategy,
}


def make_strategy(name: str, **kwargs) -> BaseStrategy:
    try:
        strategy_class = STRATEGIES[name]
    except KeyError as exc:
        choices = ", ".join(STRATEGIES)
        raise ValueError(f"unknown strategy {name!r}; choose from {choices}") from exc
    return strategy_class(**kwargs)
