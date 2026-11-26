"""Render actual Qt widgets and calendar exports for the README on Windows."""

from __future__ import annotations

import json
import os
from pathlib import Path
import queue
import sys
import tempfile
import threading


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ["QT_QPA_PLATFORM"] = "offscreen"
sys.dont_write_bytecode = True

from PySide6.QtCore import QRect, QRectF, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QIcon, QImage, QPainter, QPixmap
from PySide6.QtWidgets import QApplication, QWidget

from calendar_models import PreviewCompleted
from calendar_preview import run_preview_job
from desktop import APP_STYLE, CalendarWindow
from generate import APP_VERSION, LAYOUT_LABELS, prepare_pages, write_batch
from preview_dialogs import FirstPageDialog
from quote_import_dialog import QuotePreviewDialog
from quote_library import inspect_quotes


IMAGES = ROOT / "docs" / "images"


def capture(app: QApplication, widget: QWidget, filename: str) -> None:
    widget.show()
    app.processEvents()
    widget.setFocus()
    app.processEvents()
    image = QPixmap(widget.size() * 2)
    image.setDevicePixelRatio(2)
    image.fill(Qt.GlobalColor.transparent)
    widget.render(image)
    if not image.save(str(IMAGES / filename)):
        raise RuntimeError(f"Could not save {filename}")
    widget.hide()


def montage(source_images: dict[str, QImage], filename: str, layouts: str,
            columns: int, card_width: int) -> None:
    margin, gap, label_height = 28, 22, 58
    card_height = round(card_width * 1402 / 1122)
    rows = (len(layouts) + columns - 1) // columns
    width = margin * 2 + columns * card_width + (columns - 1) * gap
    height = margin * 2 + rows * (card_height + label_height) + (rows - 1) * gap
    image = QImage(width, height, QImage.Format.Format_RGB32)
    image.fill(QColor("#f3f4f7"))
    painter = QPainter(image)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setFont(QFont("Microsoft YaHei UI", 16, QFont.Weight.Medium))
    for index, layout in enumerate(layouts):
        x = margin + (index % columns) * (card_width + gap)
        y = margin + (index // columns) * (card_height + label_height + gap)
        painter.fillRect(QRect(x, y, card_width, card_height + label_height), QColor("#ffffff"))
        painter.drawImage(QRectF(x, y, card_width, card_height), source_images[layout])
        painter.setPen(QColor("#33394a"))
        painter.drawText(QRect(x, y + card_height, card_width, label_height),
                         Qt.AlignmentFlag.AlignCenter, f"{layout} · {LAYOUT_LABELS[layout]}")
    painter.end()
    if not image.save(str(IMAGES / filename)):
        raise RuntimeError(f"Could not save {filename}")


def main() -> None:
    app = QApplication([])
    for filename in ("segoeui.ttf", "segoeuib.ttf", "msyh.ttc", "msyhbd.ttc", "msyhl.ttc"):
        path = Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / filename
        if QFontDatabase.addApplicationFont(str(path)) < 0:
            raise RuntimeError(f"Could not load the installed Windows font: {filename}")
    app.setApplicationName("每日文学日历")
    app.setWindowIcon(QIcon(str(ROOT / "assets/calendar.ico")))
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    app.setFont(QFont("Segoe UI", 10))
    IMAGES.mkdir(parents=True, exist_ok=True)

    window = CalendarWindow()
    window.poll_timer.stop()
    window.resize(1120, 740)
    window.output_root = Path("calendar_runs")
    window.output_path.setText("calendar_runs")
    window.output_path.setToolTip("calendar_runs")
    window.start.setText("20270101")
    window.seed.setText("31415")
    capture(app, window, "desktop.png")

    with tempfile.TemporaryDirectory(prefix="calendar-readme-") as scratch:
        scratch_root = Path(scratch)
        batch = scratch_root / "template-gallery"
        pages = (prepare_pages(ROOT / "examples/template_gallery.csv")
                 + prepare_pages(ROOT / "examples/template_gallery_F-I.csv"))
        write_batch(pages, batch, seed=31415, on_progress=lambda *_: None)
        source_images = {
            layout: QImage(str(batch / "png" / f"2027-01-01_layout-{layout}.png"))
            for layout in LAYOUT_LABELS
        }
        if any(image.isNull() or (image.width(), image.height()) != (1122, 1402)
               for image in source_images.values()):
            raise RuntimeError("Generated calendar dimensions are unexpected")
        montage(source_images, "calendar-examples.png", "ACD", 3, 500)
        montage(source_images, "all-layouts.png", "ABCDEFGHI", 3, 380)
        if not source_images["C"].save(str(IMAGES / "calendar-single.png")):
            raise RuntimeError("Could not save the full-resolution calendar")

        quote, source = pages[0].quote, pages[0].source
        demo_file = scratch_root / "readme-quotes.json"
        demo_file.write_text(json.dumps([
            {"name": quote, "from": source},
            {"name": "天地玄黄，宇宙洪荒。", "from": "周兴嗣《千字文》"},
            {"name": quote, "from": source},
            {"name": "短", "from": "演示记录"},
        ], ensure_ascii=False, indent=2), encoding="utf-8")
        inspected = inspect_quotes(demo_file)
        dialog = QuotePreviewDialog(inspected, demo_file.name, window)
        dialog.tabs.setCurrentIndex(1)
        capture(app, dialog, "quote-import.png")
        dialog.close()

        # Reproduce the state after confirming a one-quote demonstration corpus.
        demo_file.write_text(json.dumps([{"name": quote, "from": source}], ensure_ascii=False),
                             encoding="utf-8")
        window.quotes = inspect_quotes(demo_file).quotes
        window.corpus_label.setText("readme-quotes.json · 1 条")
        window._custom_quotes = True
        window.layout_choice.setCurrentIndex(window.layout_choice.findData("C"))
        window._refresh_summary()
        plan = window._plan_for_settings()
        events = queue.Queue()
        run_preview_job(plan.pages[:1], threading.Event(), events)
        received = [events.get_nowait() for _ in range(events.qsize())]
        completed = received[-1]
        if not isinstance(completed, PreviewCompleted):
            raise RuntimeError(f"First-page rendering failed: {completed}")
        image = completed.images[0][1]
        if image != (batch / "png" / "2027-01-01_layout-C.png").read_bytes():
            raise RuntimeError("The first-page preview differs from the calendar export")
        sample = FirstPageDialog(plan.pages[0], image, len(plan.pages), window)
        capture(app, sample, "first-page-preview.png")
        sample.close()
    window.close()
    print(f"Rendered README images with Calendar Workflow {APP_VERSION}.")
    for path in sorted(IMAGES.glob("*.png")):
        image = QImage(str(path))
        print(f"{path.name}: {image.width()} x {image.height()}, {path.stat().st_size:,} bytes")


if __name__ == "__main__":
    main()
