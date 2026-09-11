import math
import random
import unittest

from task4.geometry import angle_delta_deg, clip_bearing_wedge, enclosing_center_radius, feasible_polygon, regular_circle_polygon, serpentine_grid
from task4.search_patterns import triangular_lattice


class GeometryTests(unittest.TestCase):
    def test_wedge_wraps_zero_degrees(self):
        poly = regular_circle_polygon((0, 0), 100, sides=96, outer=True)
        clipped = clip_bearing_wedge(poly, (0, 0), 0.0, 1.0)
        self.assertTrue(clipped)
        self.assertTrue(all(p[0] >= -1e-6 for p in clipped))
        self.assertTrue(any(p[0] > 90 for p in clipped))

    def test_crossing_bearings_contain_truth(self):
        truth = (300.0, 400.0)
        observations = [
            ((0.0, 0.0), math.degrees(math.atan2(400, 300)) + 0.7),
            ((600.0, 0.0), math.degrees(math.atan2(400, -300)) - 0.6),
            ((0.0, 700.0), math.degrees(math.atan2(-300, 300)) + 0.2),
        ]
        poly = feasible_polygon(observations)
        self.assertTrue(poly)
        center, radius = enclosing_center_radius(poly)
        self.assertLessEqual(math.dist(center, truth), radius + 1e-5)
        self.assertLess(radius, 20.0)

    def test_enclosing_circle_triangle(self):
        center, radius = enclosing_center_radius([(0, 0), (2, 0), (1, math.sqrt(3))])
        self.assertAlmostEqual(center[0], 1.0, places=7)
        self.assertAlmostEqual(center[1], math.sqrt(3) / 3, places=7)
        self.assertAlmostEqual(radius, 2 / math.sqrt(3), places=7)

    def test_600m_grid_has_directional_discovery_point(self):
        rng = random.Random(2026)
        grid = serpentine_grid(1800, 600)
        for _ in range(5000):
            r = 1800 * math.sqrt(rng.random())
            a = rng.random() * 2 * math.pi
            source = (r * math.cos(a), r * math.sin(a))
            direction = rng.random() * 360
            visible = [
                p for p in grid
                if math.dist(source, p) <= 1000 + 1e-9
                and abs(angle_delta_deg(math.degrees(math.atan2(p[1] - source[1], p[0] - source[0])) % 360, direction)) <= 90 + 1e-9
            ]
            self.assertTrue(visible)

    def test_900m_triangular_lattice_has_directional_discovery_point(self):
        rng = random.Random(20260911)
        lattice = triangular_lattice(1800, 900)
        self.assertLess(len(lattice), len(serpentine_grid(1800, 600)))
        for _ in range(10000):
            radius = 1800 * math.sqrt(rng.random())
            angle = rng.random() * 2 * math.pi
            source = (radius * math.cos(angle), radius * math.sin(angle))
            direction = rng.random() * 360
            self.assertTrue(
                any(
                    math.dist(source, point) <= 1000 + 1e-9
                    and abs(
                        angle_delta_deg(
                            math.degrees(
                                math.atan2(point[1] - source[1], point[0] - source[0])
                            )
                            % 360,
                            direction,
                        )
                    )
                    <= 90 + 1e-9
                    for point in lattice
                )
            )


if __name__ == "__main__":
    unittest.main()
