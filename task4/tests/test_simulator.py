import unittest
import json
import threading
from http.server import ThreadingHTTPServer
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from experiments.t4_local.engine import Emitter, LocalSimulator, SimulatorConfig, SimulatorError
from experiments.t4_local.server import make_handler
from task4.client import HTTPClient


def base(request_id):
    return {"arena_id": "default", "robot_id": "r", "request_id": request_id}


def action(request_id, x, y, channel):
    return base(request_id) | {"position": {"x": x, "y": y}, "channel": channel}


class SimulatorTests(unittest.TestCase):
    def make_sim(self, emitter=None):
        emitters = [emitter or Emitter(2, 300, 400, 1000, False, None)]
        sim = LocalSimulator(SimulatorConfig(seed=7, robot_id="r"), emitters)
        self.assertTrue(sim.enter(base("enter"))["accepted"])
        return sim

    def test_official_timing_example(self):
        sim = self.make_sim(Emitter(20, 1700, 0, 1000, False, None))
        self.assertEqual(sim.measure(action("m1", 300, 400, 1))["virtual_time_s"], 105)
        self.assertEqual(sim.measure(action("m2", 300, 400, 2))["virtual_time_s"], 111)
        self.assertEqual(sim.clear(action("c1", 300, 0, 3))["virtual_time_s"], 194)
        self.assertEqual(sim.measure(action("m3", 300, 0, 2))["virtual_time_s"], 199)

    def test_clear_does_not_change_receiver_channel(self):
        sim = self.make_sim()
        sim.measure(action("m1", 0, 0, 2))
        before = sim.stats["channel_switch_count"]
        sim.clear(action("c1", 0, 0, 10))
        sim.measure(action("m2", 0, 0, 2))
        self.assertEqual(sim.stats["channel_switch_count"], before)

    def test_near_and_clear_ignore_direction(self):
        emitter = Emitter(2, 0, 0, 1000, True, 0)
        sim = self.make_sim(emitter)
        # West is outside the east-facing half-plane, despite being close.
        self.assertEqual(sim.measure(action("m1", -1, 0, 2))["measure_result"], "no_signal")
        self.assertEqual(sim.clear(action("c1", -19, 0, 2))["clear_result"], "success")

    def test_directional_boundary_is_inclusive(self):
        emitter = Emitter(2, 0, 0, 1000, True, 0)
        sim = self.make_sim(emitter)
        self.assertEqual(sim.measure(action("m1", 0, 100, 2))["measure_result"], "direction")

    def test_fixed_location_error_and_idempotency(self):
        sim = self.make_sim()
        payload = action("m1", 0, 0, 2)
        first = sim.measure(payload)
        second = sim.measure(payload)
        self.assertEqual(first, second)
        self.assertEqual(sim.stats["measure_count"], 1)
        with self.assertRaises(SimulatorError):
            sim.measure(action("m1", 1, 0, 2))

    def test_no_signal_three_causes(self):
        directional = self.make_sim(Emitter(2, 0, 0, 1000, True, 0))
        self.assertEqual(directional.measure(action("m1", -100, 0, 2))["measure_result"], "no_signal")
        far = self.make_sim(Emitter(2, 1500, 0, 1000, False, None))
        self.assertEqual(far.measure(action("m1", 0, 0, 2))["measure_result"], "no_signal")
        absent = self.make_sim(Emitter(2, 0, 0, 1000, False, None))
        self.assertEqual(absent.measure(action("m1", 0, 0, 3))["measure_result"], "no_signal")

    def test_research_timing_and_measurement_counters(self):
        sim = self.make_sim(Emitter(2, 300, 0, 1000, False, None))
        self.assertEqual(sim.measure(action("m1", 0, 0, 3))["measure_result"], "no_signal")
        self.assertEqual(sim.measure(action("m2", 0, 0, 2))["measure_result"], "direction")
        self.assertEqual(sim.clear(action("c1", 300, 0, 2))["clear_result"], "success")
        truth = sim.truth_summary()
        self.assertEqual(truth["stats"]["no_signal_count"], 1)
        self.assertEqual(truth["stats"]["direction_count"], 1)
        self.assertEqual(truth["measurements_before_first_clear"], 2)
        self.assertEqual(truth["first_clear_time_s"], truth["last_clear_time_s"])


class HTTPIntegrationTests(unittest.TestCase):
    def setUp(self):
        self.sim = LocalSimulator(SimulatorConfig(seed=4, robot_id="r"), [Emitter(2, 300, 400, 1000, False, None)])
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), make_handler(self.sim))
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()
        self.url = f"http://127.0.0.1:{self.server.server_port}"

    def tearDown(self):
        self.server.shutdown()
        self.server.server_close()
        self.thread.join(timeout=2)

    def raw(self, path, body, headers=None):
        request = Request(self.url + path, data=body, headers=headers or {"Content-Type": "application/json"}, method="POST")
        try:
            with urlopen(request) as response:
                return response.status, json.loads(response.read())
        except HTTPError as exc:
            return exc.code, json.loads(exc.read())

    def test_http_client_uses_official_paths(self):
        client = HTTPClient(self.url, "r")
        self.assertTrue(client.enter()["accepted"])
        self.assertEqual(client.measure((0, 0), 2)["measure_result"], "direction")
        self.assertTrue(client.exit()["accepted"])

    def test_duplicate_key_and_encoding_rejected(self):
        status, _ = self.raw("/enter", b'{"arena_id":"default","arena_id":"default","robot_id":"r","request_id":"x"}')
        self.assertEqual(status, 400)
        status, _ = self.raw("/enter", b"{}", {"Content-Type": "application/json", "Content-Encoding": "gzip"})
        self.assertEqual(status, 415)

    def test_unknown_field_is_business_rejection(self):
        payload = base("x") | {"typo": 1}
        status, response = self.raw("/enter", json.dumps(payload).encode())
        self.assertEqual(status, 200)
        self.assertFalse(response["accepted"])
        self.assertEqual(response["virtual_time_s"], 0)

    def test_missing_and_bad_coordinate_are_http_400(self):
        status, _ = self.raw("/enter", json.dumps({"arena_id": "default"}).encode())
        self.assertEqual(status, 400)
        self.sim.enter(base("enter"))
        payload = action("m", 0, 0, 2)
        payload["position"]["extra"] = 1
        status, response = self.raw("/measure", json.dumps(payload).encode())
        self.assertEqual(status, 200)
        self.assertFalse(response["accepted"])
        payload = action("m2", 2_000_001, 0, 2)
        status, _ = self.raw("/measure", json.dumps(payload).encode())
        self.assertEqual(status, 400)


if __name__ == "__main__":
    unittest.main()
