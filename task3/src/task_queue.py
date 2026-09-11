"""Committed active task and freely reorderable waiting tasks."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import Iterable


class TaskKind(str, Enum):
    RESOLVE_SOURCE = "ResolveSource"
    ADVANCE_COVERAGE = "AdvanceCoverage"


@dataclass(frozen=True)
class Task:
    kind: TaskKind
    channel: int | None = None
    vertex: int | None = None
    order_key: tuple = field(default_factory=tuple, compare=False, repr=False)

    def __post_init__(self) -> None:
        if self.kind == TaskKind.RESOLVE_SOURCE and self.channel is None:
            raise ValueError("ResolveSource requires a channel")
        if self.kind == TaskKind.ADVANCE_COVERAGE and self.vertex is None:
            raise ValueError("AdvanceCoverage requires a vertex")

    @property
    def label(self) -> str:
        if self.kind == TaskKind.RESOLVE_SOURCE:
            return f"Resolve ch{self.channel}"
        return f"Advance V{self.vertex}"

    @property
    def identity(self) -> tuple[TaskKind, int | None]:
        target = self.channel if self.kind == TaskKind.RESOLVE_SOURCE else self.vertex
        return self.kind, target


class TaskQueue:
    """ACTIVE is committed; only WAITING is rebuilt after observations."""

    def __init__(self) -> None:
        self.active: Task | None = None
        self.waiting: list[Task] = []

    def rebuild(self, tasks: Iterable[Task]) -> None:
        active_identity = self.active.identity if self.active is not None else None
        unique: dict[tuple[TaskKind, int | None], Task] = {}
        for task in tasks:
            if task.identity != active_identity:
                unique[task.identity] = task
        self.waiting = sorted(unique.values(), key=lambda task: task.order_key)

    def select_active(self) -> Task | None:
        if self.active is None and self.waiting:
            self.active = self.waiting.pop(0)
        return self.active

    def complete_active(self) -> Task | None:
        completed = self.active
        self.active = None
        return completed

    def labels(self) -> list[str]:
        return [task.label for task in self.waiting]
