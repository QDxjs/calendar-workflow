"""Selection commits explicitly, previews discard stale work and defaults stay random."""

from datetime import date
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QTest
from PySide6.QtWidgets import QApplication, QDialog

from calendar_models import GenerationCancelled, PreviewCompleted
from desktop import APP_STYLE, CalendarWindow
from preview_dialogs import BatchPreviewDialog
from quote_picker_dialog import QuotePickerDialog


class QuotePickerTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(APP_STYLE)

    def setUp(self):
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        settings = patch("preferences.preferences_path", return_value=self.root / "settings.json")
        settings.start()
        self.addCleanup(settings.stop)
        with patch("desktop.load_output_directory", return_value=self.root / "output"):
            self.window = CalendarWindow()
        self.window.start.setText("20261127")
        self.dialog = None

    def tearDown(self):
        if self.dialog is not None:
            self.dialog.reject()
            self.dialog.deleteLater()
        self.window.running = False
        self.window.poll_timer.stop()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.scratch.cleanup()

    def picker(self, quotes=None):
        self.dialog = QuotePickerDialog(quotes or self.window.quotes, date(2026, 11, 27), ("A", "B"), "", self.window)
        self.dialog.preview_timer.stop()
        return self.dialog

    def render_current(self, dialog):
        dialog.preview_timer.stop()
        with patch("quote_picker_dialog.threading.Thread") as worker:
            dialog._start_preview()
        worker.call_args.kwargs["target"]()
        dialog._poll()

    def test_default_fully_random_one_per_date_and_strict_positive_integer_input(self):
        window = self.window
        self.assertEqual(window.generation_mode.currentData(), "random")
        self.assertEqual(window.layout_choice.selection(), "RANDOM")
        self.assertEqual(window.quantity.text(), "1")
        self.assertEqual(len(window._plan_for_settings().pages), 1)
        for value in ("", "0", "-1", "1.5", "+2", "2a"):
            window.quantity.setText(value)
            self.assertFalse(window.generate_button.isEnabled())
            self.assertIn("正整数", window.quantity_error.text())
        for value in ("0", "-1", "1.5"):
            window.quantity.clear()
            QTest.keyClicks(window.quantity, value)
            self.assertNotEqual(window.quantity.text(), value)
        window.quantity.setText("3")
        window.layout_choice.set_selection("A+B")
        plan = window._plan_for_settings()
        self.assertEqual(len(plan.pages), 3)
        self.assertEqual(len({page.quote for page in plan.pages}), 3)
        window.period.setCurrentText("日期范围")
        window.end.setText("20261128")
        self.assertEqual(len(window._plan_for_settings().pages), 6)
        self.assertIn("2 天 × 3 张 / per Date", window.summary_pages.text())
        window.quotes = window.quotes[:5]
        window._refresh_summary()
        self.assertIn("需要 6", window.date_error.text())
        self.assertFalse(window.generate_button.isEnabled())

    def test_quantity_and_new_dropdown_ignore_closed_wheel(self):
        window = self.window
        for widget in (window.quantity, window.generation_mode):
            position = widget.rect().center()
            widget.setFocus()
            event = QWheelEvent(QPointF(position), QPointF(widget.mapToGlobal(position)), QPoint(),
                                QPoint(0, -120), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
                                Qt.ScrollPhase.NoScrollPhase, False)
            QApplication.sendEvent(widget, event)
        self.assertEqual(window.quantity.text(), "1")
        self.assertEqual(window.generation_mode.currentData(), "random")

    def test_selected_quote_survives_layout_and_date_mode_changes_and_reset(self):
        window = self.window
        record = dict(window.quotes[7])
        window._use_selected_quote(record)
        for layout in ("A", "A+B", "RANDOM"):
            window.layout_choice.set_selection(layout)
            pages = window._plan_for_settings().pages
            self.assertTrue(all((page.quote, page.source, page.quote_id) ==
                                (record["quote"], record["source"], record["quote_id"]) for page in pages))
        self.assertIn("已选定", window.content_panel.selected_label.text())
        window.period.setCurrentText("一周")
        self.assertIsNone(window._active_quote())
        self.assertFalse(window.content_panel.pick_button.isEnabled())
        window.period.setCurrentText("单日")
        self.assertEqual(window._active_quote(), record)
        window._reset_selected_quote()
        self.assertIsNone(window._active_quote())
        self.assertIsNone(window._prepared_plan)

    def test_recommend_search_cancel_and_confirm_preserve_original_records(self):
        dialog = self.picker()
        self.assertEqual(len(dialog.records), 5)
        self.assertEqual(dialog.candidate_count.currentData(), 5)
        first = {item["quote_id"] for item in dialog.records}
        dialog._recommend()
        self.assertFalse(first & {item["quote_id"] for item in dialog.records})
        record = self.window.quotes[-1]
        dialog.query.setText(record["quote"])
        dialog.search_timer.stop()
        dialog._search()
        self.assertIn(record, dialog.records)
        dialog.list.setCurrentRow(dialog.records.index(record))
        self.render_current(dialog)
        self.assertTrue(dialog.use_button.isEnabled())
        self.assertIsNone(dialog.selected_quote)
        self.assertIsNone(self.window._selected_quote)
        dialog.accept()
        self.assertEqual(dialog.selected_quote, record)
        self.window._use_selected_quote(dialog.selected_quote)
        self.assertEqual(self.window._active_quote(), record)

    def test_empty_search_and_stale_preview_cannot_be_confirmed(self):
        dialog = self.picker(self.window.quotes[:3])
        self.assertEqual(len(dialog.records), 3)
        self.render_current(dialog)
        self.assertTrue(dialog.use_button.isEnabled())
        old_serial = dialog._serial
        dialog.query.setText("完全不存在的搜索句子")
        self.assertFalse(dialog.use_button.isEnabled())
        dialog._events.put((old_serial, PreviewCompleted((("A", b"stale"),))))
        dialog._poll()
        dialog.search_timer.stop()
        dialog._search()
        self.assertEqual(dialog.records, [])
        self.assertIn("没有匹配", dialog.results_label.text())
        dialog.accept()
        self.assertIsNone(dialog.selected_quote)
        self.assertFalse(dialog.use_button.isEnabled())
        dialog.reject()
        self.assertTrue(dialog._cancel.is_set())
        self.assertFalse(dialog.poll_timer.isActive())

    def test_search_enter_keeps_all_matches_and_requires_explicit_confirmation(self):
        dialog = self.picker()
        dialog.show()
        self.app.processEvents()
        dialog.query.setFocus()
        for key in (Qt.Key.Key_Return, Qt.Key.Key_Enter):
            dialog.query.setText("之")
            expected = dialog.search_index.search("之")
            self.assertGreater(len(expected), 5)
            with patch.object(dialog.sampler, "recommend", wraps=dialog.sampler.recommend) as recommend:
                QTest.keyClick(dialog.query, key)
            self.assertEqual(dialog.records, expected)
            recommend.assert_not_called()
            self.assertFalse(dialog.search_timer.isActive())
            self.assertTrue(dialog.isVisible())
            self.assertIsNone(dialog.selected_quote)
            self.render_current(dialog)
            dialog.use_button.setDefault(True)
            QTest.keyClick(dialog.query, key)
            self.assertTrue(dialog.isVisible())
            self.assertIsNone(dialog.selected_quote)
        self.render_current(dialog)
        dialog.use_button.click()
        self.assertEqual(dialog.selected_quote, expected[0])

    def test_picker_cancel_keeps_committed_selection_and_cached_plan(self):
        window = self.window
        record = window.quotes[7]
        window._use_selected_quote(record)
        plan = window._plan_for_settings()
        with patch("desktop.QuotePickerDialog") as factory:
            factory.return_value.exec.return_value = QDialog.DialogCode.Rejected
            window._pick_quote()
        self.assertEqual(window._active_quote(), record)
        self.assertIs(window._plan_for_settings(), plan)
        window._reset_quotes()
        self.assertIsNone(window._selected_quote)

    def test_batch_navigation_retains_duplicate_layout_pages_and_all_pngs_match_export(self):
        window = self.window
        window.layout_choice.set_selection("A")
        window.quantity.setText("3")
        with patch("desktop.threading.Thread") as previewer:
            window._start_sample()
        plan = window._prepared_plan
        previewer.call_args.kwargs["target"](*previewer.call_args.kwargs["args"])
        with patch.object(window, "_show_sample"):
            window._poll()
        self.dialog = BatchPreviewDialog(plan.pages, window._sample_images, window)
        self.dialog.next_button.click()
        self.assertEqual(self.dialog.index, 1)
        self.dialog.next_button.click()
        self.assertEqual(self.dialog.index, 2)
        self.assertFalse(self.dialog.next_button.isEnabled())
        self.dialog.previous_button.click()
        self.assertEqual(self.dialog.index, 1)
        images = window._sample_images
        with patch("desktop.threading.Thread") as exporter:
            window._start()
        exporter.call_args.kwargs["target"](*exporter.call_args.kwargs["args"])
        window._poll()
        for page, (_layout, image) in zip(plan.pages, images):
            self.assertEqual((window.latest_output_dir / "png" / f"{page.basename}.png").read_bytes(), image)

    def test_reroll_invalidates_plan_and_fixed_seed_is_not_silently_changed(self):
        window = self.window
        old = window._plan_for_settings()
        with patch("desktop.threading.Thread"):
            window._reroll()
        self.assertIsNot(window._prepared_plan, old)
        window.events.put(GenerationCancelled())
        window._poll()
        window.seed.setText("17")
        fixed = window._plan_for_settings()
        self.assertFalse(window.reroll_button.isEnabled())
        window._reroll()
        self.assertEqual(window.seed.text(), "17")
        self.assertIs(window._plan_for_settings(), fixed)


if __name__ == "__main__":
    unittest.main()
