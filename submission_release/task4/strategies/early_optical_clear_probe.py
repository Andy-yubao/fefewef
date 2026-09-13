from __future__ import annotations

from task4.geometry import distance, enclosing_center_radius

from .base import ChannelBelief
from .replacement_aware_clear_probe import ReplacementAwareClearProbeStrategy


class EarlyOpticalClearProbeStrategy(ReplacementAwareClearProbeStrategy):
    """Schedule a cheap optical attempt before the bearing region reaches 20 m."""

    name = "early_optical_clear_probe"

    def __init__(
        self,
        *args,
        early_clear_radius_m: float = 30.0,
        retry_shift_m: float = 5.0,
        **kwargs,
    ):
        super().__init__(*args, **kwargs)
        if early_clear_radius_m < 19.5:
            raise ValueError("early_clear_radius_m must be at least 19.5")
        if retry_shift_m < 0:
            raise ValueError("retry_shift_m must be nonnegative")
        self.early_clear_radius_m = early_clear_radius_m
        self.retry_shift_m = retry_shift_m
        self._failed_optical_targets: dict[int, list[tuple[float, float]]] = {}

    def _try_located(self, belief: ChannelBelief) -> bool:
        if len(belief.observations) < 2:
            return False
        polygon = belief.polygon()
        if not polygon:
            return False
        center, radius = enclosing_center_radius(polygon)
        if radius > self.early_clear_radius_m:
            return False
        if any(
            distance(center, attempted) < self.retry_shift_m
            for attempted in self._failed_optical_targets.get(belief.channel, [])
        ):
            return False
        belief.status = "located"
        belief.clear_target = center
        return True

    def _clear(self, api, position, channel):
        success = super()._clear(api, position, channel)
        if not success:
            self._failed_optical_targets.setdefault(channel, []).append(position)
        return success
