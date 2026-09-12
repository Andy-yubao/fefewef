from __future__ import annotations

from dataclasses import dataclass, field
import time

from task4.client import RobotAPI
from task4.geometry import Point, feasible_polygon


@dataclass
class ChannelBelief:
    channel: int
    status: str = "unseen"  # unseen, active, located, cleared
    observations: list[tuple[Point, float]] = field(default_factory=list)
    no_signal_positions: list[Point] = field(default_factory=list)
    attempted_positions: list[Point] = field(default_factory=list)
    first_seen_virtual_s: float | None = None
    clear_target: Point | None = None

    def polygon(self) -> list[Point]:
        return feasible_polygon(self.observations)


@dataclass
class StrategyResult:
    strategy: str
    cleared_channels: list[int]
    seen_channels: list[int]
    first_seen_virtual_s: dict[int, float]
    final_virtual_time_s: float
    action_count: int
    wall_time_s: float
    diagnostics: dict[str, object] = field(default_factory=dict)


class BaseStrategy:
    """Shared state and official-API action handling for all strategies."""

    name = "base"

    def __init__(self, grid_spacing: float = 600.0, grid_half_extent: float = 1800.0):
        self.grid_spacing = grid_spacing
        self.grid_half_extent = grid_half_extent
        self.position: Point = (0.0, 0.0)
        self.virtual_time_s = 0.0
        self.receiver_channel = 1
        self.beliefs = {channel: ChannelBelief(channel) for channel in range(1, 21)}

    def _measure(self, api: RobotAPI, position: Point, channel: int) -> dict:
        response = api.measure(position, channel)
        self.position = position
        self.virtual_time_s = float(response["virtual_time_s"])
        self.receiver_channel = channel
        belief = self.beliefs[channel]
        result = response["measure_result"]
        if result == "direction":
            belief.observations.append((position, float(response["svd_deg"])))
            if belief.status == "unseen":
                belief.status = "active"
                belief.first_seen_virtual_s = self.virtual_time_s
        elif result == "near":
            if belief.status == "unseen":
                belief.status = "active"
                belief.first_seen_virtual_s = self.virtual_time_s
        else:
            belief.no_signal_positions.append(position)
        return response

    def _channel_scan_order(self, excluded_statuses: set[str]) -> list[int]:
        channels = [
            channel
            for channel, belief in self.beliefs.items()
            if belief.status not in excluded_statuses
        ]
        if not channels:
            return channels
        if self.receiver_channel in channels:
            channels.remove(self.receiver_channel)
            reverse = self.receiver_channel >= (min(channels, default=10) + max(channels, default=10)) / 2
            return [self.receiver_channel] + sorted(channels, reverse=reverse)
        reverse = abs(self.receiver_channel - max(channels)) < abs(self.receiver_channel - min(channels))
        return sorted(channels, reverse=reverse)

    def _clear(self, api: RobotAPI, position: Point, channel: int) -> bool:
        response = api.clear(position, channel)
        self.position = position
        self.virtual_time_s = float(response["virtual_time_s"])
        if response["clear_result"] == "success":
            self.beliefs[channel].status = "cleared"
            return True
        return False

    def _finish(self, api: RobotAPI, started: float) -> StrategyResult:
        exit_response = api.exit()
        self.virtual_time_s = float(exit_response["virtual_time_s"])
        return StrategyResult(
            strategy=self.name,
            cleared_channels=[channel for channel, belief in self.beliefs.items() if belief.status == "cleared"],
            seen_channels=[channel for channel, belief in self.beliefs.items() if belief.first_seen_virtual_s is not None],
            first_seen_virtual_s={
                channel: belief.first_seen_virtual_s
                for channel, belief in self.beliefs.items()
                if belief.first_seen_virtual_s is not None
            },
            final_virtual_time_s=self.virtual_time_s,
            action_count=len(getattr(api, "actions", [])),
            wall_time_s=time.perf_counter() - started,
        )

    def run(self, api: RobotAPI) -> StrategyResult:
        raise NotImplementedError
