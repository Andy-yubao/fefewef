from __future__ import annotations

from dataclasses import dataclass
import json
import time
from typing import Any, Protocol
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class ClientError(RuntimeError):
    pass


class RobotAPI(Protocol):
    def enter(self) -> dict[str, Any]: ...
    def measure(self, position: tuple[float, float], channel: int) -> dict[str, Any]: ...
    def clear(self, position: tuple[float, float], channel: int) -> dict[str, Any]: ...
    def exit(self) -> dict[str, Any]: ...


@dataclass
class BaseClient:
    robot_id: str
    arena_id: str = "default"

    def __post_init__(self):
        self._sequence = 0
        self.actions: list[dict[str, Any]] = []

    def _base(self, kind: str) -> dict[str, Any]:
        self._sequence += 1
        return {"arena_id": self.arena_id, "robot_id": self.robot_id, "request_id": f"{kind}-{self._sequence}"}

    def _action(self, kind: str, position: tuple[float, float], channel: int) -> dict[str, Any]:
        return self._base(kind) | {"position": {"x": position[0], "y": position[1]}, "channel": channel}


class HTTPClient(BaseClient):
    def __init__(self, base_url: str, robot_id: str, timeout_s: float = 10.0, retries: int = 2):
        super().__init__(robot_id)
        self.base_url = base_url.rstrip("/")
        self.timeout_s = timeout_s
        self.retries = retries

    def _post(self, path: str, payload: dict[str, Any]) -> dict[str, Any]:
        request = Request(self.base_url + path, data=json.dumps(payload).encode("utf-8"), headers={"Content-Type": "application/json"}, method="POST")
        last_error: Exception | None = None
        for attempt in range(self.retries + 1):
            try:
                with urlopen(request, timeout=self.timeout_s) as response:
                    data = json.loads(response.read().decode("utf-8"))
                    if response.status != 200 or data.get("accepted") is not True:
                        raise ClientError(f"{path} rejected: HTTP {response.status}, {data}")
                    self.actions.append({"path": path, "request": payload, "response": data})
                    return data
            except HTTPError as exc:
                body = exc.read().decode("utf-8", errors="replace")
                raise ClientError(f"{path} HTTP {exc.code}: {body}") from exc
            except (URLError, TimeoutError) as exc:
                last_error = exc
                if attempt < self.retries:
                    time.sleep(0.1 * (attempt + 1))
        raise ClientError(f"{path} transport failure after retries: {last_error}")

    def enter(self): return self._post("/enter", self._base("enter"))
    def measure(self, position, channel): return self._post("/measure", self._action("measure", position, channel))
    def clear(self, position, channel): return self._post("/clear", self._action("clear", position, channel))
    def exit(self): return self._post("/exit", self._base("exit"))


class InProcessClient(BaseClient):
    """Fast experiment adapter exposing exactly the same four actions as HTTPClient."""
    def __init__(self, simulator, robot_id: str):
        super().__init__(robot_id)
        self.simulator = simulator

    def _post(self, path: str, payload: dict[str, Any]):
        response = self.simulator.handle(path, payload)
        if response.get("accepted") is not True:
            raise ClientError(f"{path} rejected: {response}")
        self.actions.append({"path": path, "request": payload, "response": response})
        return response

    def enter(self): return self._post("/enter", self._base("enter"))
    def measure(self, position, channel): return self._post("/measure", self._action("measure", position, channel))
    def clear(self, position, channel): return self._post("/clear", self._action("clear", position, channel))
    def exit(self): return self._post("/exit", self._base("exit"))
