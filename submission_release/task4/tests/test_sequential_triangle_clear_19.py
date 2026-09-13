import itertools
import math
import unittest

from task4.geometry import bearing_deg, distance, enclosing_center_radius
from task4.strategies.sequential_triangle_clear_19 import (
    CheckCandidate,
    LOCAL_CHECK_MAX_DETOUR_M,
    LocalTask,
    SequentialTriangleClear19Strategy,
)
from task4.strategies.triangle_cells import (
    CELL_VERTEX_IDS,
    cells_closed_at,
    fixed_start_open_route,
    fixed_start_end_route,
    main_points,
    route_length,
    triangle_cells,
)


class TriangleTopologyTests(unittest.TestCase):
    def test_fixed_nineteen_point_order_and_coordinates(self):
        points = main_points()
        self.assertEqual(len(points), 19)
        self.assertEqual(points[0], (0.0, 0.0))
        self.assertEqual(points[1], (1000.0, 0.0))
        self.assertAlmostEqual(points[2][0], 500.0)
        self.assertAlmostEqual(points[2][1], 500.0 * math.sqrt(3.0))
        self.assertEqual(len(set(points)), 19)

    def test_six_outer_points_are_not_clamped_to_arena(self):
        points = main_points()
        outside = [index for index, point in enumerate(points, start=1) if math.hypot(*point) > 1800.0]
        self.assertEqual(outside, [9, 11, 13, 15, 17, 19])
        self.assertTrue(all(math.isclose(math.hypot(*points[index - 1]), 2000.0) for index in outside))

    def test_twenty_four_explicit_unit_triangles(self):
        cells = triangle_cells()
        self.assertEqual(len(cells), 24)
        self.assertEqual(tuple(cell.vertex_ids for cell in cells), CELL_VERTEX_IDS)
        for cell in cells:
            sides = [distance(a, b) for a, b in zip(cell.polygon, cell.polygon[1:] + cell.polygon[:1])]
            self.assertTrue(all(abs(side - 1000.0) < 1e-7 for side in sides))
            self.assertEqual(cell.closed_at, max(cell.vertex_ids))

    def test_close_schedule_starts_at_p3_and_is_complete(self):
        self.assertEqual(cells_closed_at(1), ())
        self.assertEqual(cells_closed_at(2), ())
        self.assertEqual([cell.vertex_ids for cell in cells_closed_at(3)], [(1, 2, 3)])
        closed = [cell.cell_id for point_id in range(1, 20) for cell in cells_closed_at(point_id)]
        self.assertEqual(sorted(closed), list(range(1, 25)))


class FixedEndRouteTests(unittest.TestCase):
    def test_zero_and_one_task(self):
        start, end = (0.0, 0.0), (3.0, 0.0)
        self.assertEqual(fixed_start_end_route([], start, end), [])
        task = LocalTask("clear", 1, 1, (1.0, 1.0))
        self.assertEqual(fixed_start_end_route([task], start, end), [task])

    def test_two_to_four_tasks_match_brute_force_and_are_deterministic(self):
        start, end = (-1.0, 0.0), (4.0, 0.0)
        all_tasks = [
            LocalTask("clear", 1, 1, (0.0, 2.0)),
            LocalTask("cross_view", 2, 1, (1.0, -1.0)),
            LocalTask("single_visible", 3, 2, (2.0, 2.0)),
            LocalTask("clear", 4, 2, (3.0, -1.0)),
        ]
        for count in range(2, 5):
            tasks = all_tasks[:count]
            route = fixed_start_end_route(tasks, start, end, tie_key=lambda task: task.key)
            repeat = fixed_start_end_route(tasks, start, end, tie_key=lambda task: task.key)
            optimum = min(route_length(order, start, end) for order in itertools.permutations(tasks))
            self.assertEqual(route, repeat)
            self.assertEqual(set(route), set(tasks))
            self.assertAlmostEqual(route_length(route, start, end), optimum)
            self.assertEqual(end, (4.0, 0.0))

    def test_open_end_route_does_not_pay_for_return_to_anchor(self):
        start = (0.0, 0.0)
        near = LocalTask("residual", 1, 0, (1.0, 0.0))
        far = LocalTask("residual", 2, 0, (10.0, 0.0))
        self.assertEqual(
            fixed_start_open_route([far, near], start, tie_key=lambda task: task.key),
            [near, far],
        )


class CellSettlementTests(unittest.TestCase):
    def setUp(self):
        self.strategy = SequentialTriangleClear19Strategy()
        self.cell = self.strategy.cells[0]
        self.source = (450.0, 250.0)

    def _observe(self, channel, vertex_ids, source=None):
        source = source or self.source
        belief = self.strategy.beliefs[channel]
        belief.status = "active"
        for vertex_id in vertex_ids:
            station = self.strategy.points[vertex_id - 1]
            belief.observations.append((station, bearing_deg(station, source)))
            self.strategy._vertex_results[(vertex_id, channel)] = "direction"
        for vertex_id in set(self.cell.vertex_ids) - set(vertex_ids):
            self.strategy._vertex_results[(vertex_id, channel)] = "no_signal"
        return belief

    def test_zero_positive_excludes_cell(self):
        belief = self.strategy.beliefs[1]
        belief.status = "active"
        outside = (-900.0, 0.0)
        belief.observations.append((outside, bearing_deg(outside, self.source)))
        for vertex in self.cell.vertex_ids:
            self.strategy._vertex_results[(vertex, 1)] = "no_signal"
        assessment = self.strategy.assess_cell(1, self.cell.cell_id)
        self.assertEqual(assessment.outcome, "excluded")
        self.assertIn(self.cell.cell_id, self.strategy._excluded_cells[1])

    def test_one_positive_creates_special_obligation(self):
        self._observe(2, [3])
        self.strategy.position = self.strategy.points[2]
        assessment = self.strategy.assess_cell(2, self.cell.cell_id)
        self.assertEqual(assessment.outcome, "single_visible")
        tasks = self.strategy._build_cell_tasks((self.cell.cell_id,), self.strategy.points[3])
        task = next(task for task in tasks if task.kind == "single_visible" and task.channel == 2)
        station, theta = self.strategy.beliefs[2].observations[0]
        self.assertAlmostEqual(bearing_deg(station, task.point), theta)
        self.assertLessEqual(self.strategy._detour(task.point, self.strategy.points[3]), LOCAL_CHECK_MAX_DETOUR_M)

    def test_two_good_bearings_are_clearable_without_extra_check(self):
        belief = self._observe(3, [1, 2])
        center, radius = enclosing_center_radius(belief.polygon())
        self.assertLessEqual(radius, self.strategy.early_clear_radius_m)
        tasks = self.strategy._build_cell_tasks((self.cell.cell_id,), self.strategy.points[3])
        self.assertTrue(any(task.kind == "clear" and task.channel == 3 for task in tasks))
        self.assertFalse(any(task.kind == "cross_view" and task.channel == 3 for task in tasks))
        self.assertLess(distance(center, self.source), 20.0)

    def test_two_nearly_collinear_bearings_create_cross_view(self):
        self._observe(4, [1, 2], source=(450.0, 10.0))
        self.strategy.position = self.strategy.points[1]
        tasks = self.strategy._build_cell_tasks((self.cell.cell_id,), self.strategy.points[2])
        self.assertTrue(any(task.kind == "cross_view" and task.channel == 4 for task in tasks))

    def test_detour_cap_rejects_better_but_illegal_geometry(self):
        belief = self.strategy.beliefs[7]
        belief.status = "active"
        belief.observations.append(((0.0, 0.0), 0.0))
        self.strategy.position = (0.0, 0.0)
        next_fixed = (1000.0, 0.0)
        legal = CheckCandidate((300.0, 100.0), "lateral")
        illegal = CheckCandidate((0.0, 1000.0), "lateral")
        chosen = self.strategy._select_admissible_candidate(
            [illegal, legal], belief, (500.0, 500.0), next_fixed
        )
        self.assertEqual(chosen, legal)
        self.assertGreater(self.strategy._detour(illegal.point, next_fixed), LOCAL_CHECK_MAX_DETOUR_M)

    def test_channel_obligation_merges_cells_without_resetting_attempts(self):
        belief = self._observe(8, [1])
        self.strategy._vertex_results[(4, 8)] = "no_signal"
        self.strategy._update_obligations((1,))
        obligation = self.strategy._obligations[8]
        obligation.forward_attempts = 1
        self.strategy._update_obligations((3,))
        self.assertIs(self.strategy._obligations[8], obligation)
        self.assertEqual(obligation.forward_attempts, 1)
        self.assertEqual(obligation.supporting_cells, {1, 3})

    def test_outside_cell_history_is_reused_and_cleared_channels_retire(self):
        belief = self._observe(5, [1])
        outside = (-600.0, 900.0)
        belief.observations.append((outside, bearing_deg(outside, self.source)))
        assessment = self.strategy.assess_cell(5, self.cell.cell_id)
        self.assertTrue(assessment.local_polygon)
        self.assertEqual(len(belief.observations), 2)
        belief.status = "cleared"
        tasks = self.strategy._build_cell_tasks((self.cell.cell_id,), self.strategy.points[3])
        self.assertFalse(any(task.channel == 5 for task in tasks))

    def test_near_vertex_is_cleared_when_its_cell_closes(self):
        belief = self.strategy.beliefs[6]
        belief.status = "located"
        belief.clear_target = self.strategy.points[0]
        self.strategy._vertex_results[(1, 6)] = "near"
        self.strategy._vertex_results[(2, 6)] = "no_signal"
        self.strategy._vertex_results[(3, 6)] = "no_signal"
        tasks = self.strategy._build_cell_tasks((self.cell.cell_id,), self.strategy.points[3])
        self.assertTrue(any(task.kind == "clear" and task.channel == 6 for task in tasks))


if __name__ == "__main__":
    unittest.main()
    fixed_start_open_route,
