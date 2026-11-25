"""Public regression coverage for dates, input rejection and batch integrity."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import tempfile
import unittest

from calendar_models import BatchCancelled, CalendarPage
from generate import prepare_pages, prepare_replay, validate_pages, validate_png, validate_rendering, write_batch
from periods import dates_between, dates_in_iso_week, dates_in_month, dates_in_year
from verify_release import verify_builtin_corpus, verify_replay


ROOT = Path(__file__).resolve().parents[1]


class DateTests(unittest.TestCase):
    def test_leap_day_and_year(self) -> None:
        self.assertEqual(dates_in_month(2028, 2)[-1], date(2028, 2, 29))
        self.assertEqual(len(dates_in_year(2028)), 366)
        self.assertEqual(len(dates_in_year(2027)), 365)

    def test_iso_week_crosses_calendar_year(self) -> None:
        week = dates_in_iso_week(date(2021, 1, 1))
        self.assertEqual((week[0], week[-1]), (date(2020, 12, 28), date(2021, 1, 3)))
        self.assertTrue(all(day.isocalendar()[:2] == (2020, 53) for day in week))

    def test_reversed_period_is_rejected(self) -> None:
        with self.assertRaises(ValueError):
            dates_between(date(2027, 1, 2), date(2027, 1, 1))


class InputTests(unittest.TestCase):
    def test_bundled_quotes_keep_pinned_text_and_attribution(self) -> None:
        self.assertGreaterEqual(len(verify_builtin_corpus()), 366)

    def test_all_csv_examples_fit_their_layouts(self) -> None:
        for filename in ("content.csv", "examples/template_gallery.csv", "examples/template_gallery_F-I.csv"):
            with self.subTest(filename=filename):
                validate_rendering(prepare_pages(ROOT / filename), exhaustive_random_layouts=True)

    def test_invalid_csv_is_rejected_before_output(self) -> None:
        invalid_rows = (
            "2027-02-29,这是一个日期示例。,示例,A\n",
            "2027-01-01,这是一个字段示例。,示例\n",
            "2027-01-01,这是一个版式示例。,示例,Z\n",
        )
        with tempfile.TemporaryDirectory() as temporary:
            source = Path(temporary) / "invalid.csv"
            for row in invalid_rows:
                with self.subTest(row=row):
                    source.write_text("date,quote,source,layout\n" + row, encoding="utf-8")
                    with self.assertRaises(ValueError):
                        prepare_pages(source)
                    self.assertEqual(list(Path(temporary).iterdir()), [source])

    def test_same_quote_cannot_be_assigned_to_different_days(self) -> None:
        pages = [CalendarPage(date(2027, 1, day), "A", "A", "雨后记得开窗。", "示例") for day in (1, 2)]
        with self.assertRaises(ValueError):
            validate_pages(pages)

    def test_unsupported_svg_control_character_is_rejected(self) -> None:
        page = CalendarPage(date(2027, 1, 1), "A", "A", "雨后\x00记得开窗。", "示例")
        with self.assertRaises(ValueError):
            validate_pages([page])


class PublicationTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.pages = prepare_pages(ROOT / "examples/template_gallery.csv") + prepare_pages(ROOT / "examples/template_gallery_F-I.csv")

    def test_nine_layouts_render_and_manifest_replays_without_changes(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            scratch = Path(temporary)
            output = scratch / "日历 验证"
            output.mkdir()
            batch = output / "templates"
            self.assertEqual(write_batch(self.pages, batch, seed=31415, on_progress=lambda *_: None), 9)
            self.assertEqual(len(list((batch / "svg").glob("*.svg"))), 9)
            images = list((batch / "png").glob("*.png"))
            self.assertEqual(len(images), 9)
            for image in images:
                validate_png(image)
            pages, seed = prepare_replay(batch / "manifest.csv")
            self.assertEqual((pages, seed), (self.pages, 31415))
            verify_replay(output, scratch)

            corrupt = scratch / "corrupt.png"
            data = bytearray(images[0].read_bytes())
            data[-1] ^= 1
            corrupt.write_bytes(data)
            with self.assertRaises(RuntimeError):
                validate_png(corrupt)

    def test_existing_batch_is_never_overwritten(self) -> None:
        with tempfile.TemporaryDirectory() as temporary:
            output = Path(temporary) / "existing"
            output.mkdir()
            marker = output / "keep.txt"
            marker.write_text("keep", encoding="utf-8")
            with self.assertRaises(FileExistsError):
                write_batch(self.pages[:1], output)
            self.assertEqual(marker.read_text(encoding="utf-8"), "keep")
            self.assertEqual(list(output.iterdir()), [marker])

    def test_cancel_before_render_does_not_publish_or_leave_files(self) -> None:
        def cancel() -> None:
            raise BatchCancelled()

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            with self.assertRaises(BatchCancelled):
                write_batch(self.pages[:1], root / "cancelled", check_cancel=cancel)
            self.assertEqual(list(root.iterdir()), [])


if __name__ == "__main__":
    unittest.main()
