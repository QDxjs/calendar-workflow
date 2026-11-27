"""History window with an independent cancellable, read-only scan worker."""

from __future__ import annotations

from pathlib import Path
import queue
import threading

from PySide6.QtCore import QAbstractTableModel, QModelIndex, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QAbstractItemView, QDialog, QFileDialog, QHBoxLayout, QHeaderView,
    QLabel, QMessageBox, QPlainTextEdit, QPushButton, QTableView, QVBoxLayout, QWidget,
)

from batch_history import BatchSummary, run_history_scan
from preview_dialogs import _size_dialog


class HistoryTableModel(QAbstractTableModel):
    def __init__(self, parent: QWidget) -> None:
        super().__init__(parent)
        self.batches: list[BatchSummary] = []

    def rowCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else len(self.batches)

    def columnCount(self, parent: QModelIndex = QModelIndex()) -> int:
        return 0 if parent.isValid() else 5

    def headerData(self, section: int, orientation: Qt.Orientation, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if orientation == Qt.Orientation.Horizontal and role == Qt.ItemDataRole.DisplayRole:
            return ("批次", "日期范围", "页数", "版式", "状态")[section]
        return None

    def data(self, index: QModelIndex, role: int = Qt.ItemDataRole.DisplayRole) -> object:
        if not index.isValid():
            return None
        batch = self.batches[index.row()]
        if role == Qt.ItemDataRole.ToolTipRole:
            return str(batch.directory) + "\n" + batch.status
        if role == Qt.ItemDataRole.DisplayRole:
            return (batch.directory.name, batch.date_range, str(len(batch.pages)) if batch.pages else "—",
                    "/".join(sorted({p.layout for p in batch.pages})) or "—", batch.status)[index.column()]
        return None

    def append(self, batch: BatchSummary) -> None:
        row = len(self.batches)
        self.beginInsertRows(QModelIndex(), row, row)
        self.batches.append(batch)
        self.endInsertRows()

    def clear(self) -> None:
        self.beginResetModel()
        self.batches.clear()
        self.endResetModel()


class HistoryDialog(QDialog):
    def __init__(self, root: Path, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("历史批次")
        self.setMinimumSize(620, 420)
        _size_dialog(self, 980, 680)
        self.root = root
        self.replay_path: Path | None = None
        self.cancel_event = threading.Event()
        self.events: queue.Queue = queue.Queue()
        self._closed = False
        outer = QVBoxLayout(self)
        hint = QLabel("查找已有批次，打开网页或恢复到新目录。查看不会修改原文件；恢复使用当前模板和渲染器。")
        hint.setWordWrap(True)
        outer.addWidget(hint)
        row = QHBoxLayout()
        self.location = QLabel()
        self.location.setTextFormat(Qt.TextFormat.PlainText)
        self.location.setWordWrap(True)
        row.addWidget(self.location, 1)
        choose = QPushButton("选择历史位置…")
        choose.clicked.connect(self._choose_location)
        row.addWidget(choose)
        self.refresh_button = QPushButton("刷新")
        self.refresh_button.clicked.connect(self._refresh)
        row.addWidget(self.refresh_button)
        self.stop_button = QPushButton("停止扫描")
        self.stop_button.clicked.connect(self._cancel_scan)
        row.addWidget(self.stop_button)
        outer.addLayout(row)
        self.status = QLabel()
        self.status.setTextFormat(Qt.TextFormat.PlainText)
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        self.model = HistoryTableModel(self)
        self.table = QTableView()
        self.table.setModel(self.model)
        self.table.setSelectionBehavior(QAbstractItemView.SelectionBehavior.SelectRows)
        self.table.setSelectionMode(QAbstractItemView.SelectionMode.SingleSelection)
        self.table.setEditTriggers(QAbstractItemView.EditTrigger.NoEditTriggers)
        self.table.horizontalHeader().setSectionResizeMode(QHeaderView.ResizeMode.Interactive)
        self.table.horizontalHeader().setStretchLastSection(True)
        for column, width in enumerate((210, 230, 55, 90)):
            self.table.setColumnWidth(column, width)
        self.table.selectionModel().selectionChanged.connect(self._selection_changed)
        outer.addWidget(self.table, 1)
        self.details = QPlainTextEdit()
        self.details.setReadOnly(True)
        self.details.setMaximumHeight(135)
        self.details.setAccessibleName("批次详情")
        outer.addWidget(self.details)
        actions = QHBoxLayout()
        self.web_button = QPushButton("打开网页预览")
        self.web_button.clicked.connect(lambda: self._open(True))
        self.folder_button = QPushButton("打开批次目录")
        self.folder_button.clicked.connect(lambda: self._open(False))
        self.replay_button = QPushButton("恢复到新目录…")
        self.replay_button.clicked.connect(self._replay)
        for button in (self.web_button, self.folder_button, self.replay_button):
            actions.addWidget(button)
        actions.addStretch(1)
        close = QPushButton("关闭")
        close.clicked.connect(self.reject)
        actions.addWidget(close)
        outer.addLayout(actions)
        self.timer = QTimer(self)
        self.timer.setInterval(100)
        self.timer.timeout.connect(self._poll)
        self.timer.start()
        self._refresh()

    def _refresh(self) -> None:
        self.cancel_event.set()
        self.cancel_event = threading.Event()
        # Each scan owns its queue; a late previous result cannot enter this view.
        self.events = queue.Queue()
        self.model.clear()
        self.location.setText(str(self.root))
        self._selection_changed()
        self.status.setText("正在查找批次…")
        self.stop_button.setEnabled(True)
        threading.Thread(target=run_history_scan, args=(self.root, self.cancel_event, self.events), daemon=True).start()

    def _choose_location(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择批次所在位置或单个批次目录", str(self.root))
        if selected:
            self.root = Path(selected)
            self._refresh()

    def _cancel_scan(self) -> None:
        self.cancel_event.set()
        self.stop_button.setEnabled(False)
        self.status.setText("正在停止扫描…")

    def _poll(self) -> None:
        if self._closed:
            return
        for _ in range(100):
            try:
                kind, payload = self.events.get_nowait()
            except queue.Empty:
                break
            if kind == "batch":
                if not self.cancel_event.is_set():
                    self.model.append(payload)
                    self.status.setText(f"已找到 {len(self.model.batches)} 个批次，正在继续查找…")
            else:
                self.stop_button.setEnabled(False)
                count = len(self.model.batches)
                if kind == "error":
                    self.status.setText(f"无法完成扫描：{payload}。可选择其他位置或刷新。")
                elif kind == "cancelled":
                    self.status.setText(f"已停止扫描，保留 {count} 个已发现批次。")
                else:
                    self.status.setText(f"共找到 {count} 个批次。" if count else "此位置没有批次。可选择其他保存位置或单个批次目录。")

    def _selected(self) -> BatchSummary | None:
        rows = self.table.selectionModel().selectedRows()
        return self.model.batches[rows[0].row()] if rows else None

    def _selection_changed(self, *_args: object) -> None:
        batch = self._selected()
        exists = batch is not None and batch.directory.is_dir()
        self.web_button.setEnabled(bool(exists and (batch.directory / "index.html").is_file()))
        self.folder_button.setEnabled(exists)
        self.replay_button.setEnabled(bool(exists and batch.pages and not batch.error and (batch.directory / "manifest.csv").is_file()))
        if batch is None:
            self.details.clear()
        else:
            seed = "未固定" if batch.seed is None else str(batch.seed)
            self.details.setPlainText(f"目录：{batch.directory}\n日期：{batch.date_range}　页数：{len(batch.pages)}\n"
                                      f"种子：{seed}　程序版本：{' / '.join(batch.versions) or '未知'}\n"
                                      f"清单更新时间：{batch.manifest_updated}\n{batch.status}")

    def _open(self, web: bool) -> None:
        batch = self._selected()
        if batch is None:
            return
        target = batch.directory / "index.html" if web else batch.directory
        valid = target.is_file() if web else target.is_dir()
        if not valid or not QDesktopServices.openUrl(QUrl.fromLocalFile(str(target))):
            QMessageBox.warning(self, "无法打开批次", "文件已移动、删除，或系统未能打开。请刷新或重新选择历史位置。")
            self._selection_changed()

    def _replay(self) -> None:
        batch = self._selected()
        if batch is None or batch.error or not batch.pages:
            return
        manifest = batch.directory / "manifest.csv"
        if not manifest.is_file():
            QMessageBox.warning(self, "清单已不存在", "请刷新或重新选择历史位置。")
            self._selection_changed()
            return
        self.replay_path = manifest
        self.accept()

    def done(self, result: int) -> None:
        self._closed = True
        self.cancel_event.set()
        self.timer.stop()
        super().done(result)
