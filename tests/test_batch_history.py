"""Read-only batch discovery and independent history window regressions."""

import csv
import os
from pathlib import Path
import queue
import tempfile
import threading
import unittest
from unittest.mock import patch

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from batch_history import inspect_batch, run_history_scan, scan_history


def make_batch(directory):
    directory.mkdir(parents=True)
    fields = ("date", "quote", "source", "layout", "quote_id", "app_version", "seed")
    with (directory / "manifest.csv").open("w", encoding="utf-8-sig", newline="") as stream:
        writer = csv.DictWriter(stream, fields)
        writer.writeheader()
        for layout in "AB":
            writer.writerow(dict(date="2028-02-29", quote="山高月小，水落石出。", source="苏轼",
                                 layout=layout, quote_id="old-id", app_version="0.5.7", seed="17"))
    return directory


class HistoryTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def test_old_manifest_without_web_or_images_keeps_all_layouts(self):
        directory = make_batch(self.root / "old")
        before = (directory / "manifest.csv").read_bytes()
        batch = inspect_batch(directory)
        self.assertFalse(batch.error)
        self.assertEqual((len(batch.pages), batch.seed, batch.versions), (2, 17, ("0.5.7",)))
        self.assertEqual({page.layout for page in batch.pages}, {"A", "B"})
        self.assertEqual(batch.date_range, "2028-02-29")
        self.assertEqual((batch.missing_png, batch.missing_svg, batch.has_preview), (2, 2, False))
        self.assertEqual((directory / "manifest.csv").read_bytes(), before)
        self.assertEqual(len(list(directory.iterdir())), 1)

    def test_scan_is_shallow_and_excludes_staging_locks(self):
        keep = make_batch(self.root / "valid")
        make_batch(self.root / ".pending")
        make_batch(self.root / "x.publish-lock")
        make_batch(self.root / "nested" / "deep")
        self.assertEqual([batch.directory for batch in scan_history(self.root)], [keep])
        self.assertEqual(len(list(scan_history(keep))), 1)

    def test_broken_batch_does_not_hide_healthy_batch(self):
        make_batch(self.root / "valid")
        broken = self.root / "broken"
        broken.mkdir()
        (broken / "manifest.csv").write_text("not,a,manifest\n1,2,3", encoding="utf-8")
        batches = list(scan_history(self.root))
        self.assertEqual(len(batches), 2)
        self.assertEqual(sum(bool(batch.error) for batch in batches), 1)

    def test_missing_file_state_is_refreshed_from_disk(self):
        directory = make_batch(self.root / "batch")
        (directory / "index.html").write_text("offline")
        for kind in ("png", "svg"):
            (directory / kind).mkdir()
            for layout in "AB":
                (directory / kind / f"2028-02-29_layout-{layout}.{kind}").write_bytes(b"sample")
        self.assertEqual(inspect_batch(directory).status, "文件齐全")
        (directory / "png" / "2028-02-29_layout-A.png").unlink()
        self.assertEqual(inspect_batch(directory).missing_png, 1)

    def test_cancelled_scan_has_no_batch_results(self):
        make_batch(self.root / "batch")
        events = queue.Queue()
        cancel = threading.Event()
        cancel.set()
        run_history_scan(self.root, cancel, events)
        self.assertEqual(events.get_nowait(), ("cancelled", None))
        self.assertTrue(events.empty())

    def test_scan_errors_are_reported_in_own_channel(self):
        events = queue.Queue()
        run_history_scan(self.root / "missing", threading.Event(), events)
        self.assertEqual(events.get_nowait()[0], "error")
        self.assertTrue(events.empty())

    def test_cancel_after_first_batch_stops_remaining_results(self):
        make_batch(self.root / "first")
        make_batch(self.root / "second")
        events = queue.Queue()
        cancel = threading.Event()
        put = events.put

        def receive(event):
            put(event)
            if event[0] == "batch":
                cancel.set()

        with patch.object(events, "put", side_effect=receive):
            run_history_scan(self.root, cancel, events)
        self.assertEqual(events.get_nowait()[0], "batch")
        self.assertEqual(events.get_nowait(), ("cancelled", None))
        self.assertTrue(events.empty())

    def test_scan_does_not_follow_resolved_paths_outside_root(self):
        make_batch(self.root / "linked")
        with patch.object(Path, "is_relative_to", return_value=False):
            self.assertEqual(list(scan_history(self.root)), [])

    def test_one_csv_read_collects_versions_and_preserves_replay_api(self):
        from csv_inputs import read_rows
        from generate import prepare_replay
        directory = make_batch(self.root / "one-read")
        with patch("calendar_imports.read_rows", wraps=read_rows) as reader:
            batch = inspect_batch(directory)
        reader.assert_called_once_with(directory / "manifest.csv", extra_required=("quote_id",))
        self.assertEqual(prepare_replay(directory / "manifest.csv"), (list(batch.pages), batch.seed))

    def test_manifest_timestamp_local_format_and_safe_unknown(self):
        from datetime import datetime
        directory = make_batch(self.root / "mtime")
        timestamp = 1760000000
        os.utime(directory / "manifest.csv", (timestamp, timestamp))
        self.assertEqual(inspect_batch(directory).manifest_updated,
                         datetime.fromtimestamp(timestamp).strftime("%Y-%m-%d %H:%M:%S"))
        # Only stat fails; the CSV is still readable.
        original_stat = Path.stat
        calls = []

        def fail_timestamp_only(path, *args, **kwargs):
            calls.append(path)
            if len(calls) == 1:
                raise OSError("stat unavailable")
            return original_stat(path, *args, **kwargs)

        with patch.object(Path, "stat", fail_timestamp_only):
            batch = inspect_batch(directory)
        self.assertEqual(batch.manifest_updated, "未知")
        self.assertFalse(batch.error)
        self.assertTrue(batch.pages)
        self.assertEqual(inspect_batch(self.root / "missing").manifest_updated, "未知")


class HistoryDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from PySide6.QtWidgets import QApplication
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        from history_dialog import HistoryDialog
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.directory = make_batch(self.root / "old")
        with patch("history_dialog.threading.Thread"):
            self.dialog = HistoryDialog(self.root)
        self.addCleanup(self.dialog.deleteLater)
        self.addCleanup(self.dialog.reject)

    def test_missing_web_still_allows_replay(self):
        self.dialog.model.append(inspect_batch(self.directory))
        self.dialog.table.selectRow(0)
        self.assertFalse(self.dialog.web_button.isEnabled())
        self.assertTrue(self.dialog.replay_button.isEnabled())
        self.assertIn("0.5.7", self.dialog.details.toPlainText())
        self.assertIn("清单更新时间：", self.dialog.details.toPlainText())
        self.assertNotIn("生成时间", self.dialog.details.toPlainText())
        self.dialog._replay()
        self.assertEqual(self.dialog.replay_path, self.directory / "manifest.csv")
        self.assertTrue(self.dialog.cancel_event.is_set())
        self.assertFalse(self.dialog.timer.isActive())

    def test_refresh_discards_old_queue_and_close_ignores_updates(self):
        previous_events, previous_cancel = self.dialog.events, self.dialog.cancel_event
        with patch("history_dialog.threading.Thread"):
            self.dialog._refresh()
        previous_events.put(("batch", inspect_batch(self.directory)))
        self.dialog._poll()
        self.assertTrue(previous_cancel.is_set())
        self.assertEqual(self.dialog.model.rowCount(), 0)
        self.dialog.reject()
        self.dialog.events.put(("batch", inspect_batch(self.directory)))
        self.dialog._poll()
        self.assertEqual(self.dialog.model.rowCount(), 0)

    def test_cancel_drops_queued_results_and_keeps_existing_rows(self):
        batch = inspect_batch(self.directory)
        self.dialog.model.append(batch)
        self.dialog.events.put(("batch", batch))
        self.dialog._cancel_scan()
        self.dialog.events.put(("cancelled", None))
        self.dialog._poll()
        self.assertEqual(self.dialog.model.rowCount(), 1)
        self.assertFalse(self.dialog.stop_button.isEnabled())
