import unittest

from task4.strategies import STRATEGIES, make_strategy


class StrategyPackageTests(unittest.TestCase):
    def test_all_strategies_are_registered(self):
        self.assertEqual(
            set(STRATEGIES),
            {"coverage", "active", "reacquire", "deferred", "lattice", "opportunistic", "belief", "route_optimized", "local_eig", "rejoin_clear", "early_stop", "integrated_route", "clear_probe"},
        )

    def test_each_concrete_strategy_has_its_own_module(self):
        expected_modules = {
            "coverage": "task4.strategies.coverage",
            "active": "task4.strategies.active",
            "reacquire": "task4.strategies.reacquire",
            "deferred": "task4.strategies.deferred",
            "lattice": "task4.strategies.lattice",
            "opportunistic": "task4.strategies.opportunistic",
            "belief": "task4.strategies.belief",
            "route_optimized": "task4.strategies.route_optimized",
            "local_eig": "task4.strategies.local_eig",
            "rejoin_clear": "task4.strategies.rejoin_clear",
            "early_stop": "task4.strategies.early_stop",
            "integrated_route": "task4.strategies.integrated_route",
            "clear_probe": "task4.strategies.clear_probe",
        }
        for name, module in expected_modules.items():
            with self.subTest(strategy=name):
                self.assertEqual(type(make_strategy(name)).__module__, module)

    def test_unknown_strategy_has_clear_error(self):
        with self.assertRaisesRegex(ValueError, "unknown strategy"):
            make_strategy("missing")

    def test_tuned_defaults_are_stable(self):
        opportunistic = make_strategy("opportunistic")
        belief = make_strategy("belief")
        self.assertEqual(opportunistic.lattice_spacing, 760.0)
        self.assertEqual(opportunistic.clear_detour_threshold_m, 1500.0)
        self.assertEqual(belief.belief_travel_weight, 16.0)
        clear_probe = make_strategy("clear_probe")
        self.assertEqual(clear_probe.lattice_spacing, 735.0)
        self.assertEqual(clear_probe.replacement_distance_m, 400.0)
        self.assertEqual(clear_probe.max_replaced_waypoints, 2)

    def test_receiver_aware_channel_order_avoids_extra_switch(self):
        strategy = make_strategy("clear_probe")
        strategy.receiver_channel = 20
        order = strategy._channel_scan_order({"located", "cleared"})
        self.assertEqual(order[0], 20)
        self.assertEqual(order[-1], 1)


if __name__ == "__main__":
    unittest.main()
