"""Strict serial HTTP+JSON client for the simulator protocol."""

from __future__ import annotations

from dataclasses import dataclass
import json
from pathlib import Path
import threading
import time
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
import uuid

from .config import ClientConfig


class ProtocolError(RuntimeError):
    pass


class TransportError(RuntimeError):
    pass


@dataclass(frozen=True)
class ResponseRecord:
    path: str
    request: dict[str, Any]
    status: int
    response: dict[str, Any]
    attempts: int
    wall_elapsed_s: float


class SimulatorClient:
    """One in-flight request, immutable retry payloads, and auditable JSONL logs."""

    def __init__(self, config: ClientConfig, log_path: str | Path | None = None):
        if not config.robot_id:
            raise ValueError("robot_id is required")
        self.config = config
        self.log_path = Path(log_path) if log_path else None
        self.last_virtual_time_s = 0.0
        self.remaining_real_duration_s: float | None = None
        self._entered_monotonic: float | None = None
        self._counter = 0
        self._lock = threading.Lock()
        self.position = (0.0, 0.0)
        self.current_channel = 1

    def _request_id(self, action: str) -> str:
        self._counter += 1
        return f"{action}-{self._counter}-{uuid.uuid4().hex[:12]}"

    def _base(self, action: str) -> dict[str, Any]:
        return {
            "arena_id": self.config.arena_id,
            "robot_id": self.config.robot_id,
            "request_id": self._request_id(action),
        }

    def _write_log(self, record: dict[str, Any]) -> None:
        if self.log_path is None:
            return
        record = json.loads(json.dumps(record, ensure_ascii=False))
        request = record.get("request")
        if isinstance(request, dict) and "robot_id" in request:
            request["robot_id"] = "<redacted>"
        self.log_path.parent.mkdir(parents=True, exist_ok=True)
        with self.log_path.open("a", encoding="utf-8") as handle:
            handle.write(json.dumps(record, ensure_ascii=False, sort_keys=True) + "\n")

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        body = json.dumps(payload, ensure_ascii=False, separators=(",", ":"), allow_nan=False).encode("utf-8")
        if len(body) > 65536:
            raise ProtocolError("request exceeds 65536 bytes")
        start = time.perf_counter()
        last_error: Exception | None = None
        # Lock spans all retries, so no distinct action can be in flight.
        with self._lock:
            for attempt in range(1, self.config.retries + 2):
                request = Request(
                    self.config.base_url.rstrip("/") + path,
                    data=body,
                    headers={"Content-Type": "application/json; charset=utf-8"},
                    method="POST",
                )
                try:
                    with urlopen(request, timeout=self.config.timeout_s) as response:
                        status = int(response.status)
                        raw = response.read().decode("utf-8")
                    parsed = json.loads(raw)
                except HTTPError as exc:
                    status = int(exc.code)
                    try:
                        parsed = json.loads(exc.read().decode("utf-8"))
                    except Exception as decode_exc:
                        raise ProtocolError(f"HTTP {status} with invalid JSON") from decode_exc
                    self._write_log({"event": "response", "path": path, "request": payload,
                                     "status": status, "response": parsed, "attempt": attempt})
                    raise ProtocolError(f"HTTP {status}: {parsed}") from exc
                except (TimeoutError, URLError, ConnectionError, OSError) as exc:
                    last_error = exc
                    self._write_log({"event": "transport_retry", "path": path, "request": payload,
                                     "attempt": attempt, "error": repr(exc)})
                    if attempt <= self.config.retries:
                        time.sleep(self.config.retry_backoff_s * attempt)
                        continue
                    raise TransportError(f"{path} failed after {attempt} attempts: {exc}") from exc
                if status != 200:
                    raise ProtocolError(f"HTTP {status}: {parsed}")
                if not isinstance(parsed, dict) or parsed.get("accepted") is not True:
                    self._write_log({"event": "rejected", "path": path, "request": payload,
                                     "status": status, "response": parsed, "attempt": attempt})
                    raise ProtocolError(f"action rejected: {parsed}")
                if "virtual_time_s" not in parsed:
                    raise ProtocolError("accepted response lacks virtual_time_s")
                self.last_virtual_time_s = float(parsed["virtual_time_s"])
                self._write_log({"event": "response", "path": path, "request": payload,
                                 "status": status, "response": parsed, "attempt": attempt,
                                 "wall_elapsed_s": time.perf_counter() - start})
                return parsed
        assert last_error is not None
        raise TransportError(str(last_error))

    def enter(self) -> dict[str, Any]:
        response = self._post("/enter", self._base("enter"))
        self.remaining_real_duration_s = float(response["remaining_real_duration_s"])
        self._entered_monotonic = time.monotonic()
        return response

    def measure(self, position: tuple[float, float] | list[float], channel: int) -> dict[str, Any]:
        payload = self._base("measure")
        payload.update({"position": {"x": float(position[0]), "y": float(position[1])}, "channel": int(channel)})
        response = self._post("/measure", payload)
        self.position = (float(position[0]), float(position[1]))
        self.current_channel = int(channel)
        return response

    def clear(self, position: tuple[float, float] | list[float], channel: int) -> dict[str, Any]:
        payload = self._base("clear")
        payload.update({"position": {"x": float(position[0]), "y": float(position[1])}, "channel": int(channel)})
        response = self._post("/clear", payload)
        self.position = (float(position[0]), float(position[1]))
        # Protocol invariant: clear does not mutate current_channel.
        return response

    def exit(self) -> dict[str, Any]:
        return self._post("/exit", self._base("exit"))

    def real_time_left_s(self) -> float:
        if self._entered_monotonic is None or self.remaining_real_duration_s is None:
            return math.inf
        return self.remaining_real_duration_s - (time.monotonic() - self._entered_monotonic)


# Imported late only to keep the protocol section visually compact.
import math
