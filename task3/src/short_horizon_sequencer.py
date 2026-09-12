"""Small deterministic route sequencer for READY resolve tasks."""

from __future__ import annotations

from dataclasses import dataclass
from itertools import permutations

import numpy as np

from .task_queue import Task


@dataclass(frozen=True)
class TaskPreview:
    """Deterministic proxy for the next useful action of a resolve task."""

    task: Task
    operation_time_s: float
    end_position: np.ndarray
    requires_channel_switch: bool = True


@dataclass(frozen=True)
class SequencePreview:
    tasks: tuple[Task, ...]
    estimated_cost_s: float | None
    estimated_end_position: np.ndarray
    feasible: bool
    reason: str | None = None

    @property
    def label(self) -> str:
        return " -> ".join(task.label for task in self.tasks)


@dataclass(frozen=True)
class SequenceDecision:
    chosen_task: Task | None
    chosen_sequence: SequencePreview | None
    sequences: tuple[SequencePreview, ...]


def choose_short_horizon_sequence(
    current_position: np.ndarray,
    current_channel: int | None,
    resolves: list[TaskPreview],
    advance: Task | None,
    advance_position: np.ndarray | None,
    required_before_advance: set[tuple],
    speed_mps: float,
    switch_s: float,
    horizon: int = 2,
) -> SequenceDecision:
    """Choose the cheapest at-most-two-resolve route using time as its cost.

    A resolve preview represents the deterministic next useful service action under
    current belief.  If not every required current-sector task fits in the horizon,
    Advance is deliberately deferred and the best resolve prefix is selected.
    """
    if horizon < 1:
        raise ValueError("horizon must be positive")
    if speed_mps <= 0.0:
        raise ValueError("speed_mps must be positive")

    start = np.asarray(current_position, float)
    previews = resolves[:3]
    by_identity = {preview.task.identity: preview for preview in previews}
    sequences: list[SequencePreview] = []

    def evaluate(order: tuple[TaskPreview, ...], include_advance: bool) -> SequencePreview:
        position = start.copy()
        channel = current_channel
        cost = 0.0
        tasks: list[Task] = []
        for preview in order:
            target = np.asarray(preview.end_position, float)
            cost += float(np.linalg.norm(target - position)) / speed_mps
            if preview.requires_channel_switch and preview.task.channel != channel:
                cost += switch_s
            cost += preview.operation_time_s
            position = target.copy()
            channel = preview.task.channel
            tasks.append(preview.task)
        if include_advance:
            assert advance is not None and advance_position is not None
            tasks.append(advance)
            covered = {preview.task.identity for preview in order}
            missing = required_before_advance - covered
            if missing:
                labels = ", ".join(
                    by_identity[item].task.label if item in by_identity else str(item)
                    for item in sorted(missing, key=str)
                )
                return SequencePreview(
                    tuple(tasks), None, position, False,
                    f"would strand required task(s): {labels}",
                )
            target = np.asarray(advance_position, float)
            cost += float(np.linalg.norm(target - position)) / speed_mps
            position = target.copy()
        return SequencePreview(tuple(tasks), cost, position, True)

    max_length = min(horizon, len(previews))
    include_advance = advance is not None and advance_position is not None
    if include_advance and not required_before_advance:
        sequences.append(evaluate((), True))
    for length in range(1, max_length + 1):
        for order in permutations(previews, length):
            sequences.append(evaluate(order, include_advance))

    feasible = [sequence for sequence in sequences if sequence.feasible and sequence.tasks]
    if not feasible and required_before_advance and previews:
        # More required work than fits in the horizon: compare resolve-only prefixes
        # and replan after the selected committed task completes.
        for length in range(1, max_length + 1):
            for order in permutations(previews, length):
                sequences.append(evaluate(order, False))
        feasible = [sequence for sequence in sequences if sequence.feasible and sequence.tasks]
    if not feasible:
        return SequenceDecision(None, None, tuple(sequences))

    chosen = min(
        feasible,
        key=lambda sequence: (
            float(sequence.estimated_cost_s),
            sequence.label,
        ),
    )
    chosen_task = next(
        (task for task in chosen.tasks if task.identity in by_identity),
        chosen.tasks[0] if chosen.tasks else None,
    )
    return SequenceDecision(chosen_task, chosen, tuple(sequences))
