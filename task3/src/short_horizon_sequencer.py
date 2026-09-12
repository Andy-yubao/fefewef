"""Honest single-step selection for READY resolve and coverage tasks."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .task_queue import Task


@dataclass(frozen=True)
class TaskPreview:
    """Known effects of one immediate action, with explicit completion semantics."""

    task: Task
    immediate_action: str
    immediate_reason: str
    immediate_operation_time_s: float
    immediate_end_position: np.ndarray
    requires_channel_switch: bool = True
    completion_known: bool = False
    estimated_completion_cost_s: float | None = None
    estimated_completion_end_position: np.ndarray | None = None

    def __post_init__(self) -> None:
        completion_fields_known = (
            self.estimated_completion_cost_s is not None
            and self.estimated_completion_end_position is not None
        )
        if self.completion_known != completion_fields_known:
            raise ValueError(
                "completion estimates must be present exactly when completion_known is true"
            )


@dataclass(frozen=True)
class SequencePreview:
    """A production decision candidate containing exactly one next task."""

    tasks: tuple[Task, ...]
    estimated_immediate_cost_s: float
    decision_end_position: np.ndarray
    feasible: bool
    immediate_action: str
    completion_known: bool
    estimated_completion_cost_s: float | None = None
    estimated_completion_end_position: np.ndarray | None = None
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
    horizon: int = 1,
) -> SequenceDecision:
    """Choose one task, then let execution update belief before replanning.

    Resolve candidates are priced only as their known immediate action. If any
    READY resolve is required before Advance, only those obligations are eligible.
    """
    if horizon != 1:
        raise ValueError("production sequencer currently supports only horizon=1")
    if speed_mps <= 0.0:
        raise ValueError("speed_mps must be positive")

    start = np.asarray(current_position, float)
    sequences: list[SequencePreview] = []
    eligible_resolves = [
        preview for preview in resolves
        if not required_before_advance or preview.task.identity in required_before_advance
    ]
    for preview in eligible_resolves:
        target = np.asarray(preview.immediate_end_position, float)
        cost = float(np.linalg.norm(target - start)) / speed_mps
        if preview.requires_channel_switch and preview.task.channel != current_channel:
            cost += switch_s
        cost += preview.immediate_operation_time_s
        sequences.append(SequencePreview(
            tasks=(preview.task,),
            estimated_immediate_cost_s=cost,
            decision_end_position=target.copy(),
            feasible=True,
            immediate_action=preview.immediate_action,
            completion_known=preview.completion_known,
            estimated_completion_cost_s=preview.estimated_completion_cost_s,
            estimated_completion_end_position=(
                None
                if preview.estimated_completion_end_position is None
                else np.asarray(preview.estimated_completion_end_position, float).copy()
            ),
        ))

    if not required_before_advance and advance is not None and advance_position is not None:
        target = np.asarray(advance_position, float)
        cost = float(np.linalg.norm(target - start)) / speed_mps
        sequences.append(SequencePreview(
            tasks=(advance,),
            estimated_immediate_cost_s=cost,
            decision_end_position=target.copy(),
            feasible=True,
            immediate_action="ADVANCE",
            completion_known=True,
            estimated_completion_cost_s=cost,
            estimated_completion_end_position=target.copy(),
        ))

    if not sequences:
        return SequenceDecision(None, None, ())

    chosen = min(
        sequences,
        key=lambda sequence: (sequence.estimated_immediate_cost_s, sequence.label),
    )
    return SequenceDecision(chosen.tasks[0], chosen, tuple(sequences))
