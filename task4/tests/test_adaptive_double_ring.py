import math
import unittest
from unittest.mock import patch

from experiments.t4_local.engine import Emitter, LocalSimulator, SimulatorConfig
from task4.client import InProcessClient
from task4.geometry import distance
from task4.strategies.adaptive_double_ring_clear_probe import (
    AdaptiveDoubleRingClearProbeStrategy,
)


def make_client(emitters, seed=7):
    simulator = LocalSimulator(SimulatorConfig(seed=seed), emitters)
    return simulator, InProcessClient(simulator, simulator.config.robot_id)


class AdaptiveDoubleRingTests(unittest.TestCase):
    def test_optical_certificates_cover_the_complete_radial_interval(self):
        for feasible_radius in (19.5, 35.0, 35.01, 45.0, 45.01, 50.0):
            with self.subTest(feasible_radius=feasible_radius):
                strategy = AdaptiveDoubleRingClearProbeStrategy(
                    early_clear_radius_m=feasible_radius
                )
                count, ring_radius = strategy._optical_ring()
                # For the closest ring center the angular gap is <=pi/count.
                # Squared distance is convex in r, so its endpoint maxima
                # certify the entire annulus; the center covers r<=20.
                for radial_distance in (20.0, max(20.0, feasible_radius)):
                    worst_squared_distance = (
                        radial_distance**2
                        + ring_radius**2
                        - 2.0
                        * radial_distance
                        * ring_radius
                        * math.cos(math.pi / count)
                    )
                    self.assertLess(worst_squared_distance, 20.0**2)

    def test_failed_center_reaches_last_optical_ring_point_and_clears(self):
        for feasible_radius in (35.0, 45.0, 50.0):
            with self.subTest(feasible_radius=feasible_radius):
                strategy = AdaptiveDoubleRingClearProbeStrategy(
                    early_clear_radius_m=feasible_radius
                )
                count, ring_radius = strategy._optical_ring()
                angle = 2.0 * math.pi * (count - 1) / count
                source = (
                    (feasible_radius - 2.0) * math.cos(angle),
                    (feasible_radius - 2.0) * math.sin(angle),
                )
                simulator, api = make_client([
                    Emitter(7, *source, 1000.0, False, None)
                ])
                api.enter()
                # Two genuine API observations certify a small region around
                # the real source, entirely within the proposed center disk.
                for station in (
                    (source[0] + 30.0, source[1]),
                    (source[0], source[1] + 30.0),
                ):
                    response = strategy._measure(api, station, 7)
                    self.assertEqual(response["measure_result"], "direction")
                polygon = strategy.beliefs[7].polygon()
                self.assertTrue(polygon)
                self.assertLessEqual(
                    max(distance((0.0, 0.0), vertex) for vertex in polygon),
                    feasible_radius,
                )

                self.assertTrue(strategy._clear(api, (0.0, 0.0), 7))
                clears = [action for action in api.actions if action["path"] == "/clear"]
                self.assertEqual(clears[0]["response"]["clear_result"], "no_target_in_range")
                self.assertEqual(clears[-1]["response"]["clear_result"], "success")
                self.assertEqual(len(clears), count + 1)
                self.assertEqual(strategy._stats["optical_cover_attempts"], count)
                self.assertEqual(strategy.beliefs[7].status, "cleared")
                self.assertAlmostEqual(strategy.position[0], ring_radius * math.cos(angle))
                self.assertAlmostEqual(strategy.position[1], ring_radius * math.sin(angle))
                self.assertEqual(strategy.position, simulator.position)
                self.assertEqual(strategy.virtual_time_s, clears[-1]["response"]["virtual_time_s"])
                self.assertAlmostEqual(strategy.virtual_time_s, simulator.virtual_time_s, places=6)
                self.assertEqual(strategy.receiver_channel, simulator.channel)

    def test_uncertified_failed_clear_does_not_start_optical_ring(self):
        strategy = AdaptiveDoubleRingClearProbeStrategy()
        simulator, api = make_client([
            Emitter(7, 1000.0, 0.0, 1000.0, False, None)
        ])
        api.enter()
        strategy._measure(api, (1030.0, 0.0), 7)
        strategy._measure(api, (1000.0, 30.0), 7)
        self.assertFalse(strategy._clear(api, (0.0, 0.0), 7))
        self.assertEqual(simulator.stats["clear_attempt_count"], 1)
        self.assertEqual(strategy._stats["optical_cover_attempts"], 0)
        self.assertNotEqual(strategy.beliefs[7].status, "cleared")

    def test_fifteen_seen_keep_unknown_channels_and_sixteen_exclude_them(self):
        strategy = AdaptiveDoubleRingClearProbeStrategy()
        for channel in range(1, 16):
            strategy.beliefs[channel].status = "active"
        self.assertFalse(strategy._all_seen())
        self.assertTrue(
            set(range(16, 21)).issubset(
                strategy._channel_scan_order({"located", "cleared"})
            )
        )
        strategy.beliefs[16].status = "active"
        self.assertTrue(strategy._all_seen())
        self.assertEqual(
            set(strategy._channel_scan_order({"located", "cleared"})),
            set(range(1, 17)),
        )

    def test_sixteenth_near_source_stops_unknown_scans_and_clears_before_exit(self):
        simulator, api = make_client([
            Emitter(channel, 0.0, 0.0, 1000.0, False, None)
            for channel in range(1, 17)
        ])
        strategy = AdaptiveDoubleRingClearProbeStrategy()
        result = strategy.run(api)

        measurements = [action for action in api.actions if action["path"] == "/measure"]
        self.assertEqual(len(measurements), 16)
        self.assertEqual(
            {action["request"]["channel"] for action in measurements},
            set(range(1, 17)),
        )
        self.assertEqual(result.diagnostics["coverage_points_visited"], 1)
        self.assertEqual(result.diagnostics["coverage_points_omitted_after_seen16"], 24)
        self.assertIsNotNone(result.diagnostics["seen16_time_s"])
        self.assertTrue(simulator.truth_summary()["all_cleared"])
        self.assertEqual(result.cleared_channels, list(range(1, 17)))
        self.assertEqual(api.actions[-1]["path"], "/exit")
        self.assertEqual(api.actions[-2]["response"]["clear_result"], "success")
        self.assertEqual(result.final_virtual_time_s, simulator.virtual_time_s)

    def test_fifteen_sources_preserve_and_visit_all_twenty_five_cover_points(self):
        simulator, api = make_client([
            Emitter(channel, 0.0, 0.0, 1000.0, False, None)
            for channel in range(1, 16)
        ])
        strategy = AdaptiveDoubleRingClearProbeStrategy()
        expected_cover = set(strategy._search_waypoints())
        self.assertEqual(len(expected_cover), 25)
        result = strategy.run(api)

        absent_measurements = [
            action for action in api.actions
            if action["path"] == "/measure" and action["request"]["channel"] == 20
        ]
        actual_cover = {
            (action["request"]["position"]["x"], action["request"]["position"]["y"])
            for action in absent_measurements
        }
        self.assertEqual(actual_cover, expected_cover)
        self.assertEqual(len(absent_measurements), 25)
        self.assertEqual(result.diagnostics["coverage_points_visited"], 25)
        self.assertEqual(result.diagnostics["coverage_points_omitted_after_seen16"], 0)
        self.assertIsNone(result.diagnostics["seen16_time_s"])
        self.assertTrue(simulator.truth_summary()["all_cleared"])

    def test_clear_site_probes_use_actual_position_and_preserve_cover(self):
        simulator, api = make_client([
            Emitter(2, 0.0, 0.0, 1000.0, False, None),
            Emitter(3, 500.0, 0.0, 1000.0, False, None),
            Emitter(4, 0.0, 500.0, 1000.0, False, None),
        ])
        strategy = AdaptiveDoubleRingClearProbeStrategy()
        api.enter()
        for channel in (2, 3, 4):
            strategy._measure(api, (100.0, 100.0), channel)
        strategy.position = (100.0, 100.0)
        remaining = strategy._search_waypoints()
        before = list(remaining)
        action_count = len(api.actions)
        with patch.object(strategy, "_clear_probe_value", side_effect=lambda point, belief: float(belief.channel)):
            strategy._after_clear(api, (0.0, 0.0), remaining)
        probes = api.actions[action_count:]
        self.assertEqual(remaining, before)
        self.assertEqual(len(probes), 2)
        self.assertEqual({action["request"]["channel"] for action in probes}, {3, 4})
        self.assertTrue(all(
            action["request"]["position"] == {"x": 100.0, "y": 100.0}
            for action in probes
        ))
        self.assertEqual(strategy.position, simulator.position)

    def test_known_directional_source_finishes_by_optical_strip_with_shared_state(self):
        # This source is visible at the first station, but all standard
        # forward/lateral reacquisition candidates lie behind its beam.
        # The 20/55/90 m optical prefix also misses; the strip must complete it.
        simulator, api = make_client([
            Emitter(7, 150.0, 0.0, 1000.0, True, 180.0)
        ])
        strategy = AdaptiveDoubleRingClearProbeStrategy()
        api.enter()
        self.assertEqual(strategy._measure(api, (0.0, 0.0), 7)["measure_result"], "direction")
        strategy._measure(api, (900.0, 700.0), 20)
        initial_state = (strategy.position, strategy.virtual_time_s, strategy.receiver_channel)
        created = []
        original_factory = strategy._make_reacquisition_helper

        def capture_helper():
            helper = original_factory()
            self.assertEqual(
                (helper.position, helper.virtual_time_s, helper.receiver_channel),
                initial_state,
            )
            created.append(helper)
            return helper

        with patch.object(strategy, "_make_reacquisition_helper", side_effect=capture_helper):
            strategy._finish_known_sources(api)
        self.assertEqual(len(created), 1)
        helper = created[0]
        self.assertIs(helper.beliefs, strategy.beliefs)
        self.assertEqual(strategy.beliefs[7].status, "cleared")
        self.assertGreater(simulator.stats["clear_attempt_count"], 3)
        self.assertEqual(strategy.receiver_channel, 7)
        self.assertEqual(strategy.receiver_channel, helper.receiver_channel)
        self.assertEqual(strategy.receiver_channel, simulator.channel)
        self.assertEqual(strategy.position, helper.position)
        self.assertEqual(strategy.position, simulator.position)
        self.assertEqual(strategy.virtual_time_s, helper.virtual_time_s)
        self.assertEqual(strategy.virtual_time_s, api.actions[-1]["response"]["virtual_time_s"])
        self.assertAlmostEqual(strategy.virtual_time_s, simulator.virtual_time_s, places=6)
        self.assertTrue(simulator.truth_summary()["all_cleared"])

    def test_invalid_parameters_cannot_disable_certificates(self):
        invalid = [
            {"early_clear_radius_m": radius}
            for radius in (19.49, 50.01, float("nan"), float("inf"), -float("inf"))
        ]
        invalid.extend({"max_replaced_waypoints": count} for count in (-1, 1, 2))
        invalid.extend({"clear_probe_limit": count} for count in (-1, 0.5, True))
        for kwargs in invalid:
            with self.subTest(kwargs=kwargs):
                with self.assertRaises(ValueError):
                    AdaptiveDoubleRingClearProbeStrategy(**kwargs)


if __name__ == "__main__":
    unittest.main()
