from __future__ import annotations

from collections.abc import Callable

from .active import ActiveStrategy
from .active_clear_probe import ActiveClearProbeStrategy
from .base import BaseStrategy
from .coverage import CoverageStrategy
from .clear_probe import ClearProbeStrategy
from .clear_probe_multistart import ClearProbeMultistartStrategy
from .certified_clear_probe import CertifiedClearProbeStrategy
from .certified_geometry_clear_probe import CertifiedGeometryClearProbeStrategy
from .deferred import DeferredCoverageStrategy
from .early_stop import EarlyStopStrategy
from .endgame_clear_probe import EndgameClearProbeStrategy
from .early_optical_clear_probe import EarlyOpticalClearProbeStrategy
from .belief import BeliefSearchStrategy
from .lattice import LatticeDeferredStrategy
from .local_eig import LocalEIGStrategy
from .integrated_route import IntegratedRouteStrategy
from .ida_heuristic_clear_probe import IDAHeuristicClearProbeStrategy
from .geometry_aware_clear_probe import GeometryAwareClearProbeStrategy
from .geometry_early_optical_clear_probe import GeometryEarlyOpticalClearProbeStrategy
from .opportunistic import OpportunisticClearStrategy
from .optimized_clear_probe import OptimizedClearProbeStrategy
from .reacquire import ReacquireStrategy
from .route_optimized import RouteOptimizedStrategy
from .rejoin_clear import RejoinClearStrategy
from .replacement_aware_clear_probe import ReplacementAwareClearProbeStrategy


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
    "clear_probe_multistart": ClearProbeMultistartStrategy,
    "certified_clear_probe": CertifiedClearProbeStrategy,
    "active_clear_probe": ActiveClearProbeStrategy,
    "endgame_clear_probe": EndgameClearProbeStrategy,
    "optimized_clear_probe": OptimizedClearProbeStrategy,
    "replacement_aware_clear_probe": ReplacementAwareClearProbeStrategy,
    "geometry_aware_clear_probe": GeometryAwareClearProbeStrategy,
    "certified_geometry_clear_probe": CertifiedGeometryClearProbeStrategy,
    "early_optical_clear_probe": EarlyOpticalClearProbeStrategy,
    "ida_heuristic_clear_probe": IDAHeuristicClearProbeStrategy,
    "geometry_early_optical_clear_probe": GeometryEarlyOpticalClearProbeStrategy,
}


def make_strategy(name: str, **kwargs) -> BaseStrategy:
    try:
        strategy_class = STRATEGIES[name]
    except KeyError as exc:
        choices = ", ".join(STRATEGIES)
        raise ValueError(f"unknown strategy {name!r}; choose from {choices}") from exc
    return strategy_class(**kwargs)
