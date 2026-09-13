"""Deterministic offline simulator matching problem-3 timing and observations."""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import math
import time
from typing import Any

import numpy as np

from .config import PhysicalConfig


@dataclass(frozen=True)
class Source:
    channel: int
    position: tuple[float, float]
    reception_radius_m: float


@dataclass(frozen=True)
class Scenario:
    scenario_id: str
    seed: int
    sources: tuple[Source, ...]

    @property
    def total(self) -> int:
        return len(self.sources)


def random_scenario(
    seed: int,
    physical: PhysicalConfig = PhysicalConfig(),
    source_count: int | None = None,
) -> Scenario:
    rng = np.random.default_rng(seed)
    if source_count is None:
        total = int(rng.integers(physical.min_sources, physical.max_sources + 1))
    else:
        total = int(source_count)
        if not physical.min_sources <= total <= physical.max_sources:
            raise ValueError(
                f"source_count must be in [{physical.min_sources}, {physical.max_sources}]"
            )
    channels = np.sort(rng.choice(np.arange(1, physical.channels + 1), total, replace=False))
    radii = physical.target_radius_m * np.sqrt(rng.random(total))
    angles = rng.uniform(0.0, 2.0 * math.pi, total)
    receive = rng.uniform(physical.reception_min_m, physical.reception_max_m, total)
    sources = tuple(Source(int(c), (float(r * math.cos(a)), float(r * math.sin(a))), float(rr))
                    for c, r, a, rr in zip(channels, radii, angles, receive))
    return Scenario(f"offline-{seed:08d}", seed, sources)


class MockSimulator:
    def __init__(self, scenario: Scenario, physical: PhysicalConfig = PhysicalConfig(),
                 fixed_error: bool = True):
        self.scenario = scenario
        self.physical = physical
        self.fixed_error = fixed_error
        self.position = (0.0, 0.0)
        self.current_channel = 1
        self.last_virtual_time_s = 0.0
        self.cleared: set[int] = set()
        self.entered = False
        self.exited = False
        self.actions: list[dict[str, Any]] = []
        self._wall_start: float | None = None

    def _source(self, channel: int) -> Source | None:
        return next((s for s in self.scenario.sources if s.channel == channel), None)

    def _error_deg(self, channel: int, position: tuple[float, float]) -> float:
        # Quantized physical location makes repeated measurements return the
        # same environmental error; different locations follow a bounded law.
        key = f"{self.scenario.seed}:{channel}:{position[0]:.6f}:{position[1]:.6f}".encode()
        value = int.from_bytes(hashlib.sha256(key).digest()[:8], "big") / 2**64
        # Leave half a display unit for the simulator's two-decimal rounding,
        # so the returned bearing still satisfies the official +/-1 degree bound.
        return 1.99 * value - 0.995

    def _move(self, position: tuple[float, float]) -> float:
        distance = math.dist(self.position, position)
        self.position = position
        movement = distance / self.physical.speed_mps
        self.last_virtual_time_s += movement
        return movement

    def _response(self, **extra: Any) -> dict[str, Any]:
        return {"accepted": True, "real_timestamp_ms": int(time.time() * 1000),
                "virtual_time_s": self.last_virtual_time_s, **extra}

    def enter(self) -> dict[str, Any]:
        if self.entered:
            raise RuntimeError("duplicate enter")
        self.entered = True
        self._wall_start = time.monotonic()
        response = self._response(max_virtual_duration_s=360000, max_real_duration_s=1200,
                                  remaining_real_duration_s=1200)
        self.actions.append({"path": "/enter", "response": response})
        return response

    def measure(self, position: tuple[float, float] | list[float], channel: int) -> dict[str, Any]:
        p = (float(position[0]), float(position[1]))
        movement = self._move(p)
        switched = channel != self.current_channel
        if switched:
            self.last_virtual_time_s += self.physical.switch_s
        self.current_channel = channel
        self.last_virtual_time_s += self.physical.measure_s
        source = self._source(channel)
        if source is None or channel in self.cleared:
            response = self._response(measure_result="no_signal")
        else:
            distance = math.dist(p, source.position)
            if distance > source.reception_radius_m:
                response = self._response(measure_result="no_signal")
            elif distance <= self.physical.near_radius_m:
                response = self._response(measure_result="near")
            else:
                true = math.degrees(math.atan2(source.position[1] - p[1], source.position[0] - p[0])) % 360.0
                error = self._error_deg(channel, p)
                response = self._response(measure_result="direction", svd_deg=round((true + error) % 360.0, 2))
        self.actions.append({"path": "/measure", "position": p, "channel": channel,
                             "movement_s": movement, "switched": switched, "response": response})
        return response

    def clear(self, position: tuple[float, float] | list[float], channel: int) -> dict[str, Any]:
        p = (float(position[0]), float(position[1]))
        movement = self._move(p)
        source = self._source(channel)
        success = (source is not None and channel not in self.cleared
                   and math.dist(p, source.position) <= self.physical.clear_radius_m + 1e-9)
        self.last_virtual_time_s += self.physical.optical_s
        if success:
            self.last_virtual_time_s += self.physical.laser_s
            self.cleared.add(channel)
        response = self._response(clear_result="success" if success else "no_target_in_range")
        self.actions.append({"path": "/clear", "position": p, "channel": channel,
                             "movement_s": movement, "response": response})
        return response

    def exit(self) -> dict[str, Any]:
        self.exited = True
        response = self._response(exit_reason="user_exit")
        self.actions.append({"path": "/exit", "response": response})
        return response

    def real_time_left_s(self) -> float:
        return 1200.0 if self._wall_start is None else 1200.0 - (time.monotonic() - self._wall_start)
