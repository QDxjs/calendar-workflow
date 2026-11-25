"""Modern Qt desktop interface for the offline literature calendar."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import queue
import sys
import threading

from PySide6.QtCore import QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QComboBox,
    QDialog,
    QDialogButtonBox,
    QFileDialog,
    QFrame,
    QHBoxLayout,
    QLabel,
    QLineEdit,
    QMainWindow,
    QMessageBox,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from calendar_models import (
    GenerationCancelled,
    GenerationCompleted,
    GenerationEvent,
    GenerationFailed,
    GenerationProgress,
)
from generate import LAYOUT_LABELS, prepare_replay
from generation_service import PagePreparation, run_generation_job
from launcher import OUTPUT_ROOT, plan_pages, unique_output_dir
from periods import dates_between, dates_in_iso_week, dates_in_month, dates_in_year
from preferences import load_output_directory, save_output_directory
from quote_library import QUOTE_DIRECTORY, builtin_quotes, inspect_quotes


APP_STYLE = """
QWidget {
    color: #202435;
    font-family: "Segoe UI", "Microsoft YaHei UI", sans-serif;
    font-size: 13px;
}
QMainWindow, QWidget#page, QScrollArea, QWidget#scrollContent { background: #f4f6fa; }
QLabel#pageTitle { color: #191d2d; font-size: 24px; font-weight: 700; }
QLabel#pageSubtitle { color: #777e90; font-size: 13px; }
QFrame#card { background: white; border: 1px solid #e8eaf1; border-radius: 15px; }
QLabel#sectionTitle { color: #222638; font-size: 15px; font-weight: 700; }
QLabel#sectionHint { color: #8a90a1; font-size: 11px; }
QLabel#fieldLabel { color: #555b6d; font-size: 12px; font-weight: 600; }
QLineEdit, QComboBox {
    color: #24283a; background: #fbfcfe; border: 1px solid #dfe3ec; border-radius: 8px;
    padding: 9px 10px; min-height: 20px; selection-background-color: #7357e8;
}
QLineEdit:focus, QComboBox:focus { border: 1px solid #8069eb; background: white; }
QLineEdit:disabled { color: #82889a; background: #f4f5f8; }
QComboBox::drop-down { border: none; width: 26px; }
QComboBox QAbstractItemView { background: white; border: 1px solid #dfe3ec; selection-background-color: #eeeaff; }
QPushButton {
    color: #41465a; background: white; border: 1px solid #dfe3ec; border-radius: 8px;
    padding: 9px 12px; font-weight: 600;
}
QPushButton:hover { background: #f7f6ff; border-color: #bcb1f5; }
QPushButton:disabled { color: #a9adba; background: #f3f4f7; border-color: #eceef2; }
QPushButton#primaryButton { color: white; background: #7054e8; border: 1px solid #7054e8; padding: 12px 18px; font-size: 14px; }
QPushButton#primaryButton:hover { background: #6044d7; border-color: #6044d7; }
QPushButton#quietButton { color: #666b7b; background: transparent; border-color: transparent; }
QPushButton#quietButton:hover { color: #5440bd; background: #f4f1ff; }
QFrame#quotePanel { background: #f7f6ff; border: 1px solid #ebe7ff; border-radius: 10px; }
QLabel#quoteTitle { color: #393250; font-weight: 700; }
QLabel#muted { color: #82889a; }
QLabel#statValue { color: #24283a; font-size: 18px; font-weight: 700; }
QLabel#statLabel { color: #898fa0; font-size: 11px; }
QLabel#status { color: #777e90; font-size: 12px; }
QLabel#status[status="error"] { color: #bd3a4a; }
QProgressBar { background: #eceef4; border: none; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: #785eea; border-radius: 4px; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #d5d9e4; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QDialog { background: #f8f9fc; }
QTextBrowser { background: white; border: 1px solid #e4e7ef; border-radius: 8px; padding: 10px; }
"""


def _label(text: str, object_name: str | None = None) -> QLabel:
    label = QLabel(text)
    if object_name:
        label.setObjectName(object_name)
    return label


def _card() -> QFrame:
    frame = QFrame()
    frame.setObjectName("card")
    return frame


def _field(label_text: str, widget: QWidget) -> QWidget:
    wrapper = QWidget()
    layout = QVBoxLayout(wrapper)
    layout.setContentsMargins(0, 0, 0, 0)
    layout.setSpacing(6)
    layout.addWidget(_label(label_text, "fieldLabel"))
    layout.addWidget(widget)
    return wrapper


class QuotePreviewDialog(QDialog):
    def __init__(self, preview: object, filename: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setWindowTitle("确认导入语录")
        self.setMinimumWidth(470)
        self.preview = preview
        layout = QVBoxLayout(self)
        layout.setContentsMargins(24, 22, 24, 18)
        layout.setSpacing(13)
        layout.addWidget(_label(f"导入「{filename}」", "sectionTitle"))
        layout.addWidget(_label("确认后将替换本次运行中的语料；取消不会更改现有语料。", "muted"))

        counts = QHBoxLayout()
        counts.setSpacing(10)
        for value, caption in (
            (preview.total_count, "文件记录"),
            (len(preview.quotes), "可导入"),
            (preview.duplicate_count, "重复"),
            (preview.invalid_count, "无效"),
        ):
            block = QFrame()
            block.setObjectName("quotePanel")
            block_layout = QVBoxLayout(block)
            block_layout.setContentsMargins(12, 9, 12, 9)
            block_layout.addWidget(_label(str(value), "statValue"), alignment=Qt.AlignmentFlag.AlignHCenter)
            block_layout.addWidget(_label(caption, "statLabel"), alignment=Qt.AlignmentFlag.AlignHCenter)
            counts.addWidget(block)
        layout.addLayout(counts)

        samples = "\n".join(f"• {item['quote'][:54]}" for item in preview.quotes[:5]) or "没有可导入的有效语录。"
        sample_view = QLabel(f"内容样例\n\n{samples}")
        sample_view.setWordWrap(True)
        sample_view.setTextFormat(Qt.TextFormat.PlainText)
        sample_view.setObjectName("muted")
        layout.addWidget(sample_view)

        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Cancel | QDialogButtonBox.StandardButton.Ok)
        buttons.button(QDialogButtonBox.StandardButton.Ok).setText("确认导入")
        buttons.button(QDialogButtonBox.StandardButton.Ok).setObjectName("primaryButton")
        buttons.button(QDialogButtonBox.StandardButton.Cancel).setText("取消")
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)


class CalendarWindow(QMainWindow):
    def __init__(self, *, smoke_output: Path | None = None, smoke_year: bool = False) -> None:
        super().__init__()
        self.smoke_output = smoke_output
        self.smoke_year = smoke_year
        self.exit_code = 0
        self.running = False
        self.closing = False
        self.latest_output_dir: Path | None = None
        self.events: queue.Queue[GenerationEvent] = queue.Queue()
        self.cancel_event = threading.Event()
        packaged = getattr(sys, "frozen", False)
        self.output_root = Path(OUTPUT_ROOT) if packaged else load_output_directory(OUTPUT_ROOT)
        if smoke_output is not None:
            self.output_root = smoke_output
        if packaged and smoke_output is None:
            try:
                self.output_root.mkdir(parents=True, exist_ok=True)
            except OSError as exc:
                raise OSError(
                    f"无法在程序目录创建 calendar_runs：{exc}\n"
                    "请将便携软件解压到有写入权限的位置后重试。"
                ) from exc
        self.quotes = builtin_quotes()
        self.setWindowTitle("每日文学日历")
        screen = QApplication.primaryScreen()
        available = screen.availableGeometry().size() if screen is not None else None
        available_width = available.width() if available is not None else 1280
        available_height = available.height() if available is not None else 800
        minimum_width = min(850, max(620, available_width - 40))
        minimum_height = min(600, max(480, available_height - 40))
        self.setMinimumSize(minimum_width, minimum_height)
        self.resize(
            max(minimum_width, min(1040, int(available_width * 0.86))),
            max(minimum_height, min(700, int(available_height * 0.88))),
        )
        self._build()
        QTimer.singleShot(0, self._update_responsive_layout)
        self._refresh_summary()
        self.poll_timer = QTimer(self)
        self.poll_timer.setInterval(100)
        self.poll_timer.timeout.connect(self._poll)
        self.poll_timer.start()
        if smoke_output is not None:
            QTimer.singleShot(250, self._smoke)

    def _build(self) -> None:
        page = QWidget()
        page.setObjectName("page")
        outer = QHBoxLayout(page)
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setFrameShape(QFrame.Shape.NoFrame)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        content.setObjectName("scrollContent")
        content_layout = QVBoxLayout(content)
        content_layout.setContentsMargins(28, 24, 28, 26)
        content_layout.setSpacing(16)

        header = QHBoxLayout()
        header.setSpacing(16)
        title_block = QVBoxLayout()
        title_block.setSpacing(4)
        title_block.addWidget(_label("每日文学日历", "pageTitle"))
        title_block.addWidget(_label("挑选日期与版式，把喜欢的文字变成可以收藏的日历。", "pageSubtitle"))
        header.addLayout(title_block, 1)
        open_folder = QPushButton("打开日历文件夹")
        open_folder.clicked.connect(self._open_output)
        header.addWidget(open_folder)
        content_layout.addLayout(header)

        self.body_layout = QBoxLayout(QBoxLayout.Direction.LeftToRight)
        self.body_layout.setSpacing(16)
        self.settings_card = self._settings_card()
        self.summary_card = self._summary_card()
        self.body_layout.addWidget(self.settings_card, 3)
        self.body_layout.addWidget(self.summary_card, 2)
        content_layout.addLayout(self.body_layout)
        content_layout.addStretch(1)
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        self.scroll_area = scroll
        self.setCentralWidget(page)
        self.statusBar().setSizeGripEnabled(False)
        self.statusBar().showMessage("离线可用 · 内容仅保存在本机")

    def resizeEvent(self, event: object) -> None:
        super().resizeEvent(event)
        self._update_responsive_layout()

    def _update_responsive_layout(self) -> None:
        if not hasattr(self, "body_layout") or not hasattr(self, "scroll_area"):
            return
        content_width = self.scroll_area.viewport().width() - 56
        direction = (
            QBoxLayout.Direction.LeftToRight
            if content_width >= 930
            else QBoxLayout.Direction.TopToBottom
        )
        if self.body_layout.direction() != direction:
            self.body_layout.setDirection(direction)

    def _settings_card(self) -> QWidget:
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 17, 18, 18)
        layout.setSpacing(12)
        layout.addWidget(_label("生成设置", "sectionTitle"))
        layout.addWidget(_label("选择生成范围、页面风格与语录来源。", "sectionHint"))

        self.period = QComboBox()
        self.period.addItems(("单日", "日期范围", "一周", "月份", "年份"))
        self.period.currentTextChanged.connect(self._update_fields)
        self.period.currentTextChanged.connect(self._refresh_summary)
        layout.addWidget(_field("生成范围", self.period))

        dates_row = QHBoxLayout()
        dates_row.setSpacing(12)
        today = date.today().strftime("%Y%m%d")
        self.start = QLineEdit(today)
        self.start.setPlaceholderText("YYYYMMDD")
        self.start.textChanged.connect(self._refresh_summary)
        self.start_wrap = _field("目标日期", self.start)
        self.end = QLineEdit(today)
        self.end.setPlaceholderText("YYYYMMDD")
        self.end.textChanged.connect(self._refresh_summary)
        self.end_wrap = _field("结束日期", self.end)
        self.end_wrap.hide()
        dates_row.addWidget(self.start_wrap, 1)
        dates_row.addWidget(self.end_wrap, 1)
        layout.addLayout(dates_row)

        options = QHBoxLayout()
        options.setSpacing(12)
        self.layout_choice = QComboBox()
        self.layout_choice.addItem("随机版式", "随机")
        for letter, label in LAYOUT_LABELS.items():
            self.layout_choice.addItem(f"{letter} · {label}", letter)
        self.layout_choice.currentIndexChanged.connect(self._refresh_summary)
        self.seed = QLineEdit()
        self.seed.setPlaceholderText("留空则随机")
        options.addWidget(_field("页面版式", self.layout_choice), 3)
        options.addWidget(_field("随机种子（可选）", self.seed), 2)
        layout.addLayout(options)

        quote_panel = QFrame()
        quote_panel.setObjectName("quotePanel")
        quote_layout = QVBoxLayout(quote_panel)
        quote_layout.setContentsMargins(14, 12, 14, 12)
        quote_layout.setSpacing(8)
        quote_header = QHBoxLayout()
        self.corpus_label = _label(self._builtin_label(), "quoteTitle")
        quote_header.addWidget(self.corpus_label)
        quote_header.addStretch(1)
        quote_layout.addLayout(quote_header)
        quote_buttons = QHBoxLayout()
        self.import_button = QPushButton("导入语录")
        self.import_button.clicked.connect(self._import_quotes)
        self.reset_button = QPushButton("恢复内置")
        self.reset_button.setObjectName("quietButton")
        self.reset_button.setEnabled(False)
        self.reset_button.clicked.connect(self._reset_quotes)
        quote_buttons.addWidget(self.import_button)
        quote_buttons.addWidget(self.reset_button)
        quote_buttons.addStretch(1)
        quote_layout.addLayout(quote_buttons)
        layout.addWidget(quote_panel)

        output = QHBoxLayout()
        output.setSpacing(9)
        output.addWidget(_label("保存到", "fieldLabel"))
        self.output_path = QLineEdit(str(self.output_root))
        self.output_path.setReadOnly(True)
        self.output_path.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        output.addWidget(self.output_path, 1)
        self.browse_button = QPushButton("更改")
        self.browse_button.clicked.connect(self._choose_folder)
        output.addWidget(self.browse_button)
        layout.addSpacing(2)
        layout.addLayout(output)
        return card

    def _summary_card(self) -> QWidget:
        card = _card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(18, 17, 18, 18)
        layout.setSpacing(11)
        layout.addWidget(_label("本次日历", "sectionTitle"))
        layout.addWidget(_label("生成前可随时调整设置。", "sectionHint"))

        summary = QFrame()
        summary.setStyleSheet("background:#f7f8fc; border:1px solid #eceef4; border-radius:11px;")
        summary_layout = QVBoxLayout(summary)
        summary_layout.setContentsMargins(14, 13, 14, 13)
        summary_layout.setSpacing(12)
        self.summary_period = _label("单日", "statValue")
        self.summary_period.setWordWrap(True)
        summary_layout.addWidget(self.summary_period)
        self.summary_pages = _label("1 页", "muted")
        summary_layout.addWidget(self.summary_pages)
        self.summary_layout = _label("随机版式", "muted")
        summary_layout.addWidget(self.summary_layout)
        self.summary_quotes = _label(f"可用语录：{len(self.quotes)} 条", "muted")
        summary_layout.addWidget(self.summary_quotes)
        layout.addWidget(summary)

        layout.addWidget(_label("说明", "fieldLabel"))
        tip = _label("每个批次单独保存。\n取消生成不会留下未完成批次。\n生成后点击“预览日历”打开网页。")
        tip.setObjectName("muted")
        tip.setWordWrap(True)
        layout.addWidget(tip)
        layout.addStretch(1)

        self.progress = QProgressBar()
        self.progress.setRange(0, 100)
        self.progress.setValue(0)
        self.progress.setTextVisible(False)
        layout.addWidget(self.progress)
        self.status = _label("准备就绪 · 离线可用", "status")
        self.status.setWordWrap(True)
        layout.addWidget(self.status)

        actions = QHBoxLayout()
        actions.setSpacing(8)
        self.generate_button = QPushButton("生成日历")
        self.generate_button.setObjectName("primaryButton")
        self.generate_button.clicked.connect(self._start)
        self.cancel_button = QPushButton("取消")
        self.cancel_button.setEnabled(False)
        self.cancel_button.clicked.connect(self._cancel)
        self.preview_button = QPushButton("预览日历")
        self.preview_button.setEnabled(False)
        self.preview_button.clicked.connect(self._open_latest_preview)
        actions.addWidget(self.generate_button, 1)
        actions.addWidget(self.preview_button)
        actions.addWidget(self.cancel_button)
        layout.addLayout(actions)

        self.replay_button = QPushButton("从批次清单恢复…")
        self.replay_button.clicked.connect(self._choose_replay)
        layout.addWidget(self.replay_button)
        return card

    def _builtin_label(self) -> str:
        return f"一言语料 · {len(self.quotes)} 条"

    def _update_fields(self, period: str) -> None:
        labels = {
            "单日": ("目标日期", ""),
            "日期范围": ("开始日期", "结束日期"),
            "一周": ("该周任意一天", ""),
            "月份": ("目标月份 YYYYMM", ""),
            "年份": ("目标年份 YYYY", ""),
        }
        first, second = labels[period]
        self.start_wrap.findChild(QLabel, "fieldLabel").setText(first)
        self.end_wrap.setVisible(bool(second))
        self.end_wrap.findChild(QLabel, "fieldLabel").setText(second or "结束日期")

    @staticmethod
    def _date(value: str) -> date:
        if len(value) != 8 or not value.isdigit():
            raise ValueError("日期请使用 YYYYMMDD 格式，例如 20270101。")
        return date(int(value[:4]), int(value[4:6]), int(value[6:8]))

    def _selection(self) -> tuple[list[date], str, str]:
        selected = self.period.currentText()
        if selected == "单日":
            day = self._date(self.start.text())
            return [day], f"date_{day:%Y%m%d}", day.isoformat()
        if selected == "日期范围":
            first, last = self._date(self.start.text()), self._date(self.end.text())
            if last < first:
                raise ValueError("结束日期不能早于开始日期。")
            count = (last - first).days + 1
            if count > len(self.quotes):
                raise ValueError(f"本次 {count} 天，但可用的不重复语录只有 {len(self.quotes)} 条。")
            return dates_between(first, last), f"range_{first:%Y%m%d}-{last:%Y%m%d}", f"{first} 至 {last}"
        if selected == "一周":
            day = self._date(self.start.text())
            days = dates_in_iso_week(day)
            year, week, _ = day.isocalendar()
            return days, f"week_{year}-W{week:02d}", f"ISO {year}-W{week:02d}"
        if selected == "月份":
            value = self.start.text().replace("-", "")
            if len(value) != 6 or not value.isdigit():
                raise ValueError("月份请使用 YYYYMM 格式，例如 202701。")
            year, month = int(value[:4]), int(value[4:])
            return dates_in_month(year, month), f"month_{year}{month:02d}", f"{year}-{month:02d}"
        value = self.start.text()
        if len(value) != 4 or not value.isdigit():
            raise ValueError("年份请使用 YYYY 格式，例如 2027。")
        year = int(value)
        return dates_in_year(year), f"year_{year}", str(year)

    def _refresh_summary(self, *_args: object) -> None:
        self.summary_layout.setText(self.layout_choice.currentText())
        self.summary_quotes.setText(f"可用语录：{len(self.quotes)} 条")
        try:
            days, _key, label = self._selection()
        except (ValueError, OSError):
            self.summary_period.setText("检查日期格式")
            self.summary_pages.setText("输入有效日期后显示页数")
            return
        self.summary_period.setText(label)
        self.summary_pages.setText(f"{len(days)} 页")

    def _set_status(self, text: str, *, error: bool = False) -> None:
        self.status.setText(text)
        self.status.setProperty("status", "error" if error else "normal")
        self.status.style().unpolish(self.status)
        self.status.style().polish(self.status)

    def _import_quotes(self) -> None:
        if self.running:
            return
        path, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "导入你有权使用的语录库",
            str(QUOTE_DIRECTORY) if QUOTE_DIRECTORY.is_dir() else "",
            "语录文件 (*.json *.jsonl);;JSON (*.json);;JSON Lines (*.jsonl);;所有文件 (*)",
        )
        if not path:
            return
        try:
            preview = inspect_quotes(Path(path))
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "无法导入语录", str(exc))
            return
        dialog = QuotePreviewDialog(preview, Path(path).name, self)
        if dialog.exec() != QDialog.DialogCode.Accepted:
            return
        self.quotes = preview.quotes
        self.corpus_label.setText(f"{Path(path).name} · {len(preview.quotes)} 条")
        self.reset_button.setEnabled(True)
        self._refresh_summary()

    def _reset_quotes(self) -> None:
        if self.running:
            return
        self.quotes = builtin_quotes()
        self.corpus_label.setText(self._builtin_label())
        self.reset_button.setEnabled(False)
        self._refresh_summary()

    def _choose_folder(self) -> None:
        selected = QFileDialog.getExistingDirectory(self, "选择日历保存位置", str(self.output_root))
        if not selected:
            return
        self.output_root = Path(selected)
        self.output_path.setText(str(self.output_root))
        if not getattr(sys, "frozen", False) and self.smoke_output is None:
            try:
                save_output_directory(self.output_root)
                self._set_status("保存位置已记住；下次启动仍会使用此目录。")
            except (OSError, ValueError) as exc:
                self._set_status(f"本次使用所选目录；无法保存偏好设置：{exc}", error=True)
        else:
            self._set_status("已更改本次保存位置。")

    def _open_output(self) -> None:
        path = self.output_root
        try:
            path.mkdir(parents=True, exist_ok=True)
            if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(path))):
                raise OSError("系统未能打开该文件夹。")
        except OSError as exc:
            QMessageBox.critical(self, "无法打开日历文件夹", str(exc))

    def _open_latest_preview(self) -> None:
        if self.latest_output_dir is None:
            return
        preview = self.latest_output_dir / "index.html"
        if not preview.is_file():
            QMessageBox.warning(self, "找不到日历预览", "上次生成的预览文件已不存在。")
            self.preview_button.setEnabled(False)
            return
        if not QDesktopServices.openUrl(QUrl.fromLocalFile(str(preview))):
            QMessageBox.critical(self, "无法打开日历预览", "系统未能打开网页预览。")

    def _choose_replay(self) -> None:
        if self.running:
            return
        selected, _selected_filter = QFileDialog.getOpenFileName(
            self,
            "选择要恢复的批次清单",
            str(self.output_root) if self.output_root.is_dir() else "",
            "批次清单 CSV (*.csv)",
        )
        if not selected:
            return
        output_dir = unique_output_dir("replay", None, root=self.output_root)
        manifest = Path(selected)
        self._start_job(lambda: prepare_replay(manifest), output_dir, "正在读取批次清单…")

    def _start(self) -> None:
        if self.running:
            return
        try:
            days, period_key, label = self._selection()
            if len(days) > len(self.quotes):
                raise ValueError(f"本次 {len(days)} 天，但可用的不重复语录只有 {len(self.quotes)} 条。")
            seed_text = self.seed.text().strip()
            seed = int(seed_text) if seed_text else None
            layout_data = self.layout_choice.currentData()
            layout = "RANDOM" if layout_data == "随机" else str(layout_data)
            pages = plan_pages(days, self.quotes, layout, seed)
            output_dir = unique_output_dir(period_key, layout, root=self.output_root)
        except (ValueError, OSError) as exc:
            if self.smoke_output is not None:
                self._finish_smoke(exc)
                return
            QMessageBox.warning(self, "检查生成设置", str(exc))
            return
        self._start_job(lambda: (pages, seed), output_dir, f"正在准备 {label} · {len(pages)} 页…")

    def _start_job(self, prepare: PagePreparation, output_dir: Path, status: str) -> None:
        self.cancel_event.clear()
        self.running = True
        self.generate_button.setEnabled(False)
        self.replay_button.setEnabled(False)
        self.import_button.setEnabled(False)
        self.browse_button.setEnabled(False)
        self.cancel_button.setEnabled(True)
        self.progress.setRange(0, 0)
        self._set_status(status)
        worker = threading.Thread(
            target=run_generation_job,
            args=(prepare, output_dir, self.cancel_event, self.events),
            daemon=True,
        )
        worker.start()

    def _poll(self) -> None:
        try:
            while True:
                event = self.events.get_nowait()
                if isinstance(event, GenerationProgress):
                    if self.cancel_event.is_set():
                        continue
                    self.progress.setRange(0, max(1, event.total))
                    self.progress.setValue(event.completed)
                    if event.completed:
                        self._set_status(f"正在生成页面 · {event.completed}/{event.total}")
                    else:
                        self._set_status(f"正在预检 {event.total} 个页面…")
                    continue

                self.running = False
                self.generate_button.setEnabled(True)
                self.replay_button.setEnabled(True)
                self.import_button.setEnabled(True)
                self.browse_button.setEnabled(True)
                self.cancel_button.setEnabled(False)
                if self.closing:
                    self.close()
                    return
                if isinstance(event, GenerationCompleted):
                    self.progress.setRange(0, 100)
                    self.progress.setValue(100)
                    self.latest_output_dir = event.output_dir
                    self.preview_button.setEnabled(True)
                    self._set_status(f"已生成 {event.output_dir} · 点击“预览日历”查看")
                    if self.smoke_output is not None:
                        self._finish_smoke()
                        return
                elif isinstance(event, GenerationCancelled):
                    self.progress.setRange(0, 100)
                    self.progress.setValue(0)
                    self._set_status("已取消 · 未发布不完整批次")
                elif isinstance(event, GenerationFailed):
                    self.progress.setRange(0, 100)
                    self.progress.setValue(0)
                    self._set_status("生成未完成 · 原有文件未被覆盖", error=True)
                    if self.smoke_output is not None:
                        self._finish_smoke(event.error)
                        return
                    QMessageBox.critical(self, "生成失败", str(event.error))
        except queue.Empty:
            pass

    def _smoke(self) -> None:
        self.period.setCurrentText("年份" if self.smoke_year else "单日")
        self.start.setText("2028" if self.smoke_year else "20270101")
        self.layout_choice.setCurrentIndex(0 if self.smoke_year else 1)
        self.seed.setText("31415")
        self.output_root = self.smoke_output or self.output_root
        self._start()

    def _finish_smoke(self, error: object = None) -> None:
        if error is not None:
            self.exit_code = 1
            print(error, file=sys.stderr, flush=True)
        QApplication.instance().exit(self.exit_code)

    def _cancel(self) -> None:
        self.cancel_event.set()
        self.cancel_button.setEnabled(False)
        self._set_status("正在取消 · 等待当前页面清理…")

    def closeEvent(self, event: object) -> None:
        if self.running:
            self.closing = True
            self._cancel()
            event.ignore()
            return
        event.accept()


def run(*, smoke_output: Path | None = None, smoke_year: bool = False) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("每日文学日历")
    app.setOrganizationName("CalendarWorkflow")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    app.setFont(QFont("Segoe UI", 10))
    window: CalendarWindow | None = None
    try:
        window = CalendarWindow(smoke_output=smoke_output, smoke_year=smoke_year)
        window.show()
    except (OSError, ValueError, RuntimeError) as exc:
        if smoke_output is not None:
            print(exc, file=sys.stderr, flush=True)
            return 1
        QMessageBox.critical(None, "启动失败", str(exc))
        return 1
    result = app.exec()
    return window.exit_code if smoke_output is not None else result
