from __future__ import annotations

from .active import ActiveStrategy


class ReacquireStrategy(ActiveStrategy):
    """Active strategy that keeps trying mirrored/arc points after signal loss."""

    name = "reacquire"
    max_local_measurements = 12
    continue_after_loss = True
