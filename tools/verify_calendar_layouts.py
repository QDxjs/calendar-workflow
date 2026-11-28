"""Check the corpus across all layouts and render the reported overlap case."""

from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.dont_write_bytecode = True

from PySide6.QtCore import QRect, Qt
from PySide6.QtGui import QColor, QFont, QFontDatabase, QImage, QPainter
from PySide6.QtWidgets import QApplication

from generate import APP_VERSION, LAYOUT_LABELS, RENDERERS, metadata, prepare_replay, validate_png, write_batch
from launcher import plan_pages
from quote_library import builtin_quotes


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    quotes = builtin_quotes()
    checks = 0
    for quote in quotes:
        for layout, renderer in RENDERERS.items():
            root = ET.fromstring(renderer(metadata(date(2026, 11, 28), layout, quote["quote"], quote["source"])))
            if (root.attrib["width"], root.attrib["height"]) != ("1122", "1402"):
                raise ValueError(f"Canvas size changed: {layout}")
            checks += 1
    quote = next(item for item in quotes if item["quote"].startswith("我们不能轻易将"))
    pages = plan_pages([date(2026, 11, 28)], [quote], "+".join(RENDERERS), 17)
    batch = args.output / "screenshot-case"
    write_batch(pages, batch, seed=17, on_progress=lambda *_: None)
    if prepare_replay(batch / "manifest.csv") != (pages, 17):
        raise ValueError("Multiple-layout replay differs from its original plan.")
    app = QApplication.instance() or QApplication([])
    for name in ("msyh.ttc", "msyhbd.ttc"):
        QFontDatabase.addApplicationFont(str(Path(os.environ.get("WINDIR", "C:/Windows")) / "Fonts" / name))
    sheet = QImage(1170, 1560, QImage.Format.Format_RGB32)
    sheet.fill(QColor("#e8ebf0"))
    painter = QPainter(sheet)
    painter.setRenderHint(QPainter.RenderHint.SmoothPixmapTransform)
    painter.setFont(QFont("Microsoft YaHei", 12))
    for index, page in enumerate(pages):
        image_path = batch / "png" / f"{page.target_date}_layout-{page.layout}.png"
        validate_png(image_path)
        image = QImage(str(image_path))
        left, upper = 20 + index % 3 * 390, 20 + index // 3 * 520
        painter.drawText(QRect(left, upper, 350, 35), Qt.AlignmentFlag.AlignCenter,
                         f"{page.layout} · {LAYOUT_LABELS[page.layout]}")
        painter.drawImage(QRect(left, upper + 40, 350, 437), image)
        if page.layout == "C":
            image.copy(100, 900, 922, 360).save(str(args.output / "c-quote-detail.png"))
    painter.end()
    if not sheet.save(str(args.output / "nine-layouts.png")):
        raise RuntimeError("Could not save the layout contact sheet.")
    report = {"version": APP_VERSION, "quotes": len(quotes), "svg_layout_checks": checks,
              "png_pages": len(pages), "canvas": [1122, 1402], "quote_id": quote["quote_id"]}
    (args.output / "report.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    app.processEvents()
    print(f"Calendar layout checks passed: {checks} SVGs, {len(pages)} original-size PNGs, replay and screenshot regression.")


if __name__ == "__main__":
    main()
