"""Compact content-source editor; manual drafts live only in this widget."""

from PySide6.QtCore import QSignalBlocker, Signal, Qt
from PySide6.QtWidgets import (
    QFrame, QHBoxLayout, QLabel, QLineEdit, QPlainTextEdit,
    QPushButton, QVBoxLayout, QWidget,
)

from content_sources import ManualQuoteSource
from desktop_widgets import SelectionComboBox


class ManualQuotePanel(QFrame):
    changed = Signal()

    def __init__(self, corpus_label: str, parent=None) -> None:
        super().__init__(parent)
        self.setObjectName("quotePanel")
        self._single_day = True
        self._busy = False
        self._custom = False
        outer = QVBoxLayout(self)
        outer.setContentsMargins(14, 12, 14, 12)
        outer.setSpacing(8)
        self.selector = SelectionComboBox()
        self.selector.setAccessibleName("内容来源")
        self.selector.addItem("语录库抽选", "corpus")
        self.selector.addItem("单日手写", "manual")
        self.selector.setToolTip("单日手写仅支持单日模式；多日自定义请导入语料或使用 CSV。")
        outer.addWidget(self.selector)
        self.corpus_area = QWidget()
        corpus = QVBoxLayout(self.corpus_area)
        corpus.setContentsMargins(0, 0, 0, 0)
        self.corpus_label = QLabel(corpus_label)
        self.corpus_label.setObjectName("quoteTitle")
        self.corpus_label.setTextFormat(Qt.TextFormat.PlainText)
        self.corpus_label.setWordWrap(True)
        corpus.addWidget(self.corpus_label)
        self.selected_label = QLabel("自动抽选 · 每张语录由程序随机选择")
        self.selected_label.setWordWrap(True)
        self.selected_label.setTextFormat(Qt.TextFormat.PlainText)
        corpus.addWidget(self.selected_label)
        choose = QHBoxLayout()
        self.pick_button = QPushButton("挑选语录 / 搜索…")
        self.auto_button = QPushButton("恢复自动抽选")
        self.auto_button.setObjectName("quietButton")
        self.auto_button.hide()
        choose.addWidget(self.pick_button)
        choose.addWidget(self.auto_button)
        choose.addStretch(1)
        corpus.addLayout(choose)
        buttons = QHBoxLayout()
        self.import_button = QPushButton("导入语录")
        self.reset_button = QPushButton("恢复内置")
        self.reset_button.setObjectName("quietButton")
        buttons.addWidget(self.import_button)
        buttons.addWidget(self.reset_button)
        buttons.addStretch(1)
        corpus.addLayout(buttons)
        outer.addWidget(self.corpus_area)
        self.manual_area = QWidget()
        manual = QVBoxLayout(self.manual_area)
        manual.setContentsMargins(0, 0, 0, 0)
        manual.setSpacing(5)
        manual.addWidget(QLabel("正文（可选，留空生成留白日历）"))
        self.quote_edit = QPlainTextEdit()
        self.quote_edit.setAccessibleName("手写正文")
        self.quote_edit.setPlaceholderText("写下今天的文字，可换行；留空可生成留白日历")
        self.quote_edit.setFixedHeight(88)
        self.quote_edit.setTabChangesFocus(True)
        manual.addWidget(self.quote_edit)
        self.quote_error = self._error_label()
        manual.addWidget(self.quote_error)
        self.count_label = QLabel()
        self.count_label.setObjectName("sectionHint")
        self.count_label.setWordWrap(True)
        manual.addWidget(self.count_label)
        self.source_edit = QLineEdit()
        self.source_edit.setAccessibleName("手写出处（可选）")
        self.source_edit.setPlaceholderText("出处（可选），例如：《诗经》 · 无名氏")
        manual.addWidget(self.source_edit)
        self.source_error = self._error_label()
        manual.addWidget(self.source_error)
        hint = QLabel("草稿仅在本次打开期间保留；视觉断行由版式自动平衡。")
        hint.setObjectName("sectionHint")
        hint.setWordWrap(True)
        manual.addWidget(hint)
        self.clear_button = QPushButton("清空输入")
        self.clear_button.setObjectName("quietButton")
        manual.addWidget(self.clear_button)
        outer.addWidget(self.manual_area)
        self.selector.currentIndexChanged.connect(self._changed)
        self.quote_edit.textChanged.connect(self._changed)
        self.source_edit.textChanged.connect(self._changed)
        self.clear_button.clicked.connect(self.clear_draft)
        self._changed()

    @staticmethod
    def _error_label():
        label = QLabel()
        label.setObjectName("fieldError")
        label.setWordWrap(True)
        label.setTextFormat(Qt.TextFormat.PlainText)
        label.hide()
        return label

    @property
    def is_manual(self) -> bool:
        return self._single_day and self.selector.currentData() == "manual"

    def content(self) -> ManualQuoteSource:
        return ManualQuoteSource(self.quote_edit.toPlainText(), self.source_edit.text())

    def set_single_day(self, enabled: bool) -> None:
        self._single_day = enabled
        if not enabled:
            with QSignalBlocker(self.selector):
                self.selector.setCurrentIndex(0)
        self._sync()

    def set_state(self, *, busy: bool, custom: bool) -> None:
        self._busy, self._custom = busy, custom
        self._sync()

    def _sync(self) -> None:
        self.selector.setEnabled(not self._busy)
        self.selector.model().item(1).setEnabled(self._single_day and not self._busy)
        self.corpus_area.setVisible(not self.is_manual)
        self.manual_area.setVisible(self.is_manual)
        self.import_button.setEnabled(not self._busy)
        self.reset_button.setEnabled(not self._busy and self._custom)
        self.pick_button.setEnabled(not self._busy and self._single_day)
        self.pick_button.setToolTip("从完整语录库推荐或搜索，确认后进入同语录换版式。" if self._single_day else "语录挑选先支持单日；多日按每个日期自动抽选。")
        self.auto_button.setEnabled(not self._busy)
        for widget in (self.quote_edit, self.source_edit, self.clear_button):
            widget.setEnabled(not self._busy)

    def set_selected_quote(self, quote: dict[str, str] | None, *, active: bool, random_mode: bool) -> None:
        self.auto_button.setVisible(quote is not None)
        if quote is not None:
            state = "已选定" if active else "已保留，切回单日同语录模式使用"
            self.selected_label.setText(f"{state}\n{quote['quote']}\n{quote['source']}")
        else:
            self.selected_label.setText("自动抽选 · 每张独立随机语录" if random_mode else "自动抽选 · 每个日期一条语录，应用到所选版式")

    def show_error(self, field: str = "", message: str = "") -> None:
        for name, label, widget in (("quote", self.quote_error, self.quote_edit),
                                     ("source", self.source_error, self.source_edit)):
            error = message if field == name else ""
            label.setText(error)
            label.setVisible(bool(error) and self.is_manual)
            widget.setProperty("invalid", bool(error))
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _changed(self, *_args) -> None:
        count = len(self.quote_edit.toPlainText().strip())
        warning = " · 超过 58 字，将按实际版式试排；可精简或调整换行。" if count > 58 else ""
        self.count_label.setText(f"{count} 字{warning}")
        self._sync()
        self.changed.emit()

    def clear_draft(self) -> None:
        if self._busy:
            return
        with QSignalBlocker(self.quote_edit), QSignalBlocker(self.source_edit):
            self.quote_edit.clear()
            self.source_edit.clear()
        self._changed()
