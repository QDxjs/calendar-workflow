"""Shared page and cancellation types used across calendar workflows."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from pathlib import Path
from typing import Union


WEEKDAYS = ["星期一", "星期二", "星期三", "星期四", "星期五", "星期六", "星期日"]


@dataclass(frozen=True)
class CalendarPage:
    target_date: date
    layout_selection: str
    layout: str
    quote: str
    source: str
    quote_id: str = ""

    @property
    def weekday(self) -> str:
        return WEEKDAYS[self.target_date.weekday()]


@dataclass(frozen=True)
class GenerationPlan:
    """One immutable selection shared by the desktop sample and batch export."""

    pages: tuple[CalendarPage, ...]
    seed: int | None


class BatchCancelled(Exception):
    """Signal that a caller cancelled generation before publishing output."""


@dataclass(frozen=True)
class GenerationProgress:
    completed: int
    total: int


@dataclass(frozen=True)
class GenerationCompleted:
    output_dir: Path


@dataclass(frozen=True)
class GenerationCancelled:
    pass


@dataclass(frozen=True)
class GenerationFailed:
    error: Exception


@dataclass(frozen=True)
class PreviewCompleted:
    images: tuple[tuple[str, bytes], ...]


GenerationEvent = Union[
    GenerationProgress,
    GenerationCompleted,
    GenerationCancelled,
    GenerationFailed,
    PreviewCompleted,
]
