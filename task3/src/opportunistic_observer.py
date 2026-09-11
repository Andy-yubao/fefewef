"""Zero-detour observations that never replace the committed ACTIVE task."""

from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .channel_state import ChannelState
from .config import PhysicalConfig, PlannerConfig
from .opportunity_planner import EmbeddedEvent, OpportunityPlanner
from .route_planner import RouteLeg


@dataclass
class OpportunisticObserver:
    physical: PhysicalConfig = PhysicalConfig()
    planner: PlannerConfig = PlannerConfig()

    def __post_init__(self) -> None:
        self._planner = OpportunityPlanner(self.physical, self.planner)

    def events(
        self,
        start: np.ndarray,
        end: np.ndarray,
        channels: dict[int, ChannelState],
        active_channel: int | None,
        attempted: set[tuple] | None = None,
    ) -> list[EmbeddedEvent]:
        eligible = {
            channel: state for channel, state in channels.items()
            if channel != active_channel
            and state.bearing_count < self.planner.max_bearings_before_fallback
        }
        leg = RouteLeg(np.asarray(start, float), np.asarray(end, float), "active_task", -1)
        return self._planner.events(leg, eligible, attempted)
