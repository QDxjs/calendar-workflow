"""Render temporary desktop previews through the same pipeline as batch export."""

from __future__ import annotations

from pathlib import Path
import queue
import tempfile
import threading

from calendar_models import (
    BatchCancelled, CalendarPage, GenerationCancelled, GenerationEvent,
    GenerationFailed, GenerationProgress, PreviewCompleted,
)
from generate import RENDERERS, metadata, svg_to_png, validate_rendering


def run_preview_job(
    pages: tuple[CalendarPage, ...],
    cancel_event: threading.Event,
    events: queue.Queue[GenerationEvent],
) -> None:
    """Return PNG bytes only after temporary files have been removed."""
    def check_cancel() -> None:
        if cancel_event.is_set():
            raise BatchCancelled()

    try:
        images: list[tuple[str, bytes]] = []
        with tempfile.TemporaryDirectory(prefix="calendar-preview-") as scratch:
            root = Path(scratch)
            for index, page in enumerate(pages):
                check_cancel()
                validate_rendering([page], check_cancel=check_cancel)
                svg_path, png_path = root / "page.svg", root / "page.png"
                svg_path.write_text(RENDERERS[page.layout](metadata(
                    page.target_date, page.layout, page.quote, page.source, page.creator,
                )), encoding="utf-8")
                svg_to_png(svg_path, png_path)
                check_cancel()
                images.append((page.layout, png_path.read_bytes()))
                events.put(GenerationProgress(index + 1, len(pages)))
        check_cancel()
        events.put(PreviewCompleted(tuple(images)))
    except BatchCancelled:
        events.put(GenerationCancelled())
    except Exception as exc:
        events.put(GenerationFailed(exc))
