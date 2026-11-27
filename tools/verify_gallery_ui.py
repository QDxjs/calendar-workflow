"""Exercise generated file:// galleries in the installed Qt Chromium engine.

Run separately from unittest so WebEngine owns its application lifecycle.
No network or additional packages are required beyond the pinned PySide6.
"""
from __future__ import annotations

import argparse
from datetime import date
import json
import os
from pathlib import Path
import sys
import tempfile

os.environ.setdefault('QT_QPA_PLATFORM', 'offscreen')
os.environ.setdefault('QTWEBENGINE_CHROMIUM_FLAGS', '--disable-gpu')
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
sys.dont_write_bytecode = True

from PySide6.QtCore import QEventLoop, QTimer, QUrl
from PySide6.QtWidgets import QApplication
from PySide6.QtWebEngineCore import QWebEngineUrlRequestInterceptor, QWebEnginePage, QWebEngineProfile
from PySide6.QtWebEngineWidgets import QWebEngineView
from calendar_models import CalendarPage
from generate import write_batch
from content_sources import ManualQuoteSource, plan_manual_page


class OfflineOnly(QWebEngineUrlRequestInterceptor):
    def __init__(self, parent):
        super().__init__(parent)
        self.remote = []

    def interceptRequest(self, info):
        if info.requestUrl().scheme() in ('http', 'https'):
            self.remote.append(info.requestUrl().toString())
            info.block(True)


def evaluate(page, expression):
    loop = QEventLoop()
    results = []
    page.runJavaScript(expression, 0, lambda result: (results.append(result), loop.quit()))
    QTimer.singleShot(10000, loop.quit)
    loop.exec()
    if not results:
        raise RuntimeError('Browser JavaScript timed out.')
    return results[0]


def check(page, expression, message):
    if not evaluate(page, f'Boolean({expression})'):
        raise AssertionError(message)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--screenshots', type=Path)
    args = parser.parse_args()
    app = QApplication([])
    profile = QWebEngineProfile(app)
    interceptor = OfflineOnly(profile)
    profile.setUrlRequestInterceptor(interceptor)
    view = QWebEngineView()
    page = QWebEnginePage(profile, view)
    view.setPage(page)
    view.resize(1000, 780)
    view.show()
    with tempfile.TemporaryDirectory(prefix='calendar-gallery-ui-') as temporary:
        batch = Path(temporary) / 'batch'
        days = (date(2027, 1, 1), date(2028, 1, 1), date(2028, 2, 29), date(2028, 3, 1))
        pages = [CalendarPage(day, layout, layout, f'离线浏览测试语录{index}', '测试出处')
                 for index, (day, layout) in enumerate(zip(days, 'ABCD'), start=1)]
        manual = '手写第一行\n第二行 & <script>alert("手写")</script>'
        pages[0] = plan_manual_page(days[0], ManualQuoteSource(manual), 'A', 17).pages[0]
        pages[1] = plan_manual_page(days[1], ManualQuoteSource(''), 'B', 17).pages[0]
        write_batch(pages, batch, seed=17, on_progress=lambda *_: None)
        # Deliberately broken image must not prevent navigation or close.
        (batch / 'png' / '2028-03-01_layout-D.png').unlink()
        loop = QEventLoop()
        loaded = []
        page.loadFinished.connect(lambda ok: (loaded.append(ok), loop.quit()))
        view.load(QUrl.fromLocalFile(str(batch / 'index.html')))
        QTimer.singleShot(30000, loop.quit)
        loop.exec()
        if loaded != [True]:
            raise AssertionError(f'Local gallery failed to load: {loaded}')
        js = lambda value: evaluate(page, value)
        check(page, '!document.getElementById("filters").hidden', 'Filters did not initialize.')
        check(page, 'document.querySelectorAll(".card:not([hidden])").length===4', 'Wrong initial count.')
        manual_json = json.dumps(manual, ensure_ascii=True)
        check(page, f'document.querySelector(".quote").textContent==={manual_json}', 'Manual newlines or escaping changed.')
        check(page, 'document.querySelector(".source").textContent===""', 'Empty manual attribution not preserved.')
        check(page, '[...document.querySelectorAll(".card")][1].querySelector(".quote").textContent===""', 'Blank card gained placeholder text.')
        check(page, '!document.querySelector(".card script")', 'Manual text became executable markup.')
        js('document.querySelector(".preview").click()')
        check(page, 'document.getElementById("viewer").open', 'Lightbox did not open.')
        check(page, f'document.getElementById("viewer-caption").textContent==={manual_json}', 'Lightbox manual content or escaping changed.')
        check(page, 'getComputedStyle(document.querySelector(".quote")).whiteSpace==="pre-wrap"', 'Manual visual line breaks collapsed.')
        if args.screenshots:
            args.screenshots.mkdir(parents=True, exist_ok=True)
            wait = QEventLoop()
            QTimer.singleShot(250, wait.quit)
            wait.exec()
            view.grab().save(str(args.screenshots / 'gallery-manual.png'))
        check(page, 'document.getElementById("viewer-prev").disabled', 'First page boundary missing.')
        js('document.getElementById("viewer").dispatchEvent(new KeyboardEvent("keydown",{key:"ArrowRight",bubbles:true}))')
        check(page, 'document.getElementById("viewer-title").textContent.includes("2 / 4")', 'Keyboard next failed.')
        check(page, 'document.getElementById("viewer-caption").textContent===""', 'Blank calendar lightbox did not keep an empty caption.')
        check(page, 'document.getElementById("viewer-png").getAttribute("href").includes("2028-01-01_layout-B.png")', 'Download points to wrong page.')
        js('document.getElementById("viewer-zoom").click()')
        check(page, '!document.getElementById("viewer-stage").classList.contains("fit")', 'Original size failed.')
        js('document.getElementById("viewer").close()')
        js('document.getElementById("month").value="2028-01";document.getElementById("month").dispatchEvent(new Event("change"))')
        check(page, 'document.querySelectorAll(".card:not([hidden])").length===1', 'Year-month filtering failed.')
        js('document.querySelector(".card:not([hidden]) .preview").click()')
        check(page, 'document.getElementById("viewer-prev").disabled&&document.getElementById("viewer-next").disabled', 'Filtered lightbox navigation escaped result set.')
        js('document.getElementById("search").value="NO_MATCH";document.getElementById("search").dispatchEvent(new Event("input"))')
        check(page, '!document.getElementById("viewer").open&&document.querySelectorAll(".card:not([hidden])").length===0', 'Zero-result state failed.')
        js('document.getElementById("search").value="";document.getElementById("month").value="";document.getElementById("layout").value="C";document.getElementById("layout").dispatchEvent(new Event("change"))')
        check(page, 'document.querySelectorAll(".card:not([hidden])").length===1', 'Combined filter reset failed.')
        js('document.getElementById("layout").value="";document.getElementById("layout").dispatchEvent(new Event("change"));document.querySelector(".preview").click()')
        # Actual key events exercise native Escape and browser focus restoration.
        from PySide6.QtCore import Qt
        from PySide6.QtTest import QTest
        QTest.keyClick(view.focusProxy(), Qt.Key.Key_Escape)
        wait = QEventLoop()
        QTimer.singleShot(200, wait.quit)
        wait.exec()
        check(page, '!document.getElementById("viewer").open', 'Native Escape failed.')
        check(page, 'document.activeElement.classList.contains("preview")', 'Focus did not return to trigger.')
        js('document.querySelectorAll(".preview")[3].click()')
        # An event-loop turn lets the file decoder report the missing image.
        wait = QEventLoop()
        QTimer.singleShot(300, wait.quit)
        wait.exec()
        check(page, '!document.getElementById("viewer-error").hidden', 'Missing-image message not shown.')
        js('document.getElementById("viewer-prev").click()')
        check(page, '!document.getElementById("viewer-image").hidden', 'Broken image blocked healthy page.')
        if args.screenshots:
            args.screenshots.mkdir(parents=True, exist_ok=True)
            js('document.getElementById("viewer-zoom").click()')
            wait = QEventLoop()
            QTimer.singleShot(250, wait.quit)
            wait.exec()
            view.grab().save(str(args.screenshots / 'gallery-lightbox.png'))
        if interceptor.remote:
            raise AssertionError('Gallery attempted network access.')
        print('Offline Chromium gallery passed: navigation, keyboard/Escape, focus, zoom, year-month filters, downloads, zero results and broken images.')
    view.close()
    page.deleteLater()
    app.processEvents()
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
