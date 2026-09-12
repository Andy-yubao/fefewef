"""Completion-level preview and short-horizon route sequencing.

A task is committed on what finishing it is predicted to cost and where it is
predicted to end - not on the price of its next action. A preview that cannot
honestly reach completion is marked ``UNKNOWN`` and takes no part in sequencing;
commitment then falls back to the sweep planner's geometric ``order_key``.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from itertools import permutations

import numpy as np

from .task_queue import Task


class CompletionCertainty(str, Enum):
    """How much a completion prediction can be trusted."""

    EXACT = "exact"          # the next action is the completion action
    ESTIMATED = "estimated"  # endpoint from belief, cost from the resolver's terminal geometry
    UNKNOWN = "unknown"      # no admissible completion endpoint; make no claim


@dataclass(frozen=True)
class CompletionPreview:
    """Where a task is predicted to finish, and what the remaining work costs.

    ``operation_s`` is the task's own remaining measurement and optical/laser
    time; travel and the channel switch depend on where and how the task is
    entered, so they are priced per leg rather than stored here.

    ``endpoint_uncertainty_m`` is where the endpoint itself comes from: zero when
    the next action is the completion action, otherwise the belief certificate
    that fixed it. It is reported so a decision can refuse to reorder tasks whose
    completion points are closer together than the belief that predicts them.
    """

    certainty: CompletionCertainty
    endpoint: np.ndarray | None = None
    operation_s: float = 0.0
    requires_measure: bool = True
    endpoint_uncertainty_m: float = float("inf")
    reason: str = ""

    def __post_init__(self) -> None:
        if (self.certainty is not CompletionCertainty.UNKNOWN) != (self.endpoint is not None):
            raise ValueError(
                "a completion endpoint must be present exactly when the prediction is known"
            )

    @property
    def known(self) -> bool:
        return self.certainty is not CompletionCertainty.UNKNOWN


UNKNOWN_COMPLETION = CompletionPreview(CompletionCertainty.UNKNOWN, reason="not_predicted")


@dataclass(frozen=True)
class TaskPreview:
    """One task: its next action, and its completion when that can be predicted.

    ``immediate_end_position`` is a geometric fact about the next action and
    ``immediate_operation_time_s`` is that action's own duration. Neither is a
    completion endpoint or a completion cost.
    """

    task: Task
    immediate_action: str
    immediate_reason: str
    immediate_operation_time_s: float
    immediate_end_position: np.ndarray
    requires_channel_switch: bool = True
    completion: CompletionPreview = UNKNOWN_COMPLETION


@dataclass(frozen=True)
class SequenceLeg:
    """One task inside a candidate ordering, priced from the state it would start in."""

    task: Task
    action: str
    cost_s: float | None
    completion: CompletionPreview
    endpoint: np.ndarray | None


@dataclass(frozen=True)
class SequencePreview:
    """A candidate ordering of one to three tasks, optionally ending at a milestone."""

    legs: tuple[SequenceLeg, ...]
    immediate_cost_s: float
    cost_s: float | None
    end_position: np.ndarray | None
    feasible: bool
    reason: str | None = None
    # Summed belief uncertainty of the endpoints this sequence commits to, in
    # seconds of travel. A cost advantage smaller than this is inside the error
    # of the estimates that produced it and is not evidence of anything.
    uncertainty_s: float = float("inf")

    @property
    def tasks(self) -> tuple[Task, ...]:
        return tuple(leg.task for leg in self.legs)

    @property
    def label(self) -> str:
        return " -> ".join(task.label for task in self.tasks)


@dataclass(frozen=True)
class SequenceDecision:
    chosen_task: Task | None
    chosen_sequence: SequencePreview | None
    sequences: tuple[SequencePreview, ...]
    basis: str
    # Which eligible tasks took part in ordering, and which carried no completion
    # prediction. Logged so a horizon or accuracy cap is never silent.
    sequenced: tuple[Task, ...] = ()
    unpriced: tuple[Task, ...] = ()


def task_commitment_key(task: Task) -> tuple:
    """Stable commitment order for one task: the sweep planner's geometric key.

    The label is a deterministic last resort for candidates that share an order
    key. Nothing about the next action appears here: an immediate cost cannot
    rank a task whose completion is unknown.
    """
    return (task.order_key, task.label)


def commitment_key(sequence: SequencePreview) -> tuple:
    """Stable commitment order for a candidate containing one next task."""
    return task_commitment_key(sequence.tasks[0])


def completion_leg_cost(
    preview: TaskPreview,
    pose: np.ndarray,
    channel_held: int | None,
    speed_mps: float,
    switch_s: float,
) -> float:
    """Price finishing ``preview``'s task, entered at ``pose`` holding ``channel_held``.

    Only the two state-dependent terms are recomputed for a hypothetical entry
    state: travel and the channel switch. The operation term is the task's own
    remaining work and does not depend on how the task is entered.
    """
    completion = preview.completion
    if not completion.known:
        raise ValueError("cannot price a task whose completion is unknown")
    endpoint = np.asarray(completion.endpoint, float)
    cost = float(np.linalg.norm(endpoint - np.asarray(pose, float))) / speed_mps
    if completion.requires_measure and preview.task.channel != channel_held:
        cost += switch_s
    return cost + completion.operation_s


def _immediate_cost(
    preview: TaskPreview, pose: np.ndarray, channel_held: int | None,
    speed_mps: float, switch_s: float,
) -> float:
    """Known price of the task's next action only. Recorded, never used to rank."""
    travel = float(np.linalg.norm(
        np.asarray(preview.immediate_end_position, float) - np.asarray(pose, float)
    )) / speed_mps
    switch = (
        switch_s
        if preview.requires_channel_switch and preview.task.channel != channel_held
        else 0.0
    )
    return travel + switch + preview.immediate_operation_time_s


def _single_task_sequences(
    eligible: list[TaskPreview],
    advance: Task | None,
    terminator: np.ndarray | None,
    pose: np.ndarray,
    channel_held: int | None,
    speed_mps: float,
    switch_s: float,
) -> list[SequencePreview]:
    """One-task candidates: every eligible Resolve, plus Advance when it is allowed."""
    sequences: list[SequencePreview] = []
    for preview in eligible:
        completion = preview.completion
        endpoint = (
            None if completion.endpoint is None
            else np.asarray(completion.endpoint, float).copy()
        )
        sequences.append(SequencePreview(
            legs=(SequenceLeg(
                task=preview.task,
                action=preview.immediate_action,
                cost_s=(
                    completion_leg_cost(preview, pose, channel_held, speed_mps, switch_s)
                    if completion.known else None
                ),
                completion=completion,
                endpoint=endpoint,
            ),),
            immediate_cost_s=_immediate_cost(preview, pose, channel_held, speed_mps, switch_s),
            cost_s=(
                completion_leg_cost(preview, pose, channel_held, speed_mps, switch_s)
                if completion.known else None
            ),
            end_position=endpoint,
            feasible=True,
        ))
    if advance is not None and terminator is not None:
        # The coverage vertex is where the immediate movement ends and that
        # movement cost is known; the whole AdvanceCoverage cost is not.
        sequences.append(SequencePreview(
            legs=(SequenceLeg(
                task=advance,
                action="ADVANCE",
                cost_s=float(np.linalg.norm(terminator - pose)) / speed_mps,
                completion=UNKNOWN_COMPLETION,
                endpoint=terminator.copy(),
            ),),
            immediate_cost_s=float(np.linalg.norm(terminator - pose)) / speed_mps,
            cost_s=float(np.linalg.norm(terminator - pose)) / speed_mps,
            end_position=terminator.copy(),
            feasible=True,
        ))
    return sequences


def _rollout(
    order: tuple[TaskPreview, ...],
    advance: Task | None,
    terminator: np.ndarray | None,
    pose: np.ndarray,
    channel_held: int | None,
    speed_mps: float,
    switch_s: float,
) -> SequencePreview:
    """Price one ordering, re-deriving every leg from the previous leg's end state.

    Each leg is entered at the previous completion endpoint holding the previous
    task's channel, so travel and switching are recomputed rather than reused.
    When a milestone is available it is appended as a positional term: the
    ordering that ends nearer the next milestone is cheaper.
    """
    legs: list[SequenceLeg] = []
    position = pose
    channel = channel_held
    total = 0.0
    immediate = 0.0
    uncertainty = 0.0
    for index, preview in enumerate(order):
        cost = completion_leg_cost(preview, position, channel, speed_mps, switch_s)
        if index == 0:
            immediate = _immediate_cost(preview, position, channel, speed_mps, switch_s)
        endpoint = np.asarray(preview.completion.endpoint, float).copy()
        legs.append(SequenceLeg(
            task=preview.task,
            action=preview.immediate_action,
            cost_s=cost,
            completion=preview.completion,
            endpoint=endpoint,
        ))
        position = endpoint
        channel = preview.task.channel
        total += cost
        uncertainty += preview.completion.endpoint_uncertainty_m / speed_mps
    if advance is not None and terminator is not None:
        travel = float(np.linalg.norm(terminator - position)) / speed_mps
        legs.append(SequenceLeg(
            task=advance,
            action="ADVANCE",
            cost_s=travel,
            completion=UNKNOWN_COMPLETION,
            endpoint=terminator.copy(),
        ))
        position = terminator.copy()
        total += travel
    return SequencePreview(
        legs=tuple(legs),
        immediate_cost_s=immediate,
        cost_s=total,
        end_position=position.copy(),
        feasible=True,
        uncertainty_s=uncertainty,
    )


def choose_short_horizon_sequence(
    current_position: np.ndarray,
    current_channel: int | None,
    resolves: list[TaskPreview],
    advance: Task | None,
    advance_position: np.ndarray | None,
    required_before_advance: set[tuple],
    speed_mps: float,
    switch_s: float,
    horizon: int = 3,
) -> SequenceDecision:
    """Sequence the eligible Resolves, or fall back to the stable order_key.

    Every eligible Resolve that can be priced to completion is ordered against
    the others (at most ``horizon`` of them, fully permuted) and the first task
    of the cheapest ordering is committed. If fewer than two completions are
    trustworthy, no rollout is fabricated and commitment reverts to the sweep
    planner's ``order_key``. If any READY resolve is required before Advance,
    only those obligations are eligible.
    """
    if horizon < 1:
        raise ValueError("horizon must be positive")
    if speed_mps <= 0.0:
        raise ValueError("speed_mps must be positive")

    pose = np.asarray(current_position, float)
    eligible = [
        preview for preview in resolves
        if not required_before_advance or preview.task.identity in required_before_advance
    ]
    advance_allowed = (
        not required_before_advance and advance is not None and advance_position is not None
    )
    terminator = np.asarray(advance_position, float) if advance_allowed else None
    basis_prefix = "required_" if required_before_advance else ""

    # The CW/CCW sweep is a hard constraint, not a score term: only Resolves that
    # already precede Advance under the macro rule may be reordered among
    # themselves, so sequencing can never pull work back across the frontier.
    orderable = [
        preview for preview in eligible
        if preview.completion.known
        and (advance is None or preview.task.order_key < advance.order_key)
    ]
    sequencable = orderable[:horizon]
    unpriced = tuple(
        preview.task for preview in eligible if not preview.completion.known
    )

    reviewed: tuple[SequencePreview, ...] = ()
    fallback = "order_key"
    if len(sequencable) >= 2:
        orderings = tuple(
            _rollout(order, advance if advance_allowed else None, terminator,
                     pose, current_channel, speed_mps, switch_s)
            for order in permutations(sequencable)
        )
        chosen = min(orderings, key=lambda sequence: (sequence.cost_s, sequence.label))
        # The rule being overridden is order_key, so that is what the evidence has
        # to beat: the cheapest ordering that starts with the task the sweep
        # planner would have committed on its own.
        incumbent_task = min(
            (preview.task for preview in sequencable), key=task_commitment_key
        )
        incumbent = min(
            (sequence for sequence in orderings if sequence.tasks[0] == incumbent_task),
            key=lambda sequence: (sequence.cost_s, sequence.label),
        )
        # Override only when the predicted gain exceeds the summed belief error
        # of the endpoints the ordering rests on. Otherwise the same tasks go
        # back to order_key instead of being shuffled on noise. The rejected
        # comparison is still reported, so the decision stays auditable.
        if chosen.tasks[0] != incumbent_task and (
            chosen.cost_s + chosen.uncertainty_s >= incumbent.cost_s
        ):
            reviewed = orderings
            fallback = "order_key_uncertain_completion"
        else:
            return SequenceDecision(
                chosen.tasks[0], chosen, orderings, f"{basis_prefix}completion_sequence",
                sequenced=tuple(preview.task for preview in sequencable),
                unpriced=unpriced,
            )

    singles = _single_task_sequences(
        eligible, advance if advance_allowed else None, terminator,
        pose, current_channel, speed_mps, switch_s,
    )
    if not singles:
        return SequenceDecision(None, None, reviewed, "no_candidate", unpriced=unpriced)
    chosen = min(singles, key=commitment_key)
    return SequenceDecision(
        chosen.tasks[0],
        None if reviewed else chosen,
        reviewed or tuple(singles),
        f"{basis_prefix}{fallback}",
        sequenced=tuple(preview.task for preview in sequencable),
        unpriced=unpriced,
    )
