from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import math
import random
import time
import unicodedata
from typing import Any


@dataclass(frozen=True)
class SimulatorConfig:
    seed: int = 0
    robot_id: str = "local-robot"
    min_emitters: int = 10
    max_emitters: int = 16
    directional_probability: float = 0.5
    arena_radius_m: float = 1800.0
    receive_radius_min_m: float = 1000.0
    receive_radius_max_m: float = 1500.0
    speed_mps: float = 5.0
    measure_time_s: float = 5.0
    switch_time_s: float = 1.0
    optical_time_s: float = 3.0
    clear_time_s: float = 2.0
    near_radius_m: float = 5.0
    clear_radius_m: float = 20.0
    max_virtual_duration_s: float = 360000.0
    max_real_duration_s: int = 1200


@dataclass
class Emitter:
    channel: int
    x: float
    y: float
    receive_radius_m: float
    directional: bool
    direction_deg: float | None
    cleared: bool = False


class SimulatorError(ValueError):
    pass


class LocalSimulator:
    """State machine behind the local HTTP evaluator.

    Public action methods expose only official response fields. ``truth_summary`` is
    intentionally separate and is used only by experiment/reporting code after a run.
    """

    def __init__(self, config: SimulatorConfig, emitters: list[Emitter] | None = None):
        self.config = config
        self._rng = random.Random(config.seed)
        self._emitters = emitters if emitters is not None else self._generate_emitters()
        self._by_channel = {e.channel: e for e in self._emitters}
        if len(self._by_channel) != len(self._emitters):
            raise SimulatorError("emitter channels must be unique")
        self.entered = False
        self.exited = False
        self.position = (0.0, 0.0)
        self.channel = 1
        self.virtual_time_s = 0.0
        self._start_monotonic: float | None = None
        self._requests: dict[str, tuple[str, dict[str, Any], dict[str, Any]]] = {}
        self.log: list[dict[str, Any]] = []
        self.stats = {
            "movement_distance_m": 0.0,
            "movement_time_s": 0.0,
            "measure_time_s": 0.0,
            "measure_count": 0,
            "no_signal_count": 0,
            "direction_count": 0,
            "near_count": 0,
            "channel_switch_count": 0,
            "clear_attempt_count": 0,
            "clear_success_count": 0,
            "optical_count": 0,
        }
        self.first_seen_time: dict[int, float] = {}
        self.clear_success_time: dict[int, float] = {}
        self.measurements_before_first_clear: int | None = None
        self.last_signal: dict[int, tuple[float, float]] = {}
        self.directional_loss_count = 0
        self.directional_reacquisition_count = 0
        self._last_detection_signal: dict[int, bool] = {}

    def _generate_emitters(self) -> list[Emitter]:
        n = self._rng.randint(self.config.min_emitters, self.config.max_emitters)
        channels = self._rng.sample(range(1, 21), n)
        result = []
        for channel in channels:
            radius = self.config.arena_radius_m * math.sqrt(self._rng.random())
            angle = self._rng.random() * 2 * math.pi
            directional = self._rng.random() < self.config.directional_probability
            result.append(
                Emitter(
                    channel=channel,
                    x=radius * math.cos(angle),
                    y=radius * math.sin(angle),
                    receive_radius_m=self._rng.uniform(
                        self.config.receive_radius_min_m,
                        self.config.receive_radius_max_m,
                    ),
                    directional=directional,
                    direction_deg=self._rng.uniform(0.0, 360.0) if directional else None,
                )
            )
        return result

    @staticmethod
    def _timestamp_ms() -> int:
        return int(time.time() * 1000)

    def _base(self, accepted: bool, *, rejected: bool = False) -> dict[str, Any]:
        return {
            "accepted": accepted,
            "real_timestamp_ms": self._timestamp_ms(),
            "virtual_time_s": 0 if rejected else round(self.virtual_time_s, 6),
        }

    def _validate_common(self, payload: dict[str, Any], allowed: set[str]) -> bool:
        required = {"arena_id", "robot_id", "request_id"}
        if not required.issubset(payload):
            raise SimulatorError("missing required field")
        if set(payload) - allowed:
            return False
        if not isinstance(payload["arena_id"], str):
            raise SimulatorError("arena_id must be a string")
        if not self._valid_identifier(payload["robot_id"], 64):
            raise SimulatorError("invalid robot_id")
        if not self._valid_identifier(payload["request_id"], 128):
            raise SimulatorError("invalid request_id")
        if payload["arena_id"] != "default" or payload["robot_id"] != self.config.robot_id:
            return False
        return True

    @staticmethod
    def _valid_identifier(value: Any, max_bytes: int) -> bool:
        return (
            isinstance(value, str)
            and 1 <= len(value.encode("utf-8")) <= max_bytes
            and all(unicodedata.category(ch) not in {"Cc", "Cf"} for ch in value)
        )

    def _idempotent(self, path: str, payload: dict[str, Any]) -> dict[str, Any] | None:
        request_id = payload.get("request_id")
        if not isinstance(request_id, str) or request_id not in self._requests:
            return None
        old_path, old_payload, old_response = self._requests[request_id]
        if old_path != path or old_payload != payload:
            raise SimulatorError("request_id conflict")
        return dict(old_response)

    def _record(self, path: str, payload: dict[str, Any], response: dict[str, Any]) -> dict[str, Any]:
        request_id = payload["request_id"]
        self._requests[request_id] = (path, dict(payload), dict(response))
        self.log.append({"path": path, "request": payload, "response": response})
        return response

    def enter(self, payload: dict[str, Any]) -> dict[str, Any]:
        cached = self._idempotent("/enter", payload)
        if cached is not None:
            return cached
        if not self._validate_common(payload, {"arena_id", "robot_id", "request_id"}) or self.entered:
            return self._base(False, rejected=True)
        self.entered = True
        self._start_monotonic = time.monotonic()
        response = self._base(True) | {
            "max_virtual_duration_s": self.config.max_virtual_duration_s,
            "max_real_duration_s": self.config.max_real_duration_s,
            "remaining_real_duration_s": self.config.max_real_duration_s,
        }
        return self._record("/enter", payload, response)

    def _validate_action(self, payload: dict[str, Any]) -> tuple[float, float, int] | None:
        if "position" not in payload or "channel" not in payload:
            raise SimulatorError("missing position or channel")
        if not self._validate_common(
            payload, {"arena_id", "robot_id", "request_id", "position", "channel"}
        ):
            return None
        position = payload.get("position")
        if not isinstance(position, dict) or not {"x", "y"}.issubset(position):
            raise SimulatorError("invalid position object")
        if set(position) - {"x", "y"}:
            return None
        x, y, channel = position.get("x"), position.get("y"), payload.get("channel")
        if isinstance(x, bool) or isinstance(y, bool) or not isinstance(x, (int, float)) or not isinstance(y, (int, float)):
            raise SimulatorError("coordinates must be numbers")
        if not math.isfinite(x) or not math.isfinite(y) or abs(x) > 2_000_000 or abs(y) > 2_000_000:
            raise SimulatorError("coordinate out of range")
        if isinstance(channel, bool) or not isinstance(channel, (int, float)) or not float(channel).is_integer() or not 1 <= int(channel) <= 20:
            raise SimulatorError("channel must be an integer in 1..20")
        return float(x), float(y), int(channel)

    def _ready(self) -> bool:
        real_ok = self._start_monotonic is None or time.monotonic() - self._start_monotonic < self.config.max_real_duration_s
        return self.entered and not self.exited and self.virtual_time_s < self.config.max_virtual_duration_s and real_ok

    def _move(self, x: float, y: float) -> None:
        distance = math.hypot(x - self.position[0], y - self.position[1])
        duration = distance / self.config.speed_mps
        self.stats["movement_distance_m"] += distance
        self.stats["movement_time_s"] += duration
        self.virtual_time_s += duration
        self.position = (x, y)

    @staticmethod
    def _angle_delta_deg(a: float, b: float) -> float:
        return (a - b + 180.0) % 360.0 - 180.0

    def _covered(self, emitter: Emitter, x: float, y: float) -> bool:
        if math.hypot(x - emitter.x, y - emitter.y) > emitter.receive_radius_m + 1e-9:
            return False
        if not emitter.directional:
            return True
        from_source = math.degrees(math.atan2(y - emitter.y, x - emitter.x)) % 360.0
        return abs(self._angle_delta_deg(from_source, float(emitter.direction_deg))) <= 90.0 + 1e-12

    def _bearing_error(self, emitter: Emitter, x: float, y: float) -> float:
        key = f"{self.config.seed}|{emitter.channel}|{x:.9f}|{y:.9f}".encode()
        raw = hashlib.blake2b(key, digest_size=8).digest()
        unit = int.from_bytes(raw, "big") / (2**64 - 1)
        return 2.0 * unit - 1.0

    def measure(self, payload: dict[str, Any]) -> dict[str, Any]:
        cached = self._idempotent("/measure", payload)
        if cached is not None:
            return cached
        action = self._validate_action(payload)
        if action is None or not self._ready():
            return self._base(False, rejected=True)
        x, y, channel = action
        self._move(x, y)
        if channel != self.channel:
            self.virtual_time_s += self.config.switch_time_s
            self.stats["channel_switch_count"] += 1
        self.channel = channel
        self.virtual_time_s += self.config.measure_time_s
        self.stats["measure_time_s"] += self.config.measure_time_s
        self.stats["measure_count"] += 1
        emitter = self._by_channel.get(channel)
        response = self._base(True)
        signal = emitter is not None and not emitter.cleared and self._covered(emitter, x, y)
        if not signal:
            response["measure_result"] = "no_signal"
            self.stats["no_signal_count"] += 1
            if emitter is not None and emitter.directional and not emitter.cleared and self._last_detection_signal.get(channel) is True:
                self.directional_loss_count += 1
        else:
            if channel in self.first_seen_time:
                if emitter is not None and emitter.directional and self._last_detection_signal.get(channel) is False:
                    self.directional_reacquisition_count += 1
            else:
                self.first_seen_time[channel] = self.virtual_time_s
            self.last_signal[channel] = (x, y)
            distance = math.hypot(x - emitter.x, y - emitter.y)
            if distance <= self.config.near_radius_m + 1e-9:
                response["measure_result"] = "near"
                self.stats["near_count"] += 1
            else:
                bearing = math.degrees(math.atan2(emitter.y - y, emitter.x - x)) % 360.0
                response["measure_result"] = "direction"
                self.stats["direction_count"] += 1
                response["svd_deg"] = round((bearing + self._bearing_error(emitter, x, y)) % 360.0, 2)
        if emitter is not None and emitter.directional and not emitter.cleared:
            self._last_detection_signal[channel] = bool(signal)
        return self._record("/measure", payload, response)

    def clear(self, payload: dict[str, Any]) -> dict[str, Any]:
        cached = self._idempotent("/clear", payload)
        if cached is not None:
            return cached
        action = self._validate_action(payload)
        if action is None or not self._ready():
            return self._base(False, rejected=True)
        x, y, channel = action
        self._move(x, y)
        self.stats["clear_attempt_count"] += 1
        self.stats["optical_count"] += 1
        emitter = self._by_channel.get(channel)
        success = emitter is not None and not emitter.cleared and math.hypot(x - emitter.x, y - emitter.y) <= self.config.clear_radius_m + 1e-9
        if success:
            emitter.cleared = True
            self.virtual_time_s += self.config.optical_time_s + self.config.clear_time_s
            self.stats["clear_success_count"] += 1
            self.clear_success_time[channel] = self.virtual_time_s
            if self.measurements_before_first_clear is None:
                self.measurements_before_first_clear = int(self.stats["measure_count"])
            result = "success"
        else:
            self.virtual_time_s += self.config.optical_time_s
            result = "no_target_in_range"
        response = self._base(True) | {"clear_result": result}
        return self._record("/clear", payload, response)

    def exit(self, payload: dict[str, Any]) -> dict[str, Any]:
        cached = self._idempotent("/exit", payload)
        if cached is not None:
            return cached
        if not self._validate_common(payload, {"arena_id", "robot_id", "request_id"}) or not self._ready():
            return self._base(False, rejected=True)
        self.exited = True
        response = self._base(True) | {"exit_reason": "user_exit"}
        return self._record("/exit", payload, response)

    def handle(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        return {"/enter": self.enter, "/measure": self.measure, "/clear": self.clear, "/exit": self.exit}[path](payload)

    def truth_summary(self) -> dict[str, Any]:
        emitters = [asdict(e) for e in self._emitters]
        cleared = sum(e.cleared for e in self._emitters)
        return {
            "seed": self.config.seed,
            "emitter_count": len(emitters),
            "directional_count": sum(e.directional for e in self._emitters),
            "cleared_count": cleared,
            "clear_rate": cleared / len(emitters),
            "all_cleared": cleared == len(emitters),
            "virtual_time_s": self.virtual_time_s,
            "first_seen_time_s": dict(self.first_seen_time),
            "clear_success_time_s": dict(self.clear_success_time),
            "first_clear_time_s": min(self.clear_success_time.values()) if self.clear_success_time else None,
            "last_clear_time_s": max(self.clear_success_time.values()) if self.clear_success_time else None,
            "measurements_before_first_clear": self.measurements_before_first_clear,
            "directional_loss_count": self.directional_loss_count,
            "directional_reacquisition_count": self.directional_reacquisition_count,
            "stats": dict(self.stats),
            "emitters": emitters,
        }
