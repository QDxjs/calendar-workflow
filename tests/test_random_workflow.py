"""Per-date quantity, unique output names, manifest compatibility and preview."""

import csv
from datetime import date, timedelta
from pathlib import Path
import queue
import tempfile
import threading
import unittest

from batch_history import inspect_batch
from calendar_models import CalendarPage, PreviewCompleted
from calendar_preview import run_preview_job
from generate import prepare_replay, validate_pages, validate_png, write_batch
from launcher import plan_pages
from quote_library import builtin_quotes


class RandomWorkflowTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.quotes = builtin_quotes()[:20]
        cls.days = [date(2026, 11, 27) + timedelta(days=index) for index in range(2)]

    def test_per_date_total_layout_pool_no_repeat_and_seed_reproduction(self):
        for layout in ("A", "A+B", "RANDOM"):
            with self.subTest(layout=layout):
                pages = plan_pages(self.days, self.quotes, layout, 17, pages_per_date=5)
                self.assertEqual(pages, plan_pages(self.days, self.quotes, layout, 17, pages_per_date=5))
                self.assertEqual(len(pages), 10)
                self.assertEqual(len({page.quote for page in pages}), 10)
                self.assertEqual(len({page.basename for page in pages}), 10)
                for day in self.days:
                    daily = [page for page in pages if page.target_date == day]
                    self.assertEqual([page.variant for page in daily], [1, 2, 3, 4, 5])
                if layout != "RANDOM":
                    self.assertTrue({page.layout for page in pages} <= set(layout.split("+")))
                if layout != "A":
                    self.assertTrue(all(left.layout != right.layout for left, right in zip(pages, pages[1:])))
                validate_pages(pages)

    def test_only_positive_integer_quantities_are_valid_and_capacity_is_total(self):
        for invalid in (0, -1, 1.5, True, "2"):
            with self.subTest(value=invalid), self.assertRaisesRegex(ValueError, "正整数"):
                plan_pages(self.days, self.quotes, "RANDOM", pages_per_date=invalid)
        with self.assertRaisesRegex(ValueError, "需要的 22"):
            plan_pages(self.days, self.quotes, "A", pages_per_date=11)

    def test_selected_record_applies_to_each_layout_unchanged(self):
        selected = self.quotes[3]
        pages = plan_pages(self.days[:1], self.quotes, "A+B", selected_quote=selected)
        self.assertEqual([page.layout for page in pages], ["A", "B"])
        self.assertTrue(all((page.quote, page.source, page.quote_id) ==
                            (selected["quote"], selected["source"], selected["quote_id"]) for page in pages))
        with self.assertRaisesRegex(ValueError, "单日"):
            plan_pages(self.days, self.quotes, "A", selected_quote=selected)

    def test_repeated_layout_pages_roundtrip_history_gallery_and_all_preview_images(self):
        pages = plan_pages(self.days[:1], self.quotes, "A", 17, pages_per_date=5)
        events = queue.Queue()
        run_preview_job(tuple(pages), threading.Event(), events)
        result = None
        while not events.empty():
            result = events.get_nowait()
        self.assertIsInstance(result, PreviewCompleted)
        self.assertEqual(len(result.images), 5)
        with tempfile.TemporaryDirectory() as scratch:
            batch = Path(scratch) / "random-five"
            write_batch(pages, batch, seed=17, on_progress=lambda *_: None)
            self.assertEqual(prepare_replay(batch / "manifest.csv"), (pages, 17))
            summary = inspect_batch(batch)
            self.assertEqual(summary.pages, tuple(pages))
            self.assertEqual(summary.status, "文件齐全")
            gallery = (batch / "index.html").read_text(encoding="utf-8")
            for page, (_layout, image) in zip(pages, result.images):
                png = batch / "png" / f"{page.basename}.png"
                self.assertEqual(png.read_bytes(), image)
                validate_png(png)
                self.assertIn(f"png/{page.basename}.png", gallery)
            self.assertEqual(len(list((batch / "png").glob("*.png"))), 5)

    def test_legacy_manifests_without_variant_column_and_invalid_new_ordinal(self):
        page = CalendarPage(self.days[0], "A", "A", self.quotes[0]["quote"], self.quotes[0]["source"])
        self.assertEqual(page.basename, "2026-11-27_layout-A")
        with tempfile.TemporaryDirectory() as scratch:
            manifest = Path(scratch) / "manifest.csv"
            def save(fields, row):
                with manifest.open("w", encoding="utf-8-sig", newline="") as handle:
                    writer = csv.DictWriter(handle, fieldnames=fields)
                    writer.writeheader()
                    writer.writerow(row)
            record = {"date": "2026-11-27", "layout": "A", "quote": page.quote, "source": page.source, "quote_id": ""}
            save(list(record), record)
            self.assertEqual(prepare_replay(manifest), ([page], None))
            for value in ("0", "-1", "1.5", "../file"):
                save(list(record) + ["variant"], dict(record, variant=value))
                with self.subTest(value=value), self.assertRaisesRegex(ValueError, "页序号"):
                    prepare_replay(manifest)


if __name__ == "__main__":
    unittest.main()
