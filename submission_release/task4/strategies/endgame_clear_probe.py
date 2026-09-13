from __future__ import annotations

from task4.client import RobotAPI
from task4.geometry import distance

from .clear_probe import ClearProbeStrategy


class EndgameClearProbeStrategy(ClearProbeStrategy):
    """Choose residual active channels by nearest route-compatible local probe."""

    name = "endgame_clear_probe"

    def _resolve_active_channels(self, api: RobotAPI) -> None:
        helper = self._make_reacquisition_helper()
        pending = {
            channel
            for channel, belief in self.beliefs.items()
            if belief.status == "active"
        }
        while pending:
            def next_probe_distance(channel: int) -> tuple[float, int]:
                belief = self.beliefs[channel]
                candidate = next(
                    (
                        point
                        for point in helper._candidate_points(belief)
                        if all(
                            distance(point, attempted) >= 20.0
                            for attempted in belief.attempted_positions
                        )
                    ),
                    None,
                )
                return (
                    distance(helper.position, candidate) if candidate is not None else float("inf"),
                    channel,
                )

            channel = min(pending, key=next_probe_distance)
            pending.remove(channel)
            helper._localize(api, channel)
        self.position, self.virtual_time_s = helper.position, helper.virtual_time_s
