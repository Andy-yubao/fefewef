import unittest

from task4.strategies import STRATEGIES, make_strategy
from task4.strategies.integrated_route import RouteNode, _plan_nodes_multistart


class StrategyPackageTests(unittest.TestCase):
    def test_all_strategies_are_registered(self):
        self.assertEqual(
            set(STRATEGIES),
            {
                "coverage",
                "active",
                "reacquire",
                "deferred",
                "lattice",
                "opportunistic",
                "belief",
                "route_optimized",
                "local_eig",
                "rejoin_clear",
                "early_stop",
                "integrated_route",
                "clear_probe",
                "clear_probe_multistart",
                "certified_clear_probe",
                "active_clear_probe",
                "endgame_clear_probe",
                "optimized_clear_probe",
                "replacement_aware_clear_probe",
                "geometry_aware_clear_probe",
                "certified_geometry_clear_probe",
                "early_optical_clear_probe",
                "ida_heuristic_clear_probe",
                "geometry_early_optical_clear_probe",
                "sequential_triangle_clear_19",
            },
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
            "clear_probe_multistart": "task4.strategies.clear_probe_multistart",
            "certified_clear_probe": "task4.strategies.certified_clear_probe",
            "active_clear_probe": "task4.strategies.active_clear_probe",
            "endgame_clear_probe": "task4.strategies.endgame_clear_probe",
            "optimized_clear_probe": "task4.strategies.optimized_clear_probe",
            "replacement_aware_clear_probe": "task4.strategies.replacement_aware_clear_probe",
            "geometry_aware_clear_probe": "task4.strategies.geometry_aware_clear_probe",
            "certified_geometry_clear_probe": "task4.strategies.certified_geometry_clear_probe",
            "early_optical_clear_probe": "task4.strategies.early_optical_clear_probe",
            "ida_heuristic_clear_probe": "task4.strategies.ida_heuristic_clear_probe",
            "geometry_early_optical_clear_probe": "task4.strategies.geometry_early_optical_clear_probe",
            "sequential_triangle_clear_19": "task4.strategies.sequential_triangle_clear_19",
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
        replacement_aware = make_strategy("replacement_aware_clear_probe")
        self.assertEqual(replacement_aware.lattice_spacing, 731.0)
        self.assertEqual(replacement_aware.replacement_distance_m, 400.0)
        self.assertEqual(replacement_aware.max_replaced_waypoints, 2)
        geometry_aware = make_strategy("geometry_aware_clear_probe")
        self.assertEqual(geometry_aware.route_length_slack_m, 100.0)
        early_optical = make_strategy("early_optical_clear_probe")
        self.assertEqual(early_optical.early_clear_radius_m, 30.0)
        heuristic = make_strategy("ida_heuristic_clear_probe")
        self.assertEqual(heuristic.heuristic_depth, 3)
        self.assertEqual(heuristic.geometry_credit_s, 12.0)
        geometry_optical = make_strategy("geometry_early_optical_clear_probe")
        self.assertEqual(geometry_optical.early_clear_radius_m, 30.0)
        self.assertEqual(geometry_optical.route_length_slack_m, 100.0)

    def test_receiver_aware_channel_order_avoids_extra_switch(self):
        strategy = make_strategy("clear_probe")
        strategy.receiver_channel = 20
        order = strategy._channel_scan_order({"located", "cleared"})
        self.assertEqual(order[0], 20)
        self.assertEqual(order[-1], 1)

    def test_certified_replacement_protects_adjacent_lattice_points(self):
        strategy = make_strategy("certified_clear_probe")
        center = (0.0, 0.0)
        remaining = strategy._search_waypoints()
        selected = strategy._choose_replacements(center, remaining)
        self.assertEqual(selected, [center])
        neighbor = strategy._lattice_neighbors(center)[0]
        self.assertFalse(strategy._certifies_replacement(neighbor, neighbor))

    def test_multistart_route_is_a_deterministic_permutation(self):
        nodes = [
            RouteNode("measure", 0, (0.0, 0.0)),
            RouteNode("measure", 1, (1.0, 0.0)),
            RouteNode("clear", 2, (1.0, 1.0)),
            RouteNode("measure", 3, (0.0, 1.0)),
        ]
        first = _plan_nodes_multistart(nodes, (0.0, 0.0))
        second = _plan_nodes_multistart(nodes, (0.0, 0.0))
        self.assertEqual(first, second)
        self.assertEqual(set(first), set(nodes))

    def test_replacement_aware_route_omits_provisional_substitute(self):
        strategy = make_strategy("replacement_aware_clear_probe")
        clear = RouteNode("clear", 1, (0.0, 0.0))
        near = RouteNode("measure", 2, (100.0, 0.0))
        far = RouteNode("measure", 3, (1000.0, 0.0))
        route = strategy._plan_route([clear, near, far], (0.0, 0.0))
        self.assertIn(clear, route)
        self.assertIn(far, route)
        self.assertNotIn(near, route)


if __name__ == "__main__":
    unittest.main()
