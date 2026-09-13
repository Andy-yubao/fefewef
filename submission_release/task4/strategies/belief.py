from __future__ import annotations

from dataclasses import dataclass
import math
import random

from task4.client import RobotAPI
from task4.geometry import angle_delta_deg, bearing_deg, distance, enclosing_center_radius

from .base import ChannelBelief
from .opportunistic import OpportunisticClearStrategy


@dataclass(frozen=True)
class VisibilityParticle:
    x: float
    y: float
    radius: float
    directional: bool
    direction_deg: float

    def visible_from(self, point: tuple[float, float]) -> bool:
        if math.hypot(point[0] - self.x, point[1] - self.y) > self.radius:
            return False
        if not self.directional:
            return True
        from_source = math.degrees(math.atan2(point[1] - self.y, point[0] - self.x)) % 360.0
        return abs(angle_delta_deg(from_source, self.direction_deg)) <= 90.0


class BeliefSearchStrategy(OpportunisticClearStrategy):
    """Particle visibility belief with a binary-EIG waypoint ordering surrogate."""

    name = "belief"

    def __init__(
        self,
        grid_spacing: float = 600.0,
        grid_half_extent: float = 1800.0,
        lattice_spacing: float = 760.0,
        clear_detour_threshold_m: float = 1500.0,
        particle_count: int = 1600,
        belief_seed: int = 20260911,
        assumed_directional_probability: float = 0.5,
        belief_travel_weight: float = 16.0,
    ):
        super().__init__(
            grid_spacing,
            grid_half_extent,
            lattice_spacing,
            clear_detour_threshold_m,
        )
        self.particle_count = particle_count
        self.belief_seed = belief_seed
        self.assumed_directional_probability = assumed_directional_probability
        self.belief_travel_weight = belief_travel_weight
        self._particles = self._make_particles()
        self._alive_mask = (1 << len(self._particles)) - 1
        self._visibility_masks = self._make_visibility_masks()

    def _make_particles(self) -> list[VisibilityParticle]:
        rng = random.Random(self.belief_seed)
        particles = []
        for _ in range(self.particle_count):
            radius_from_origin = self.grid_half_extent * math.sqrt(rng.random())
            angle = rng.random() * 2 * math.pi
            particles.append(
                VisibilityParticle(
                    x=radius_from_origin * math.cos(angle),
                    y=radius_from_origin * math.sin(angle),
                    radius=rng.uniform(1000.0, 1500.0),
                    directional=rng.random() < self.assumed_directional_probability,
                    direction_deg=rng.random() * 360.0,
                )
            )
        return particles

    def _make_visibility_masks(self) -> dict[tuple[float, float], int]:
        masks = {}
        for point in self._search_waypoints():
            mask = 0
            for index, particle in enumerate(self._particles):
                if particle.visible_from(point):
                    mask |= 1 << index
            masks[point] = mask
        return masks

    @staticmethod
    def _binary_entropy(probability: float) -> float:
        if probability <= 0.0 or probability >= 1.0:
            return 0.0
        return -probability * math.log(probability) - (1 - probability) * math.log(1 - probability)

    def _active_geometry_context(self) -> list[tuple[tuple[float, float], list[float]]]:
        context = []
        for belief in self.beliefs.values():
            if belief.status != "active" or not belief.observations:
                continue
            polygon = belief.polygon()
            if not polygon:
                continue
            center, _ = enclosing_center_radius(polygon)
            context.append(
                (center, [bearing_deg(station, center) for station, _ in belief.observations])
            )
        return context

    @staticmethod
    def _active_geometry_value(
        point: tuple[float, float],
        context: list[tuple[tuple[float, float], list[float]]],
    ) -> float:
        value = 0.0
        for center, previous_bearings in context:
            if distance(point, center) > 1500.0:
                continue
            proposed_bearing = bearing_deg(point, center)
            best_crossing = max(
                abs(
                    math.sin(
                        math.radians(
                            angle_delta_deg(proposed_bearing, previous_bearing)
                        )
                    )
                )
                for previous_bearing in previous_bearings
            )
            value += best_crossing
        return value

    def _select_waypoint(self, remaining: list[tuple[float, float]]) -> tuple[float, float]:
        unseen_count = sum(belief.status == "unseen" for belief in self.beliefs.values())
        alive_count = self._alive_mask.bit_count()
        if unseen_count == 0 or alive_count == 0:
            return super()._select_waypoint(remaining)
        active_context = self._active_geometry_context()
        return max(
            remaining,
            key=lambda point: self._score_waypoint(point, unseen_count, alive_count, active_context),
        )

    def _score_waypoint(self, point, unseen_count, alive_count, active_context) -> float:
        visible = (self._alive_mask & self._visibility_masks[point]).bit_count()
        probability = visible / alive_count
        information = self._binary_entropy(probability)
        search_value = unseen_count * (probability + 0.6 * information)
        geometry_value = 1.5 * self._active_geometry_value(point, active_context)
        travel_penalty = self.belief_travel_weight * distance(self.position, point) / self.lattice_spacing
        return search_value + geometry_value - travel_penalty

    def _after_waypoint(
        self,
        api: RobotAPI,
        waypoint: tuple[float, float],
        remaining: list[tuple[float, float]],
    ) -> None:
        if any(belief.status == "unseen" for belief in self.beliefs.values()):
            self._alive_mask &= ~self._visibility_masks[waypoint]
        super()._after_waypoint(api, waypoint, remaining)
