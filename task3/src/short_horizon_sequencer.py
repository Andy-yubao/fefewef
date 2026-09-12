"""Honest single-step commitment for READY resolve and coverage tasks.

A task is committed by the sweep planner's stable geometric ``order_key``, not
by the price of its next action.  ``estimated_immediate_cost_s`` describes one
action - it is recorded, and it is what execution performs next - but it is not
evidence about the cost of a task whose *completion* is unknown.  An
intermediate MEASURE that happens to sit on the robot's own pose therefore
costs 5-6 s without ever becoming a task-level commitment argument."""

from __future__ import annotations

from dataclasses import dataclass
import numpy as np

from .task_queue import Task


@dataclass(frozen=True)
class TaskPreview:
    """Known effects of one immediate action, with explicit completion semantics.

    ``immediate_end_position`` is a geometric fact about the next action and
    ``immediate_operation_time_s`` is that action's own duration. Neither is
    promoted to a completion endpoint or completion cost unless the next action
    really does finish the task, which is what ``completion_known`` records.
    """

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
    """A production decision candidate containing exactly one next task.

    ``estimated_immediate_cost_s`` is the known cost of the next action only
    (movement, channel switch, operation), and ``decision_end_position`` is where
    that action ends. Both are facts about the next step, never a claim that the
    task finishes there.
    """

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


def commitment_key(sequence: SequencePreview) -> tuple:
    """Stable task-level commitment order for one candidate.

    ``estimated_immediate_cost_s`` prices a single action, so it cannot rank
    tasks whose completion is unknown.  Those fall back to the sweep planner's
    geometric ``order_key``; the label is a deterministic last resort for
    candidates that share an order key.
    """
    return (sequence.tasks[0].order_key, sequence.label)


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

    Every candidate carries an honest immediate preview; commitment itself
    follows ``commitment_key``. If any READY resolve is required before Advance,
    only those obligations are eligible.
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
        # The coverage vertex fixes where the immediate movement ends, and that
        # movement cost is known.  It is not the whole AdvanceCoverage cost:
        # execution also runs en-route observations and an unknown-channel scan.
        target = np.asarray(advance_position, float)
        sequences.append(SequencePreview(
            tasks=(advance,),
            estimated_immediate_cost_s=float(np.linalg.norm(target - start)) / speed_mps,
            decision_end_position=target.copy(),
            feasible=True,
            immediate_action="ADVANCE",
            completion_known=False,
        ))

    if not sequences:
        return SequenceDecision(None, None, ())

    chosen = min(sequences, key=commitment_key)
    return SequenceDecision(chosen.tasks[0], chosen, tuple(sequences))
