"""Regression coverage for preview rendering and its terminal events."""

from __future__ import annotations

from datetime import date
from functools import partial
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import Mock, patch

import calendar_preview
from calendar_models import (
    CalendarPage, GenerationCancelled, GenerationEvent, GenerationFailed,
    GenerationProgress, PreviewCompleted,
)
from generate import write_batch
from quote_library import builtin_quotes


class PreviewTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        quote = builtin_quotes()[0]
        # A single date allows every layout to use the same quote in one batch.
        cls.pages = tuple(CalendarPage(date(2027, 1, 1), layout, layout, **quote) for layout in "ABCDEFGHI")

    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.preview_root = self.root / "previews"
        self.preview_root.mkdir()

    def collect_events(
        self, pages: tuple[CalendarPage, ...], cancellation: threading.Event | None = None,
    ) -> list[GenerationEvent]:
        events: queue.Queue[GenerationEvent] = queue.Queue()
        pending_paths: list[Path] = []
        put = events.put

        def observe_event(event: GenerationEvent) -> None:
            # A consumer can see a terminal event before the worker returns.
            if not isinstance(event, GenerationProgress):
                pending_paths.extend(self.preview_root.iterdir())
            put(event)

        factory = partial(tempfile.TemporaryDirectory, dir=self.preview_root)
        with (
            patch.object(calendar_preview.tempfile, "TemporaryDirectory", side_effect=factory),
            patch.object(events, "put", side_effect=observe_event),
        ):
            calendar_preview.run_preview_job(pages, cancellation or threading.Event(), events)

        self.assertEqual(pending_paths, [], "a terminal event was sent before preview cleanup")
        self.assertEqual(list(self.preview_root.iterdir()), [], "preview left temporary files behind")
        return [events.get_nowait() for _ in range(events.qsize())]

    def test_all_nine_layouts_match_batch_rendering(self) -> None:
        batch = self.root / "batch"
        self.assertEqual(write_batch(list(self.pages), batch, on_progress=lambda *_: None), 9)

        preview_svgs: list[bytes] = []
        rasterize = calendar_preview.svg_to_png

        def record_svg(svg_path: Path, png_path: Path) -> None:
            preview_svgs.append(svg_path.read_bytes())
            rasterize(svg_path, png_path)

        with patch.object(calendar_preview, "svg_to_png", side_effect=record_svg):
            received = self.collect_events(self.pages)

        self.assertEqual(len(received), len(self.pages) + 1)
        *progress, completed = received
        self.assertEqual(progress, [GenerationProgress(index, len(self.pages)) for index in range(1, 10)])
        self.assertIsInstance(completed, PreviewCompleted)
        self.assertEqual(tuple(layout for layout, _ in completed.images), tuple(page.layout for page in self.pages))
        self.assertEqual(len(preview_svgs), len(self.pages))

        for page, (_, png_bytes), svg_bytes in zip(self.pages, completed.images, preview_svgs):
            with self.subTest(layout=page.layout):
                basename = f"{page.target_date.isoformat()}_layout-{page.layout}"
                self.assertEqual(svg_bytes, (batch / "svg" / f"{basename}.svg").read_bytes())
                self.assertIsInstance(png_bytes, bytes)
                self.assertEqual(png_bytes, (batch / "png" / f"{basename}.png").read_bytes())

    def test_cancel_after_render_cleans_up_without_completing(self) -> None:
        cancellation = threading.Event()
        rasterize = calendar_preview.svg_to_png

        def render_then_cancel(svg_path: Path, png_path: Path) -> None:
            rasterize(svg_path, png_path)
            cancellation.set()

        with patch.object(calendar_preview, "svg_to_png", side_effect=render_then_cancel) as render:
            received = self.collect_events(self.pages[:2], cancellation)

        render.assert_called_once()
        self.assertIn(self.preview_root, render.call_args.args[1].parents)
        self.assertEqual(received, [GenerationCancelled()])

    def test_render_failure_discards_partial_preview_and_cleans_up(self) -> None:
        error = RuntimeError("PNG rasterization failed")
        rasterize = calendar_preview.svg_to_png

        def fail_on_second_page(svg_path: Path, png_path: Path) -> None:
            if render.call_count == 1:
                rasterize(svg_path, png_path)
                return
            png_path.write_bytes(b"partial PNG")
            raise error

        with patch.object(calendar_preview, "svg_to_png", side_effect=fail_on_second_page) as render:
            received = self.collect_events(self.pages[:2])

        self.assertEqual(render.call_count, 2)
        self.assertIn(self.preview_root, render.call_args.args[1].parents)
        self.assertEqual(received, [GenerationProgress(1, 2), GenerationFailed(error)])

    def test_already_cancelled_job_does_not_start_a_renderer(self) -> None:
        cancellation = threading.Event()
        cancellation.set()
        page = self.pages[0]
        render_svg = Mock(wraps=calendar_preview.RENDERERS[page.layout])

        with (
            patch.dict(calendar_preview.RENDERERS, {page.layout: render_svg}),
            patch.object(calendar_preview, "svg_to_png") as rasterize,
        ):
            received = self.collect_events((page,), cancellation)

        render_svg.assert_not_called()
        rasterize.assert_not_called()
        self.assertEqual(received, [GenerationCancelled()])
