"""Run calendar generation jobs without depending on desktop widgets."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path
import queue
import threading

from calendar_models import (
    BatchCancelled,
    CalendarPage,
    GenerationCancelled,
    GenerationCompleted,
    GenerationEvent,
    GenerationFailed,
    GenerationProgress,
)
from generate import write_batch


PagePreparation = Callable[[], tuple[list[CalendarPage], int | None]]


def run_generation_job(
    prepare: PagePreparation,
    output_dir: Path,
    cancel_event: threading.Event,
    events: queue.Queue[GenerationEvent],
) -> None:
    try:
        def check_cancel() -> None:
            if cancel_event.is_set():
                raise BatchCancelled()

        def progress(completed: int, total: int) -> None:
            check_cancel()
            events.put(GenerationProgress(completed, total))

        pages, seed = prepare()
        write_batch(pages, output_dir, seed=seed, on_progress=progress, check_cancel=check_cancel)
        events.put(GenerationCompleted(output_dir))
    except BatchCancelled:
        events.put(GenerationCancelled())
    except Exception as exc:
        events.put(GenerationFailed(exc))
