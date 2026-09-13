"""HTTP status, rejection, idempotent retry, and channel-state tests."""

from __future__ import annotations

import json
from unittest.mock import patch
from urllib.error import URLError

import pytest

from task3.src.client import ProtocolError, SimulatorClient, TransportError
from task3.src.config import ClientConfig


class FakeResponse:
    def __init__(self, body: dict, status: int = 200):
        self.body = json.dumps(body).encode()
        self.status = status
    def __enter__(self): return self
    def __exit__(self, *args): return False
    def read(self): return self.body


def client(retries: int = 1) -> SimulatorClient:
    return SimulatorClient(ClientConfig(robot_id="test-team", retries=retries, retry_backoff_s=0.0))


def test_timeout_retry_reuses_identical_request_and_id() -> None:
    c = client(retries=1)
    accepted = FakeResponse({"accepted": True, "real_timestamp_ms": 1, "virtual_time_s": 0,
                             "remaining_real_duration_s": 1200,
                             "max_virtual_duration_s": 360000, "max_real_duration_s": 1200})
    with patch("task3.src.client.urlopen", side_effect=[URLError("drop"), accepted]) as mocked:
        c.enter()
    assert mocked.call_count == 2
    first = mocked.call_args_list[0].args[0].data
    second = mocked.call_args_list[1].args[0].data
    assert first == second
    assert json.loads(first)["request_id"] == json.loads(second)["request_id"]


def test_rejected_response_does_not_reset_last_valid_virtual_time() -> None:
    c = client()
    c.last_virtual_time_s = 42.5
    rejected = FakeResponse({"accepted": False, "real_timestamp_ms": 1, "virtual_time_s": 0})
    with patch("task3.src.client.urlopen", return_value=rejected):
        with pytest.raises(ProtocolError, match="rejected"):
            c._post("/measure", {"request_id": "x"})
    assert c.last_virtual_time_s == 42.5


def test_connection_failure_is_reported_after_configured_retries() -> None:
    c = client(retries=2)
    with patch("task3.src.client.urlopen", side_effect=URLError("offline")) as mocked:
        with pytest.raises(TransportError, match="after 3 attempts"):
            c.enter()
    assert mocked.call_count == 3


def test_clear_does_not_change_current_measurement_channel() -> None:
    c = client()
    c.current_channel = 7
    response = FakeResponse({"accepted": True, "real_timestamp_ms": 1, "virtual_time_s": 10,
                             "clear_result": "no_target_in_range"})
    with patch("task3.src.client.urlopen", return_value=response):
        c.clear((1.0, 2.0), 3)
    assert c.current_channel == 7

