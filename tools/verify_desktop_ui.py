"""Capture and check desktop layouts at the requested Qt display scale."""

from __future__ import annotations

import argparse
import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading
import time
from unittest.mock import patch


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True

from PySide6.QtCore import QPoint
from PySide6.QtGui import QFont, QFontDatabase
from PySide6.QtWidgets import QApplication

from desktop import APP_STYLE, CalendarWindow
from calendar_models import PreviewCompleted
from calendar_preview import run_preview_job
from generate import APP_VERSION
from preview_dialogs import BatchPreviewDialog
from quote_picker_dialog import QuotePickerDialog


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    app = QApplication([])
    for filename in ("segoeui.ttf", "segoeuib.ttf", "msyh.ttc", "msyhbd.ttc", "msyhl.ttc"):
        font = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename
        if QFontDatabase.addApplicationFont(str(font)) < 0:
            raise RuntimeError(f"Could not load the installed font: {filename}")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    app.setFont(QFont("Segoe UI", 10))
    captures = []
    with tempfile.TemporaryDirectory(prefix="calendar-ui-") as scratch:
        with patch("preferences.preferences_path", return_value=Path(scratch) / "settings.json"), patch(
            "desktop.load_output_directory", return_value=Path("calendar_runs").resolve(),
        ):
            window = CalendarWindow()
            try:
                window.start.setText("20270101")
                window.layout_choice.set_selection("A+C+F")
                window.show()
                for name, width, height in (("wide", 1180, 900), ("standard", 1040, 700), ("narrow", 720, 600)):
                    for mode in ("random", "same_quote", "manual"):
                        manual = mode == "manual"
                        window.resize(width, height)
                        window.content_panel.selector.setCurrentIndex(int(manual))
                        window.generation_mode.setCurrentIndex(0 if mode == "random" else 1)
                        window.scroll_area.verticalScrollBar().setValue(0)
                        for _iteration in range(4):
                            app.processEvents()
                        for button in (window.sample_button, window.generate_button,
                                       window.preview_button, window.cancel_button,
                                       window.replay_button, window.reroll_button):
                            position = button.mapTo(window.centralWidget(), QPoint())
                            if (position.x() < 0 or position.y() < 0
                                    or position.x() + button.width() > window.centralWidget().width()
                                    or position.y() + button.height() > window.centralWidget().height()):
                                raise RuntimeError(f"Action clipped at {name}: {button.text()}")
                        if window.scroll_area.horizontalScrollBar().maximum():
                            raise RuntimeError(f"Settings overflow horizontally at {name}.")
                        filename = f"{name}-{mode}.png"
                        if not window.grab().save(str(args.output / filename)):
                            raise RuntimeError(f"Could not save {filename}")
                        captures.append({
                            "image": filename,
                            "window": [window.width(), window.height()],
                            "device_pixel_ratio": window.devicePixelRatioF(),
                            "scroll_max": window.scroll_area.verticalScrollBar().maximum(),
                        })
                window.period.grab().save(str(args.output / "dropdown.png"))
                window.period.setEnabled(False)
                window.period.grab().save(str(args.output / "dropdown-disabled.png"))
                events = queue.Queue()
                run_preview_job(window._layout_example_pages(), threading.Event(), events)
                result = None
                while not events.empty():
                    result = events.get_nowait()
                if not isinstance(result, PreviewCompleted):
                    raise RuntimeError(f"Layout examples failed: {result}")
                window._layout_images = result.images
                window._show_layouts()
                app.processEvents()
                dialog = window._layout_dialog
                dialog.resize(540, 600)
                app.processEvents()
                for button in (dialog.random_button, dialog.all_button,
                               dialog.apply_button, dialog.close_button):
                    position = button.mapTo(dialog, QPoint())
                    if (position.x() < 0 or position.x() + button.width() > dialog.width()
                            or position.y() < 0 or position.y() + button.height() > dialog.height()):
                        raise RuntimeError(f"Layout chooser action clipped: {button.text()}")
                dialog.grab().save(str(args.output / "layout-chooser.png"))
                dialog.reject()
                picker = QuotePickerDialog(window.quotes, window._date("20261127"), ("A", "B"), "", window)
                try:
                    picker.query.setText("苏轼 明月")
                    picker.show()
                    deadline = time.monotonic() + 15
                    while not picker.use_button.isEnabled() and time.monotonic() < deadline:
                        app.processEvents()
                        time.sleep(0.02)
                    if not picker.use_button.isEnabled():
                        raise RuntimeError(f"Quote picker preview failed: {picker.preview_status.text()}")
                    for name, width, height in (("wide", 1060, 760), ("narrow", 640, 600)):
                        picker.resize(width, height)
                        for _iteration in range(4):
                            app.processEvents()
                        for button in (picker.refresh_button, picker.use_button, picker.cancel_button,
                                       picker.preview_layout, picker.candidate_count):
                            position = button.mapTo(picker, QPoint())
                            if (position.x() < 0 or position.x() + button.width() > picker.width()
                                    or position.y() < 0 or position.y() + button.height() > picker.height()):
                                raise RuntimeError(f"Quote picker control clipped: {name}")
                        picker.grab().save(str(args.output / f"quote-picker-{name}.png"))
                finally:
                    picker.reject()
                    picker.deleteLater()
                window.content_panel.selector.setCurrentIndex(0)
                window.generation_mode.setCurrentIndex(0)
                window.quantity.setText("3")
                window.layout_choice.set_selection("A")
                plan = window._plan_for_settings()
                previews = queue.Queue()
                run_preview_job(plan.pages, threading.Event(), previews)
                while not previews.empty():
                    result = previews.get_nowait()
                if not isinstance(result, PreviewCompleted):
                    raise RuntimeError(f"Batch preview failed: {result}")
                batch_dialog = BatchPreviewDialog(plan.pages, result.images, window)
                try:
                    batch_dialog.show()
                    batch_dialog.next_button.click()
                    app.processEvents()
                    if batch_dialog.index != 1:
                        raise RuntimeError("Batch preview did not navigate to the next page.")
                    batch_dialog.grab().save(str(args.output / "batch-preview.png"))
                finally:
                    batch_dialog.reject()
                    batch_dialog.deleteLater()
            finally:
                window.poll_timer.stop()
                window.close()
                window.deleteLater()
                app.processEvents()
    (args.output / "report.json").write_text(
        json.dumps({"version": APP_VERSION, "captures": captures}, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"Desktop UI checks passed: {len(captures)} layouts at Qt scale {os.environ.get('QT_SCALE_FACTOR', '1')}.")


if __name__ == "__main__":
    main()
