"""Regression checks for date modes, task controls and output recovery."""

from __future__ import annotations

from datetime import date
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtWidgets import QApplication

import desktop
from calendar_models import (
    GenerationCancelled, GenerationCompleted, GenerationFailed,
    GenerationProgress, PreviewCompleted,
)


class DesktopTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyleSheet(desktop.APP_STYLE)

    def setUp(self) -> None:
        self.scratch = tempfile.TemporaryDirectory()
        self.root = Path(self.scratch.name)
        settings = patch("preferences.preferences_path", return_value=self.root / "settings.json")
        settings.start()
        self.addCleanup(settings.stop)
        with patch("desktop.load_output_directory", return_value=self.root / "output"):
            self.window = desktop.CalendarWindow()
        self.window.start.setText("20270115")

    def tearDown(self) -> None:
        self.window.running = False
        self.window.poll_timer.stop()
        self.window.close()
        self.window.deleteLater()
        self.app.processEvents()
        self.scratch.cleanup()

    def test_modes_convert_valid_values_and_remember_each_mode(self) -> None:
        window = self.window
        window.period.setCurrentText("月份")
        self.assertEqual((window.start.text(), window.start.placeholderText()), ("202701", "YYYYMM"))
        window.start.setText("2028-02")
        self.assertEqual(len(window._selection()[0]), 29)
        window.period.setCurrentText("年份")
        self.assertEqual((window.start.text(), window.start.placeholderText()), ("2028", "YYYY"))
        self.assertEqual(len(window._selection()[0]), 366)
        window.period.setCurrentText("单日")
        self.assertEqual(window.start.text(), "20270115")
        window.period.setCurrentText("日期范围")
        self.assertEqual(window.end.text(), "20270115")
        window.end.setText("20270118")
        window.period.setCurrentText("月份")
        self.assertEqual(window.start.text(), "2028-02")
        window.period.setCurrentText("日期范围")
        self.assertEqual((window.start.text(), window.end.text()), ("20270115", "20270118"))
        self.assertEqual(len(window._selection()[0]), 4)
        window.period.setCurrentText("一周")
        window.start.setText("20210101")
        self.assertEqual(window._selection()[0][0], date(2020, 12, 28))

    def test_invalid_input_is_preserved_and_specific_errors_block_generation(self) -> None:
        window = self.window
        window.start.setText("20270229")
        self.assertIn("不存在", window.date_error.text())
        self.assertFalse(window.generate_button.isEnabled())
        self.assertIn("修正", window.status.text())
        window.period.setCurrentText("年份")
        self.assertEqual(window.start.text(), "20270229")
        self.assertIn("四位数字", window.date_error.text())
        window.start.setText("2028")
        window.seed.setText("not-an-integer")
        self.assertIn("整数", window.seed_error.text())
        self.assertFalse(window.generate_button.isEnabled())
        window.seed.setText("-17")
        self.assertTrue(window.generate_button.isEnabled())
        self.assertIn("准备就绪", window.status.text())
        window.quotes = window.quotes[:2]
        window._refresh_summary()
        self.assertIn("366", window.date_error.text())
        self.assertIn("当前只有 2 条", window.date_error.text())
        self.assertFalse(window.start.property("invalid"))
        self.assertFalse(window.generate_button.isEnabled())
        window.period.setCurrentText("日期范围")
        window.start.setText("20270115")
        window.end.setText("20270114")
        self.assertIn("不能早于", window.date_error.text())
        self.assertTrue(window.end.property("invalid"))
        # A bad new-calendar setting does not prevent restoring an existing manifest.
        self.assertTrue(window.replay_button.isEnabled())

    def test_running_task_freezes_settings_summary_and_prepared_pages(self) -> None:
        window = self.window
        window.seed.setText("31415")
        window._custom_quotes = True
        with patch("desktop.threading.Thread") as worker:
            window._start()
        self.assertTrue(window.running)
        for name in ("period", "start", "end", "layout_choice", "seed", "import_button", "reset_button", "browse_button", "generate_button", "replay_button", "sample_button", "layouts_button"):
            with self.subTest(control=name):
                self.assertFalse(getattr(window, name).isEnabled())
        prepare = worker.call_args.kwargs["args"][0]
        pages, seed = prepare()
        summary = window.summary_period.text()
        window.start.setText("20270116")
        window.seed.setText("99")
        self.assertEqual(window.summary_period.text(), summary)
        self.assertEqual((pages[0].target_date, seed), (date(2027, 1, 15), 31415))

    def test_terminal_events_restore_controls_and_preserve_successful_preview(self) -> None:
        window = self.window
        successful = self.root / "successful"
        successful.mkdir()
        (successful / "index.html").write_text("previous preview", encoding="utf-8")
        window.latest_output_dir = successful
        window._custom_quotes = True
        for event in (GenerationCancelled(), GenerationFailed(PermissionError("denied")), GenerationCompleted(successful)):
            with self.subTest(event=type(event).__name__):
                with patch("desktop.threading.Thread"):
                    window._start()
                self.assertTrue(window.preview_button.isEnabled())
                if isinstance(event, GenerationCancelled):
                    window._cancel()
                    self.assertFalse(window.cancel_button.isEnabled())
                    self.assertFalse(window.period.isEnabled())
                window.events.put(event)
                with patch("desktop.QMessageBox.critical"), patch("desktop.QDesktopServices.openUrl") as opener:
                    window._poll()
                    opener.assert_not_called()
                self.assertFalse(window.running)
                self.assertTrue(window.period.isEnabled())
                self.assertTrue(window.generate_button.isEnabled())
                self.assertTrue(window.reset_button.isEnabled())
                self.assertFalse(window.cancel_button.isEnabled())
                self.assertTrue(window.preview_button.isEnabled())
                self.assertEqual(window.latest_output_dir, successful)

    def test_read_only_default_keeps_window_available_for_folder_recovery(self) -> None:
        destination = self.root / "portable-default"
        with patch.object(desktop.sys, "frozen", True, create=True), patch("desktop.OUTPUT_ROOT", destination), patch("desktop.check_output_directory", side_effect=PermissionError("denied")):
            window = desktop.CalendarWindow()
        try:
            self.assertEqual(window.output_root, destination)
            self.assertIn("权限", window.output_error.text())
            self.assertFalse(window.generate_button.isEnabled())
            self.assertTrue(window.browse_button.isEnabled())
            alternative = self.root / "writable"
            with patch("desktop.QFileDialog.getExistingDirectory", return_value=str(alternative)), patch("desktop.save_output_directory"):
                window._choose_folder()
            self.assertEqual(window.output_root, alternative)
            self.assertEqual(list(alternative.iterdir()), [])
            self.assertEqual(window.output_error.text(), "")
            self.assertTrue(window.generate_button.isEnabled())
        finally:
            window.poll_timer.stop()
            window.close()
            window.deleteLater()

    def test_output_probe_cleans_up_and_permission_failure_starts_no_worker(self) -> None:
        target = self.root / "new" / "nested"
        desktop.check_output_directory(target)
        self.assertEqual(list(target.iterdir()), [])
        occupied = self.root / "file"
        occupied.write_text("keep", encoding="utf-8")
        with self.assertRaises(OSError):
            desktop.check_output_directory(occupied)
        self.assertEqual(occupied.read_text(encoding="utf-8"), "keep")
        with patch("desktop.check_output_directory", side_effect=PermissionError("denied")), patch("desktop.threading.Thread") as worker:
            self.window._start()
        worker.assert_not_called()
        self.assertFalse(self.window.running)
        self.assertIn("权限", self.window.output_error.text())
        self.assertTrue(self.window.browse_button.isEnabled())

    def test_actual_sample_and_export_share_plan_with_or_without_seed(self) -> None:
        window = self.window
        window.period.setCurrentText("日期范围")
        window.end.setText("20270117")
        for seed in ("", "31415"):
            with self.subTest(seed=seed):
                window.seed.setText(seed)
                window.output_root = self.root / ("unseeded" if not seed else "seeded")
                with patch("desktop.threading.Thread") as worker:
                    window._start_sample()
                plan = window._prepared_plan
                args = worker.call_args.kwargs["args"]
                self.assertEqual(args[0], plan.pages[:1])
                self.assertFalse(window.generate_button.isEnabled())
                self.assertFalse(window.sample_button.isEnabled())
                worker.call_args.kwargs["target"](*args)
                with patch.object(window, "_show_sample") as viewer:
                    window._poll()
                viewer.assert_called_once_with(plan)
                self.assertFalse(window.output_root.exists())
                self.assertEqual(window.preview_button.isEnabled(), window.latest_output_dir is not None)
                self.assertEqual(window.summary_pages.text(), "3 页")
                image = window._sample_image
                with patch("desktop.threading.Thread") as repeat, patch.object(window, "_show_sample"):
                    window._start_sample()
                repeat.assert_not_called()
                with patch("desktop.threading.Thread") as exporter:
                    window._start()
                prepare, output, cancel, events = exporter.call_args.kwargs["args"]
                self.assertEqual(prepare(), (list(plan.pages), plan.seed))
                exporter.call_args.kwargs["target"](prepare, output, cancel, events)
                with patch("desktop.QDesktopServices.openUrl") as browser:
                    window._poll()
                browser.assert_not_called()
                first = plan.pages[0]
                self.assertEqual((output / "png" / f"{first.target_date}_layout-{first.layout}.png").read_bytes(), image)
                self.assertTrue(window.preview_button.isEnabled())

    def test_content_changes_invalidate_sample_but_output_change_does_not(self) -> None:
        window = self.window
        plan = window._plan_for_settings()
        window._sample_image = b"previous image"
        window.output_root = self.root / "another destination"
        window._refresh_summary()
        self.assertIs(window._prepared_plan, plan)
        self.assertIsNotNone(window._sample_image)
        changes = (
            lambda: window.start.setText("20270116"),
            lambda: window.seed.setText("31415"),
            lambda: window.layout_choice.setCurrentIndex(2),
            lambda: setattr(window, "quotes", window.quotes[1:]),
            lambda: window.start.setText("invalid"),
        )
        for change in changes:
            plan = window._plan_for_settings()
            window._sample_image = b"stale image"
            change()
            window._refresh_summary()
            self.assertIsNone(window._prepared_plan)
            self.assertIsNone(window._sample_image)
            self.assertIn("重新", window.sample_status.text())

    def test_preview_cancel_failure_and_late_completion_keep_previous_batch(self) -> None:
        window = self.window
        window.latest_output_dir = self.root / "previous batch"
        for event in (GenerationCancelled(), GenerationFailed(RuntimeError("renderer unavailable")), PreviewCompleted((("A", b"late image"),))):
            with self.subTest(event=type(event).__name__):
                with patch("desktop.threading.Thread"):
                    window._start_sample()
                if isinstance(event, PreviewCompleted):
                    window._cancel()
                window.events.put(GenerationProgress(1, 1))
                window.events.put(event)
                with patch.object(window, "_show_sample") as viewer, patch("desktop.QMessageBox.critical"), patch("desktop.QDesktopServices.openUrl") as browser:
                    window._poll()
                viewer.assert_not_called()
                browser.assert_not_called()
                self.assertIsNone(window._sample_image)
                self.assertFalse(window.running)
                self.assertTrue(window.sample_button.isEnabled())
                self.assertTrue(window.generate_button.isEnabled())
                self.assertTrue(window.preview_button.isEnabled())
                self.assertEqual(window.summary_pages.text(), "1 页")

    def test_unwritable_output_still_allows_temporary_sample(self) -> None:
        window = self.window
        window._output_error = "保存位置没有写入权限"
        window._refresh_summary()
        self.assertFalse(window.generate_button.isEnabled())
        self.assertTrue(window.sample_button.isEnabled())
        with patch("desktop.check_output_directory") as check_output, patch("desktop.threading.Thread") as worker:
            window._start_sample()
        check_output.assert_not_called()
        worker.assert_called_once()

    def test_layout_dialog_cancel_waits_for_worker_and_choice_updates_summary(self) -> None:
        window = self.window
        with patch("desktop.threading.Thread"):
            window._show_layouts()
        dialog = window._layout_dialog
        self.assertTrue(window.running)
        dialog._select("随机")
        self.assertTrue(window.cancel_event.is_set())
        self.assertTrue(window.running)
        self.assertIsNone(window._layout_dialog)
        window.events.put(GenerationCancelled())
        window._poll()
        self.assertTrue(window.layouts_button.isEnabled())
        with patch("desktop.threading.Thread"):
            window._show_layouts()
        dialog = window._layout_dialog
        # Model a ready chooser without performing another real renderer run.
        window.events.put(GenerationCancelled())
        window._poll()
        dialog._select("I")
        self.assertEqual(window.layout_choice.currentData(), "I")
        self.assertIn("I", window.summary_layout.text())

    def test_success_finishes_plan_but_retry_reuses_it_and_seed_reproduces(self) -> None:
        window = self.window
        window.period.setCurrentText("日期范围")
        window.end.setText("20270117")
        actual_planner = desktop.plan_pages
        # Controlled random outcomes prove replanning without a probabilistic assertion.
        def controlled_planner(days, quotes, layout, seed):
            return actual_planner(days, quotes, layout, planner.call_count if seed is None else seed)
        with patch("desktop.plan_pages", side_effect=controlled_planner) as planner:
            first = window._plan_for_settings()
            window._sample_image = b"preview for first batch"
            for event in (GenerationCancelled(), GenerationFailed(RuntimeError("retry"))):
                with patch("desktop.threading.Thread"):
                    window._start()
                window.events.put(event)
                with patch("desktop.QMessageBox.critical"):
                    window._poll()
                self.assertIs(window._prepared_plan, first)
                self.assertIs(window._plan_for_settings(), first)
                self.assertEqual(planner.call_count, 1)
            with patch("desktop.threading.Thread"):
                window._start()
            window.events.put(GenerationCompleted(self.root / "first"))
            window._poll()
            self.assertIsNone(window._prepared_plan)
            self.assertIsNone(window._sample_image)
            second = window._plan_for_settings()
            self.assertEqual(planner.call_count, 2)
            self.assertNotEqual(first.pages, second.pages)
        window.seed.setText("31415")
        fixed = window._plan_for_settings()
        with patch("desktop.threading.Thread"):
            window._start()
        window.events.put(GenerationCompleted(self.root / "fixed"))
        window._poll()
        again = window._plan_for_settings()
        self.assertIsNot(again, fixed)
        self.assertEqual(again, fixed)

    def test_import_cancel_and_empty_keep_corpus_confirm_invalidates_sample(self) -> None:
        import json
        window = self.window
        existing = window.quotes
        existing_plan = window._plan_for_settings()
        window._sample_image = b"sample"
        source = self.root / "quotes.json"
        source.write_text(json.dumps([{"name": "有效的测试正文", "from": "用户提供的出处"}], ensure_ascii=False), encoding="utf-8")
        for result in (desktop.QDialog.DialogCode.Rejected, desktop.QDialog.DialogCode.Accepted):
            with patch("desktop.QFileDialog.getOpenFileName", return_value=(str(source), "")), patch.object(desktop.QuotePreviewDialog, "exec", return_value=result):
                window._import_quotes()
            if result == desktop.QDialog.DialogCode.Rejected:
                self.assertIs(window.quotes, existing)
                self.assertIs(window._prepared_plan, existing_plan)
            else:
                self.assertEqual(window.quotes[0]["source"], "用户提供的出处")
                self.assertIsNone(window._prepared_plan)
                self.assertIsNone(window._sample_image)
        imported = window.quotes
        source.write_text('[{"name":"短","from":"出处"}]', encoding="utf-8")
        with patch("desktop.QFileDialog.getOpenFileName", return_value=(str(source), "")), patch.object(desktop.QuotePreviewDialog, "exec", return_value=desktop.QDialog.DialogCode.Accepted):
            window._import_quotes()
        self.assertIs(window.quotes, imported)


    def test_portable_directory_persists_and_reset_preserves_content_plan(self):
        import preferences
        window = self.window
        plan = window._plan_for_settings()
        selected = self.root / "portable-output"
        default = self.root / "default-output"
        with patch.object(desktop.sys, "frozen", True, create=True):
            window._set_output_directory(selected)
            self.assertEqual(preferences.load_output_directory(default), selected)
            self.assertIs(window._prepared_plan, plan)
            with patch("desktop.OUTPUT_ROOT", default):
                window._reset_output_directory()
            self.assertEqual(window.output_root, default)
            self.assertEqual(preferences.load_output_directory(default), default)
            self.assertIs(window._prepared_plan, plan)

    def test_history_uses_shared_replay_and_locks_during_generation(self):
        from PySide6.QtWidgets import QDialog
        manifest = self.root / "batch" / "manifest.csv"
        with patch("desktop.HistoryDialog") as factory, patch.object(self.window, "_replay_manifest") as replay:
            factory.return_value.exec.return_value = QDialog.DialogCode.Accepted
            factory.return_value.replay_path = manifest
            self.window._show_history()
            replay.assert_called_once_with(manifest)
            factory.return_value.deleteLater.assert_called_once()
        self.window.running = True
        self.window._sync_controls()
        self.assertFalse(self.window.history_button.isEnabled())
        self.assertFalse(self.window.default_folder_button.isEnabled())
        with patch("desktop.HistoryDialog") as factory:
            self.window._show_history()
            factory.assert_not_called()

    def test_reset_clears_custom_preference_even_when_default_is_read_only(self):
        import preferences
        preferences.save_output_directory(self.root / "custom")
        default = self.root / "default"
        with patch("desktop.OUTPUT_ROOT", default), patch("desktop.check_output_directory", side_effect=PermissionError("read only")):
            self.window._reset_output_directory()
        self.assertEqual(preferences.load_output_directory(default), default)
        self.assertIn("权限", self.window.output_error.text())
        self.assertFalse(self.window.generate_button.isEnabled())

    def _manual(self, quote="春风又绿江南岸\n明月何时照我还", source=""):
        panel = self.window.content_panel
        panel.quote_edit.setPlainText(quote)
        panel.source_edit.setText(source)
        panel.selector.setCurrentIndex(1)
        return panel

    def test_manual_switch_preserves_imported_corpus_and_memory_draft(self):
        window = self.window
        window.quotes = window.quotes[:2]
        original = window.quotes
        window._custom_quotes = True
        panel = self._manual(source="原样署名")
        self.assertTrue(window._settings_valid)
        self.assertIn("单日手写", window.summary_quotes.text())
        self.assertEqual(window._content_key()[0], "manual")
        self.assertIs(window.quotes, original)
        window.period.setCurrentText("月份")
        self.assertFalse(panel.is_manual)
        self.assertEqual(panel.selector.currentData(), "corpus")
        self.assertFalse(panel.selector.model().item(1).isEnabled())
        self.assertFalse(window._settings_valid)  # Corpus capacity still checked.
        window.period.setCurrentText("单日")
        self.assertTrue(panel.selector.model().item(1).isEnabled())
        self.assertFalse(panel.is_manual)
        panel.selector.setCurrentIndex(1)
        self.assertEqual(panel.content().source, "原样署名")
        self.assertIn("\n", panel.content().quote)
        self.assertIs(window.quotes, original)
        self.assertTrue(window._custom_quotes)
        panel.clear_button.click()
        self.assertEqual(panel.content().quote, "")
        self.assertEqual(panel.content().source, "")
        self.assertIs(window.quotes, original)
        self.assertTrue(window.generate_button.isEnabled())
        self.assertIn("留白日历", window.summary_quotes.text())
        self.assertFalse((self.root / "settings.json").exists())

    def test_manual_fields_validate_inline_and_long_quote_is_soft_warning(self):
        panel = self._manual(quote="，。")
        self.assertIn("有效文字", panel.quote_error.text())
        self.assertFalse(self.window.sample_button.isEnabled())
        panel.quote_edit.setPlainText("春" * 65)
        self.assertIn("超过 58", panel.count_label.text())
        self.assertTrue(self.window.sample_button.isEnabled())
        panel.source_edit.setText("出处\x00")
        self.assertIn("U+0000", panel.source_error.text())
        self.assertFalse(self.window.generate_button.isEnabled())
        panel.source_edit.clear()
        self.assertTrue(self.window.generate_button.isEnabled())
        self.assertIn("无出处", self.window.summary_quotes.text())

    def test_manual_cache_newlines_source_and_output_destination(self):
        window = self.window
        panel = self._manual()
        for change in (lambda: panel.source_edit.setText("署名"),
                       lambda: panel.quote_edit.setPlainText("春风又绿江南岸 明月何时照我还"),
                       lambda: panel.quote_edit.setPlainText("春风又绿江南岸\n明月何时照我还"),
                       lambda: panel.selector.setCurrentIndex(0)):
            plan = window._plan_for_settings()
            window._sample_image = b"cached"
            window.output_root = self.root / "new-output"
            window._refresh_summary()
            self.assertIs(window._prepared_plan, plan)
            self.assertEqual(window._sample_image, b"cached")
            change()
            self.assertIsNone(window._prepared_plan)
            self.assertIsNone(window._sample_image)

    def test_manual_fit_error_blocks_work_until_content_changes(self):
        window = self.window
        panel = self._manual(quote="\n".join(["春风"] * 6))
        with patch("desktop.threading.Thread") as worker, patch("desktop.QMessageBox.warning") as dialog:
            window._start_sample()
        worker.assert_not_called()
        dialog.assert_not_called()
        self.assertIn("全部版式", panel.quote_error.text())
        self.assertFalse(window.sample_button.isEnabled())
        window.output_root = self.root / "different"
        window._refresh_summary()
        self.assertFalse(window.sample_button.isEnabled())
        panel.quote_edit.setPlainText("春风")
        self.assertTrue(window.sample_button.isEnabled())
        self.assertEqual(window._plan_for_settings().pages[0].quote, "春风")

    def test_manual_does_not_need_corpus_capacity(self):
        self.window.quotes = []
        self._manual(quote="春")
        self.assertTrue(self.window._settings_valid)
        self.assertEqual(self.window._plan_for_settings().pages[0].quote, "春")

    def test_manual_blank_quote_is_valid_and_summary_explains_blank_calendar(self):
        window = self.window
        panel = self._manual(quote=" \n\t ")
        self.assertTrue(window._settings_valid)
        self.assertTrue(window.generate_button.isEnabled())
        self.assertTrue(window.sample_button.isEnabled())
        self.assertIn("留白日历", window.summary_quotes.text())
        plan = window._plan_for_settings()
        self.assertEqual((plan.pages[0].quote, plan.pages[0].source), ("", ""))
        with patch("desktop.threading.Thread") as worker:
            window._start_sample()
        self.assertTrue(worker.called)
        window.running = False
        window._refresh_summary()
        panel.quote_edit.setPlainText("，。")
        self.assertFalse(window._settings_valid)
        self.assertIn("不能只有标点", panel.quote_error.text())

    def test_manual_preview_export_identical_and_manifest_restores(self):
        from batch_history import inspect_batch
        window = self.window
        panel = self._manual()
        window.seed.setText("31415")
        cases = (("春风又绿江南岸\n明月何时照我还", "", "31415"),
                 ("春风又绿江南岸\n明月何时照我还", "", ""),
                 ("", "", "31415"), (" \n\t ", "", ""), ("", "原样署名", "17"))
        for quote, source, seed in cases:
            panel.quote_edit.setPlainText(quote)
            panel.source_edit.setText(source)
            window.seed.setText(seed)
            with patch("desktop.threading.Thread") as worker:
                window._start_sample()
            plan = window._prepared_plan
            worker.call_args.kwargs["target"](*worker.call_args.kwargs["args"])
            with patch.object(window, "_show_sample"):
                window._poll()
            image = window._sample_image
            with patch("desktop.threading.Thread") as exporter:
                window._start()
            self.assertTrue(window.running)
            for widget in (panel.quote_edit, panel.source_edit, panel.selector, panel.clear_button):
                self.assertFalse(widget.isEnabled())
            args = exporter.call_args.kwargs["args"]
            self.assertEqual(args[0](), (list(plan.pages), plan.seed))
            exporter.call_args.kwargs["target"](*args)
            window._poll()
            output = window.latest_output_dir
            page = plan.pages[0]
            self.assertEqual((output / "png" / f"{page.target_date}_layout-{page.layout}.png").read_bytes(), image)
            self.assertEqual(desktop.prepare_replay(output / "manifest.csv"), (list(plan.pages), plan.seed))
            self.assertEqual(inspect_batch(output).pages, plan.pages)
            for widget in (panel.quote_edit, panel.source_edit, panel.selector, panel.clear_button):
                self.assertTrue(widget.isEnabled())
            self.assertEqual(panel.content().quote.strip(), page.quote)
            self.assertEqual(panel.content().source.strip(), page.source)
        panel.selector.setCurrentIndex(0)
        self.assertTrue(window._settings_valid)
        with patch("desktop.threading.Thread") as replayer:
            window._replay_manifest(output / "manifest.csv")
        self.assertEqual(replayer.call_args.kwargs["args"][0](), (list(plan.pages), plan.seed))

    def test_manual_cancel_and_failure_restore_controls_and_plan(self):
        window = self.window
        panel = self._manual()
        plan = window._plan_for_settings()
        for event in (GenerationCancelled(), GenerationFailed(ValueError("renderer failed"))):
            for preview in (True, False):
                with patch("desktop.threading.Thread"):
                    (window._start_sample if preview else window._start)()
                for widget in (panel.quote_edit, panel.source_edit, panel.selector, panel.clear_button):
                    self.assertFalse(widget.isEnabled())
                window._cancel()
                window.events.put(event)
                with patch("desktop.QMessageBox.critical"):
                    window._poll()
                self.assertFalse(window.running)
                self.assertIs(window._plan_for_settings(), plan)
                for widget in (panel.quote_edit, panel.source_edit, panel.selector, panel.clear_button):
                    self.assertTrue(widget.isEnabled())


if __name__ == "__main__":
    unittest.main()
