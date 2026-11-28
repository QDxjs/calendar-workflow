"""Single-day corpus selection with recommendations, search and real previews."""

from __future__ import annotations

from datetime import date
import queue
import random
import threading

from PySide6.QtCore import QEvent, QSize, Qt, QTimer
from PySide6.QtGui import QPixmap
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QHBoxLayout, QLabel, QLineEdit, QListWidget,
    QListWidgetItem, QPushButton, QScrollArea, QSplitter, QVBoxLayout, QWidget,
)

from calendar_models import CalendarPage, GenerationFailed, PreviewCompleted
from calendar_preview import run_preview_job
from desktop_widgets import SelectionComboBox
from generate import LAYOUT_LABELS
from preview_dialogs import _size_dialog
from quote_selection import CandidateSampler, QuoteSearch


class QuotePickerDialog(QDialog):
    def __init__(self, quotes: list[dict[str, str]], target_date: date,
                 layouts: tuple[str, ...], creator: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("挑选语录 · 随机推荐与搜索")
        _size_dialog(self, 1060, 780)
        self.setMinimumSize(min(600, self.width()), min(500, self.height()))
        self.search_index = QuoteSearch(quotes)
        self.sampler = CandidateSampler()
        self.target_date, self.creator = target_date, creator
        self.records: list[dict[str, str]] = []
        self._committed: dict[str, str] | None = None
        self._serial = 0
        self._closed = False
        self._cancel = threading.Event()
        self._events: queue.Queue = queue.Queue()
        self.pixmap = QPixmap()
        self._ready_serial = -1
        outer = QVBoxLayout(self)
        hint = QLabel("先看 3–5 条候选，或按正文、作者、作品搜索；确认后只使用选中的一条语录。候选条数不影响导出张数。")
        hint.setWordWrap(True)
        outer.addWidget(hint)
        self.query = QLineEdit()
        self.query.setAccessibleName("搜索整个当前语录库")
        self.query.setPlaceholderText("搜索正文 / 作者 / 作品；可输入片段或多个关键词，如：苏轼 明月")
        self.query.setClearButtonEnabled(True)
        outer.addWidget(self.query)
        tools = QHBoxLayout()
        tools.addWidget(QLabel("推荐候选"))
        self.candidate_count = SelectionComboBox()
        for count in (3, 5):
            self.candidate_count.addItem(f"{count} 条", count)
        self.candidate_count.setCurrentIndex(1)
        tools.addWidget(self.candidate_count)
        self.refresh_button = QPushButton("换一组候选")
        tools.addWidget(self.refresh_button)
        tools.addStretch(1)
        tools.addWidget(QLabel("预览版式"))
        self.preview_layout = SelectionComboBox()
        pool = layouts or tuple(LAYOUT_LABELS)
        for letter in pool:
            self.preview_layout.addItem(f"{letter} · {LAYOUT_LABELS[letter]}", letter)
        if not layouts:
            self.preview_layout.setCurrentIndex(random.randrange(len(pool)))
        tools.addWidget(self.preview_layout)
        outer.addLayout(tools)
        self.results_label = QLabel()
        self.results_label.setWordWrap(True)
        outer.addWidget(self.results_label)
        self.splitter = QSplitter(Qt.Orientation.Horizontal)
        self.list = QListWidget()
        self.list.setAccessibleName("语录候选和搜索结果")
        self.list.setWordWrap(True)
        self.list.setTextElideMode(Qt.TextElideMode.ElideNone)
        self.list.setSpacing(7)
        self.list.setVerticalScrollMode(QAbstractItemView.ScrollMode.ScrollPerPixel)
        self.splitter.addWidget(self.list)
        right = QWidget()
        right_layout = QVBoxLayout(right)
        right_layout.setContentsMargins(0, 0, 0, 0)
        self.preview_status = QLabel("选择左侧语录，查看真实日历效果。")
        self.preview_status.setWordWrap(True)
        self.preview_status.setTextFormat(Qt.TextFormat.PlainText)
        right_layout.addWidget(self.preview_status)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image = QLabel()
        self.scroll.setWidget(self.image)
        self.scroll.viewport().installEventFilter(self)
        self.list.viewport().installEventFilter(self)
        right_layout.addWidget(self.scroll, 1)
        self.splitter.addWidget(right)
        self.splitter.setSizes([480, 520])
        outer.addWidget(self.splitter, 1)
        actions = QHBoxLayout()
        self.use_button = QPushButton("使用这条")
        self.use_button.setObjectName("primaryButton")
        self.use_button.setEnabled(False)
        self.use_button.clicked.connect(self.accept)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.clicked.connect(self.reject)
        actions.addStretch(1)
        actions.addWidget(self.use_button)
        actions.addWidget(self.cancel_button)
        outer.addLayout(actions)
        self.search_timer = QTimer(self)
        self.search_timer.setSingleShot(True)
        self.search_timer.setInterval(180)
        self.search_timer.timeout.connect(self._search)
        self.preview_timer = QTimer(self)
        self.preview_timer.setSingleShot(True)
        self.preview_timer.setInterval(160)
        self.preview_timer.timeout.connect(self._start_preview)
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(60)
        self.poll_timer.timeout.connect(self._poll)
        self.poll_timer.start()
        self.query.textChanged.connect(self._query_changed)
        self.refresh_button.clicked.connect(self._recommend)
        self.candidate_count.currentIndexChanged.connect(self._recommend)
        self.list.currentRowChanged.connect(self._selection_changed)
        self.preview_layout.currentIndexChanged.connect(self._selection_changed)
        self.query.installEventFilter(self)
        self._recommend()

    @property
    def selected_quote(self) -> dict[str, str] | None:
        return dict(self._committed) if self._committed is not None else None

    def _query_changed(self) -> None:
        self._invalidate_preview()
        self.list.clear()
        self.records = []
        self.results_label.setText("正在搜索当前完整语录库…")
        self.search_timer.start()

    def _search(self) -> None:
        self.search_timer.stop()
        if not self.query.text().strip():
            self._recommend()
            return
        results = self.search_index.search(self.query.text())
        self._set_records(results, f"搜索结果：{len(results)} 条 · 点击可预览，也可从结果中随机推荐。")

    def _recommend(self, *_args) -> None:
        self.search_timer.stop()
        pool = self.search_index.search(self.query.text())
        records = self.sampler.recommend(pool, self.candidate_count.currentData())
        cycle = " · 当前范围已看完，开始新一轮" if self.sampler.restarted else " · 本轮推荐不重复"
        scope = "匹配范围" if self.query.text().strip() else "当前语录库"
        self._set_records(records, f"{scope} {len(pool)} 条 · 本组候选 {len(records)} 条{cycle}")

    def _set_records(self, records: list[dict[str, str]], message: str) -> None:
        self.list.clear()
        self.records = records
        self.results_label.setText(message if records else "没有匹配语录。请缩短片段或减少关键词。")
        for record in records:
            item = QListWidgetItem(f"{record['quote']}\n\n{record['source'] or '（无出处）'}")
            item.setToolTip(item.text())
            self.list.addItem(item)
        self._invalidate_preview()
        self._resize_rows()
        if records:
            self.list.setCurrentRow(0)
        else:
            self.preview_status.setText("没有可预览的语录。")

    def _invalidate_preview(self) -> None:
        self._serial += 1
        self._cancel.set()
        self.preview_timer.stop()
        self._ready_serial = -1
        self.pixmap = QPixmap()
        self.image.clear()
        self.use_button.setEnabled(False)

    def _selection_changed(self, *_args) -> None:
        self._invalidate_preview()
        if 0 <= self.list.currentRow() < len(self.records):
            self.preview_status.setText("正在准备所选语录的日历预览…")
            self.preview_timer.start()

    def _start_preview(self) -> None:
        index = self.list.currentRow()
        if not 0 <= index < len(self.records) or self._closed:
            return
        quote = self.records[index]
        layout = self.preview_layout.currentData()
        page = CalendarPage(self.target_date, layout, layout, quote["quote"], quote["source"],
                            quote["quote_id"], self.creator)
        self._cancel = threading.Event()
        serial, cancel = self._serial, self._cancel

        def render() -> None:
            events = queue.Queue()
            run_preview_job((page,), cancel, events)
            while not events.empty():
                self._events.put((serial, events.get_nowait()))

        threading.Thread(target=render, daemon=True).start()

    def _poll(self) -> None:
        while not self._events.empty():
            serial, event = self._events.get_nowait()
            if self._closed or serial != self._serial:
                continue
            if isinstance(event, PreviewCompleted):
                pixmap = QPixmap()
                if not pixmap.loadFromData(event.images[0][1], "PNG"):
                    self.preview_status.setText("预览图片无法读取，请重新选择。")
                    continue
                self.pixmap = pixmap
                self._ready_serial = serial
                self.use_button.setEnabled(True)
                self.preview_status.setText(f"{self.target_date} · 版式 {self.preview_layout.currentData()} · 1122 × 1402")
                self._resize_image()
            elif isinstance(event, GenerationFailed):
                self.preview_status.setText(f"此版式试排失败，请选择其他版式或语录：{event.error}")

    def accept(self) -> None:
        index = self.list.currentRow()
        if self._ready_serial != self._serial or not 0 <= index < len(self.records):
            return
        self._committed = dict(self.records[index])
        super().accept()

    def done(self, result: int) -> None:
        self._closed = True
        self._cancel.set()
        self.preview_timer.stop()
        self.search_timer.stop()
        self.poll_timer.stop()
        super().done(result)

    def eventFilter(self, watched, event) -> bool:
        if (watched is self.query and event.type() == QEvent.Type.KeyPress
                and event.key() in (Qt.Key.Key_Return, Qt.Key.Key_Enter)):
            self._search()
            return True
        if watched is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._resize_image()
        if watched is self.list.viewport() and event.type() == QEvent.Type.Resize:
            self._resize_rows()
        return super().eventFilter(watched, event)

    def resizeEvent(self, event) -> None:
        super().resizeEvent(event)
        if hasattr(self, "splitter"):
            self.splitter.setOrientation(Qt.Orientation.Vertical if self.width() < 780 else Qt.Orientation.Horizontal)
            self._resize_rows()

    def _resize_rows(self) -> None:
        width = max(150, self.list.viewport().width() - 28)
        for index in range(self.list.count()):
            item = self.list.item(index)
            rect = self.list.fontMetrics().boundingRect(0, 0, width, 10000,
                                                       Qt.TextFlag.TextWordWrap, item.text())
            item.setSizeHint(QSize(width, rect.height() + 24))

    def _resize_image(self) -> None:
        if self.pixmap.isNull():
            return
        scaled = self.pixmap.scaled((self.scroll.viewport().size() - QSize(4, 4)).expandedTo(QSize(1, 1)),
                                    Qt.AspectRatioMode.KeepAspectRatio,
                                    Qt.TransformationMode.SmoothTransformation)
        self.image.setPixmap(scaled)
        self.image.resize(scaled.size())
