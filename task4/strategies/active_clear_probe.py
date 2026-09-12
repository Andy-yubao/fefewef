from __future__ import annotations

from task4.client import RobotAPI

from .clear_probe import ClearProbeStrategy


class ActiveClearProbeStrategy(ClearProbeStrategy):
    """Use every clear site for active-channel geometry without scanning unseen channels."""

    name = "active_clear_probe"

    def _after_clear(self, api: RobotAPI, point, remaining) -> None:
        if not remaining:
            return
        replaceable = self._choose_replacements(point, remaining)
        for candidate in replaceable:
            remaining.remove(candidate)
        if replaceable:
            channels = self._channel_scan_order({"located", "cleared"})
        else:
            channels = [
                channel
                for channel in self._channel_scan_order({"unseen", "located", "cleared"})
                if self.beliefs[channel].status == "active"
            ]
        self._probe_channels_at_clear(api, point, channels)
