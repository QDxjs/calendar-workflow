"""Read-only import diagnostics with bounded table rendering and full details."""

from __future__ import annotations

from PySide6.QtCore import QAbstractTableModel, QModelIndex, Qt
from PySide6.QtWidgets import (
    QAbstractItemView, QApplication, QDialog, QDialogButtonBox, QFrame,
    QHeaderView, QHBoxLayout, QLabel, QPlainTextEdit, QTableView, QTabWidget,
    QVBoxLayout, QWidget,
)

from quote_library import MAX_QUOTE_LENGTH, MIN_QUOTE_LENGTH, QuoteImportPreview


class ImportTableModel(QAbstractTableModel):
    def __init__(self, preview: QuoteImportPreview, *, issues: bool, parent: QWidget) -> None:
        super().__init__(parent)
        self.preview = preview
        self.issues = issues

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.preview.issues if self.issues else self.preview.quotes)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else (3 if self.issues else 4)

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if role == Qt.ItemDataRole.DisplayRole and orientation == Qt.Orientation.Horizontal:
            return (("位置", "处理原因", "正文") if self.issues else ("位置", "字数", "正文", "展示出处"))[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid() or role != Qt.ItemDataRole.DisplayRole:
            return None
        row = index.row()
        if self.issues:
            item = self.preview.issues[row]
            value = (item.location, item.reason, item.quote)[index.column()]
        else:
            item = self.preview.quotes[row]
            value = (self.preview.accepted_locations[row], str(len(item["quote"])), item["quote"], item["source"])[index.column()]
        return value.replace("\n", " ").replace("\r", " ")


def _plain_label(value: str, name: str = "") -> QLabel:
    label = QLabel(value)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.setWordWrap(True)
    if name:
        label.setObjectName(name)
    return label


class QuotePreviewDialog(QDialog):
    def __init__(self, preview: QuoteImportPreview, filename: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.preview = preview
        self.setWindowTitle("确认导入语录")
        self.setMinimumSize(560, 480)
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry() if screen else None
        self.resize(min(820, available.width() - 40) if available else 820,
                    min(690, available.height() - 60) if available else 690)
        layout = QVBoxLayout(self)
        layout.setContentsMargins(18, 18, 18, 16)
        layout.setSpacing(10)
        layout.addWidget(_plain_label(f"导入「{filename}」", "sectionTitle"))
        layout.addWidget(_plain_label("确认后替换本次语料；取消保留现有语料。原文件不会被修改。", "muted"))
        counts = QHBoxLayout()
        for value, caption in ((preview.total_count, "文件记录"), (len(preview.quotes), "可导入"),
                               (preview.duplicate_count, "重复"), (preview.invalid_count, "无效")):
            block = QFrame()
            block.setObjectName("quotePanel")
            box = QVBoxLayout(block)
            box.setContentsMargins(10, 7, 10, 7)
            box.addWidget(_plain_label(str(value), "statValue"), alignment=Qt.AlignmentFlag.AlignHCenter)
            box.addWidget(_plain_label(caption, "statLabel"), alignment=Qt.AlignmentFlag.AlignHCenter)
            counts.addWidget(block)
        layout.addLayout(counts)
        layout.addWidget(_plain_label(
            f"正文须为 {MIN_QUOTE_LENGTH}～{MAX_QUOTE_LENGTH} 个字符，含标点和内部空白，去除首尾空白后计数。"
            "去重忽略标点、空白等符号；超长正文不会截断。换行与缩字因版式而异，可在导入后查看首张效果。", "muted"))
        self.tabs = QTabWidget()
        self.accepted_view = self._table(issues=False)
        self.issues_view = self._table(issues=True)
        self.tabs.addTab(self.accepted_view, f"可导入（{len(preview.quotes)}）")
        self.tabs.addTab(self.issues_view, f"未导入原因（{len(preview.issues)}）")
        layout.addWidget(self.tabs, 1)
        layout.addWidget(_plain_label("选中一条记录，查看完整正文、出处及处理原因。", "muted"))
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setAccessibleName("完整记录与诊断详情")
        self.details.setMinimumHeight(110)
        self.details.setMaximumHeight(165)
        layout.addWidget(self.details)
        self.buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        self.confirm_button = self.buttons.button(QDialogButtonBox.StandardButton.Ok)
        self.confirm_button.setText("确认导入")
        self.confirm_button.setObjectName("primaryButton")
        self.confirm_button.setEnabled(bool(preview.quotes))
        self.buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        self.buttons.accepted.connect(self.accept)
        self.buttons.rejected.connect(self.reject)
        layout.addWidget(self.buttons)
        self.tabs.currentChanged.connect(self._update_details)
        for view in (self.accepted_view, self.issues_view):
            view.selectionModel().currentRowChanged.connect(self._update_details)
            if view.model().rowCount():
                view.selectRow(0)
        if not preview.quotes:
            self.tabs.setCurrentIndex(1)
        self._update_details()

    def _table(self, *, issues: bool) -> QTableView:
        view = QTableView()
        view.setModel(ImportTableModel(self.preview, issues=issues, parent=view))
        view.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        view.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        view.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        view.setWordWrap(False)
        view.setAlternatingRowColors(True)
        view.verticalHeader().hide()
        view.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Stretch)
        view.horizontalHeader().setSectionResizeMode(0, QHeaderView.ResizeMode.Fixed)
        view.setColumnWidth(0, 85)
        if not issues:
            view.horizontalHeader().setSectionResizeMode(1, QHeaderView.ResizeMode.Fixed)
            view.setColumnWidth(1, 50)
        view.setMinimumHeight(130)
        view.setAccessibleName("未导入记录及原因" if issues else "可导入正文与出处")
        return view

    def _update_details(self, *_args: object) -> None:
        issues = self.tabs.currentIndex() == 1
        view = self.issues_view if issues else self.accepted_view
        index = view.currentIndex()
        if not index.isValid():
            self.details.setPlainText("没有可导入的有效语录，请查看未导入原因并修正文件后重试。"
                                      if not self.preview.quotes else "此列表没有记录。")
            return
        row = index.row()
        if issues:
            item = self.preview.issues[row]
            quote, source, location = item.quote, item.source, item.location
            result = f"未导入：{item.reason}"
            if item.duplicate_of:
                result += f"\n保留的记录：{item.duplicate_of}"
        else:
            item = self.preview.quotes[row]
            quote, source, location = item["quote"], item["source"], self.preview.accepted_locations[row]
            result = "可导入"
        self.details.setPlainText(f"{location} · {result}\n\n正文（{len(quote)} 个字符）：\n{quote}\n\n展示出处：\n{source}")

    def accept(self) -> None:
        if self.preview.quotes:
            super().accept()
