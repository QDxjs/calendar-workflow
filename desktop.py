"""Modern Qt desktop interface for the offline literature calendar."""

from __future__ import annotations

from datetime import date
from pathlib import Path
import queue
import re
import sys
import tempfile
import threading

from PySide6.QtCore import QSignalBlocker, QTimer, Qt, QUrl
from PySide6.QtGui import QDesktopServices, QFont, QIcon
from PySide6.QtWidgets import (
    QApplication,
    QBoxLayout,
    QComboBox,
    QDialog,
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
    CalendarPage,
    GenerationCancelled,
    GenerationCompleted,
    GenerationEvent,
    GenerationFailed,
    GenerationProgress,
    GenerationPlan,
    PreviewCompleted,
)
from calendar_preview import run_preview_job
from content_sources import ManualQuoteError, plan_manual_page, validate_manual_source
from manual_quote_panel import ManualQuotePanel
from generate import LAYOUT_LABELS, RESOURCE_ROOT, prepare_replay
from generation_service import PagePreparation, run_generation_job
from launcher import OUTPUT_ROOT, plan_pages, unique_output_dir
from periods import dates_between, dates_in_iso_week, dates_in_month, dates_in_year
from preferences import load_output_directory, preferences_warning, save_output_directory
from history_dialog import HistoryDialog
from preview_dialogs import FirstPageDialog, LayoutChooserDialog
from quote_library import QUOTE_DIRECTORY, builtin_quotes, inspect_quotes
from quote_import_dialog import QuotePreviewDialog


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
QLineEdit:disabled, QComboBox:disabled { color: #82889a; background: #f4f5f8; }
QLineEdit[invalid="true"], QPlainTextEdit[invalid="true"] { border-color: #bd3a4a; }
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
QPushButton#primaryButton:disabled { color: #a9adba; background: #f3f4f7; border-color: #eceef2; }
QPushButton#quietButton { color: #666b7b; background: transparent; border-color: transparent; }
QPushButton#quietButton:hover { color: #5440bd; background: #f4f1ff; }
QToolButton { background: white; border: 1px solid #dfe3ec; border-radius: 8px; padding: 6px; }
QToolButton:hover, QToolButton:checked { background: #f4f1ff; border-color: #8069eb; }
QToolButton:disabled { color: #a9adba; background: #f3f4f7; }
QFrame#quotePanel { background: #f7f6ff; border: 1px solid #ebe7ff; border-radius: 10px; }
QLabel#quoteTitle { color: #393250; font-weight: 700; }
QLabel#muted { color: #82889a; }
QLabel#statValue { color: #24283a; font-size: 18px; font-weight: 700; }
QLabel#statLabel { color: #898fa0; font-size: 11px; }
QLabel#status { color: #777e90; font-size: 12px; }
QLabel#status[status="error"] { color: #bd3a4a; }
QLabel#fieldError { color: #bd3a4a; font-size: 12px; }
QProgressBar { background: #eceef4; border: none; border-radius: 4px; height: 8px; text-align: center; }
QProgressBar::chunk { background: #785eea; border-radius: 4px; }
QScrollBar:vertical { background: transparent; width: 9px; margin: 2px; }
QScrollBar::handle:vertical { background: #d5d9e4; border-radius: 4px; min-height: 30px; }
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical { height: 0; }
QDialog { background: #f8f9fc; }
QTableView, QPlainTextEdit { background: white; border: 1px solid #dfe3ec; border-radius: 6px; selection-background-color: #eeeaff; selection-color: #24283a; }
QHeaderView::section { background: #f0eef9; border: none; padding: 5px; }
QTabWidget::pane { border: 1px solid #dfe3ec; }
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


def _error_label() -> QLabel:
    label = _label("", "fieldError")
    label.setWordWrap(True)
    label.setTextFormat(Qt.TextFormat.PlainText)
    label.hide()
    return label


class SettingsError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


def check_output_directory(directory: Path) -> None:
    """Check actual creation and writing; the probe is deleted on close."""
    directory.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryFile(dir=directory, prefix=".calendar-write-") as probe:
        probe.write(b"\0")
        probe.flush()


def output_error_message(error: OSError) -> str:
    if isinstance(error, PermissionError):
        return "保存位置没有写入权限。请点击“更改”选择可写入的文件夹。"
    if isinstance(error, (FileExistsError, NotADirectoryError)):
        return "保存路径被文件占用。请点击“更改”选择一个文件夹。"
    return f"保存位置暂时无法写入，请检查磁盘或更改文件夹。详情：{error}"


def generation_error_message(error: Exception) -> str:
    cause: BaseException | None = error
    while cause is not None:
        if isinstance(cause, PermissionError):
            return f"无法读取所需文件或写入保存位置。请检查文件权限，或更改保存位置后重试。\n\n详情：{error}"
        cause = cause.__cause__
    return f"{error}\n\n请根据提示修正后重试；原有批次不会被覆盖。"


class CalendarWindow(QMainWindow):
    def __init__(self, *, smoke_output: Path | None = None, smoke_year: bool = False,
                 smoke_manual: bool = False, smoke_quote: str | None = None) -> None:
        super().__init__()
        self.smoke_output = smoke_output
        self.smoke_year = smoke_year
        self.smoke_manual = smoke_manual
        self.smoke_quote = smoke_quote
        self.exit_code = 0
        self.running = False
        self.closing = False
        self.latest_output_dir: Path | None = None
        self.events: queue.Queue[GenerationEvent] = queue.Queue()
        self.cancel_event = threading.Event()
        self._task_kind = "generation"
        self._prepared_plan: GenerationPlan | None = None
        self._plan_key: tuple | None = None
        self._sample_plan: GenerationPlan | None = None
        self._job_plan: GenerationPlan | None = None
        self._sample_image: bytes | None = None
        self._layout_images: tuple[tuple[str, bytes], ...] | None = None
        self._layout_dialog: LayoutChooserDialog | None = None
        self._current_period = "单日"
        self._period_values: dict[str, tuple[str, str]] = {}
        self._custom_quotes = False
        self._manual_fit_failure: tuple | None = None
        self._settings_valid = False
        self._output_error = ""
        packaged = getattr(sys, "frozen", False)
        self.output_root = load_output_directory(OUTPUT_ROOT)
        self._preferences_warning = preferences_warning() if smoke_output is None else ""
        if smoke_output is not None:
            self.output_root = smoke_output
        if packaged and smoke_output is None:
            try:
                check_output_directory(self.output_root)
            except OSError as exc:
                self._output_error = output_error_message(exc)
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
        for text, name in (("每日文学日历", "pageTitle"), ("挑选日期与版式，把喜欢的文字变成可以收藏的日历。", "pageSubtitle")):
            label = _label(text, name)
            label.setWordWrap(True)
            title_block.addWidget(label)
        header.addLayout(title_block, 1)
        self.history_button = QPushButton("历史批次")
        self.history_button.clicked.connect(self._show_history)
        header.addWidget(self.history_button)
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
        self.date_error = _error_label()
        layout.addWidget(self.date_error)

        options = QHBoxLayout()
        options.setSpacing(12)
        self.layout_choice = QComboBox()
        self.layout_choice.addItem("随机版式", "随机")
        for letter, label in LAYOUT_LABELS.items():
            self.layout_choice.addItem(f"{letter} · {label}", letter)
        self.layout_choice.currentIndexChanged.connect(self._refresh_summary)
        self.seed = QLineEdit()
        self.seed.setPlaceholderText("留空则随机")
        self.seed.textChanged.connect(self._refresh_summary)
        options.addWidget(_field("页面版式", self.layout_choice), 3)
        options.addWidget(_field("随机种子（可选）", self.seed), 2)
        layout.addLayout(options)
        self.layouts_button = QPushButton("查看版式示意")
        self.layouts_button.setToolTip("比较 A–I 九种版式的统一示意图，点击即可选择。")
        self.layouts_button.clicked.connect(self._show_layouts)
        layout.addWidget(self.layouts_button)
        self.seed_error = _error_label()
        layout.addWidget(self.seed_error)

        self.content_panel = ManualQuotePanel(self._builtin_label())
        self.corpus_label = self.content_panel.corpus_label
        self.import_button = self.content_panel.import_button
        self.import_button.clicked.connect(self._import_quotes)
        self.reset_button = self.content_panel.reset_button
        self.reset_button.clicked.connect(self._reset_quotes)
        self.content_panel.changed.connect(self._refresh_summary)
        layout.addWidget(self.content_panel)

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
        self.output_error = _error_label()
        layout.addWidget(self.output_error)
        self.default_folder_button = QPushButton("恢复默认目录")
        self.default_folder_button.setObjectName("quietButton")
        self.default_folder_button.clicked.connect(self._reset_output_directory)
        layout.addWidget(self.default_folder_button)
        self.settings_warning = _error_label()
        self._show_error(self.settings_warning, self._preferences_warning)
        layout.addWidget(self.settings_warning)
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
        self.summary_layout.setWordWrap(True)
        summary_layout.addWidget(self.summary_layout)
        self.summary_quotes = _label(f"可用语录：{len(self.quotes)} 条", "muted")
        self.summary_quotes.setWordWrap(True)
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

        self.sample_button = QPushButton("查看首张效果")
        self.sample_button.clicked.connect(self._start_sample)
        layout.addWidget(self.sample_button)
        self.sample_status = _label("生成前可查看真实首张；预览不会保存正式批次。", "sectionHint")
        self.sample_status.setWordWrap(True)
        layout.addWidget(self.sample_status)

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
        previous = self._current_period
        old_start, old_end = self.start.text(), self.end.text()
        self._period_values[previous] = (old_start, old_end)
        if period in self._period_values:
            first_value, last_value = self._period_values[period]
        else:
            try:
                if previous == "月份":
                    year, month = self._month(old_start)
                    anchor = date(year, month, 1)
                elif previous == "年份":
                    anchor = date(self._year(old_start), 1, 1)
                else:
                    anchor = self._date(old_start)
                first_value = (
                    f"{anchor.year:04d}" if period == "年份"
                    else f"{anchor.year:04d}{anchor.month:02d}" if period == "月份"
                    else f"{anchor.year:04d}{anchor.month:02d}{anchor.day:02d}"
                )
                last_value = first_value
            except SettingsError:
                # Keep invalid input visible rather than guessing a replacement.
                first_value, last_value = old_start, old_end
        self._current_period = period
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
        self.start.setPlaceholderText("YYYY" if period == "年份" else "YYYYMM" if period == "月份" else "YYYYMMDD")
        self.start.setToolTip("首次切换到更具体的范围时，使用所选月份或年份的第一天；已填值会分别保留。")
        with QSignalBlocker(self.start), QSignalBlocker(self.end):
            self.start.setText(first_value)
            self.end.setText(last_value)
        self.content_panel.set_single_day(period == "单日")

    @staticmethod
    def _date(value: str, field: str = "start") -> date:
        value = value.strip()
        caption = "结束日期" if field == "end" else "日期"
        if not re.fullmatch(r"\d{8}", value):
            raise SettingsError(field, f"{caption}请使用 YYYYMMDD 格式，例如 20270101。")
        try:
            return date(int(value[:4]), int(value[4:6]), int(value[6:8]))
        except ValueError as exc:
            raise SettingsError(field, f"{caption}不存在，请检查年、月、日及闰年。") from exc

    @staticmethod
    def _month(value: str) -> tuple[int, int]:
        value = value.strip()
        if not re.fullmatch(r"\d{6}|\d{4}-\d{2}", value):
            raise SettingsError("start", "月份请使用 YYYYMM 或 YYYY-MM 格式，例如 202701。")
        value = value.replace("-", "")
        year, month = int(value[:4]), int(value[4:])
        try:
            date(year, month, 1)
        except ValueError as exc:
            raise SettingsError("start", "月份不存在，请输入有效年份和 01–12 月。") from exc
        return year, month

    @staticmethod
    def _year(value: str) -> int:
        value = value.strip()
        if not re.fullmatch(r"\d{4}", value) or not 1 <= int(value) <= 9999:
            raise SettingsError("start", "年份请使用 0001–9999 范围内的四位数字，例如 2027。")
        return int(value)

    def _seed_value(self) -> int | None:
        value = self.seed.text().strip()
        if not value:
            return None
        try:
            return int(value)
        except ValueError as exc:
            raise SettingsError("seed", "随机种子请填写整数，例如 31415；也可以留空。") from exc

    def _check_capacity(self, count: int) -> None:
        if self.content_panel.is_manual:
            return
        if count > len(self.quotes):
            raise SettingsError("quotes", f"本次需要 {count} 条不重复语录，当前只有 {len(self.quotes)} 条。请缩短范围或导入更多语录。")

    def _selection(self) -> tuple[list[date], str, str]:
        selected = self.period.currentText()
        if selected == "单日":
            day = self._date(self.start.text())
            return [day], f"date_{day:%Y%m%d}", day.isoformat()
        if selected == "日期范围":
            first, last = self._date(self.start.text()), self._date(self.end.text(), "end")
            if last < first:
                raise SettingsError("end", "结束日期不能早于开始日期，请调整日期范围。")
            count = (last - first).days + 1
            self._check_capacity(count)
            return dates_between(first, last), f"range_{first:%Y%m%d}-{last:%Y%m%d}", f"{first} 至 {last}"
        if selected == "一周":
            day = self._date(self.start.text())
            try:
                days = dates_in_iso_week(day)
            except ValueError as exc:
                raise SettingsError("start", "这一周超出支持的年份范围，请选择其他日期。") from exc
            year, week, _ = day.isocalendar()
            return days, f"week_{year}-W{week:02d}", f"ISO {year}-W{week:02d}"
        if selected == "月份":
            year, month = self._month(self.start.text())
            return dates_in_month(year, month), f"month_{year}{month:02d}", f"{year}-{month:02d}"
        year = self._year(self.start.text())
        return dates_in_year(year), f"year_{year}", str(year)

    @staticmethod
    def _show_error(label: QLabel, message: str) -> None:
        label.setText(message)
        label.setVisible(bool(message))

    @staticmethod
    def _mark_invalid(widget: QLineEdit, invalid: bool) -> None:
        if widget.property("invalid") != invalid:
            widget.setProperty("invalid", invalid)
            widget.style().unpolish(widget)
            widget.style().polish(widget)

    def _sync_controls(self) -> None:
        editable = not self.running
        for widget in (self.period, self.start, self.end, self.layout_choice, self.seed, self.import_button, self.browse_button, self.layouts_button, self.history_button, self.default_folder_button):
            widget.setEnabled(editable)
        self.reset_button.setEnabled(editable and self._custom_quotes)
        self.content_panel.set_state(busy=self.running, custom=self._custom_quotes)
        self.generate_button.setEnabled(editable and self._settings_valid and not self._output_error)
        self.sample_button.setEnabled(editable and self._settings_valid)
        self.replay_button.setEnabled(editable and not self._output_error)
        self.cancel_button.setEnabled(self.running and not self.cancel_event.is_set())
        self.preview_button.setEnabled(self.latest_output_dir is not None)

    def _refresh_summary(self, *_args: object, update_summary: bool = True) -> None:
        if self.running:
            return
        if update_summary:
            self.summary_layout.setText(self.layout_choice.currentText())
            if self.content_panel.is_manual:
                content = self.content_panel.content()
                attribution = "含出处" if content.source.strip() else "无出处"
                detail = f"{len(content.quote.strip())} 字 · {attribution}"
                if not content.quote.strip():
                    detail = "仅出处" if content.source.strip() else "留白日历"
                self.summary_quotes.setText(f"内容来源：单日手写（{detail}）")
            else:
                self.summary_quotes.setText(f"可用语录：{len(self.quotes)} 条")
        date_error = seed_error = ""
        invalid_field = ""
        try:
            days, _key, label = self._selection()
            self._check_capacity(len(days))
        except SettingsError as exc:
            date_error, invalid_field = str(exc), exc.field
            if update_summary:
                self.summary_period.setText("请检查生成范围" if exc.field == "quotes" else "请检查日期设置")
                self.summary_pages.setText("修正标出的设置后即可生成")
        else:
            if update_summary:
                self.summary_period.setText(label)
                self.summary_pages.setText(f"{len(days)} 页")
        try:
            self._seed_value()
        except SettingsError as exc:
            seed_error = str(exc)
        self._show_error(self.date_error, date_error)
        self._show_error(self.seed_error, seed_error)
        self._show_error(self.output_error, self._output_error)
        self._mark_invalid(self.start, invalid_field == "start")
        self._mark_invalid(self.end, invalid_field == "end")
        self._mark_invalid(self.seed, bool(seed_error))
        self._mark_invalid(self.output_path, bool(self._output_error))
        manual_error = None
        if self.content_panel.is_manual:
            try:
                validate_manual_source(self.content_panel.content())
                if not date_error and not seed_error and self._manual_fit_failure is not None:
                    failed_key, failed_error = self._manual_fit_failure
                    if failed_key == self._content_key():
                        raise failed_error
                    self._manual_fit_failure = None
            except ManualQuoteError as exc:
                manual_error = exc
        self.content_panel.show_error(manual_error.field if manual_error else "", str(manual_error or ""))
        self._settings_valid = not date_error and not seed_error and manual_error is None
        self._discard_changed_plan()
        self._sync_controls()
        if update_summary:
            if self._output_error:
                self._set_status("保存位置不可用 · 请点击“更改”选择其他文件夹", error=True)
            elif not self._settings_valid:
                self._set_status("请修正标出的设置后再生成。", error=True)
            else:
                self._set_status("准备就绪 · 离线可用")

    def _check_output(self) -> bool:
        try:
            check_output_directory(self.output_root)
        except OSError as exc:
            self._output_error = output_error_message(exc)
            self._set_status("保存位置不可用 · 请更改文件夹后重试", error=True)
        else:
            self._output_error = ""
        self._refresh_summary(update_summary=False)
        return not self._output_error

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
            preview = inspect_quotes(Path(path), allow_empty=True)
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "无法导入语录", str(exc))
            return
        dialog = QuotePreviewDialog(preview, Path(path).name, self)
        try:
            accepted = dialog.exec() == QDialog.DialogCode.Accepted
        finally:
            dialog.deleteLater()
        if not accepted or not preview.quotes:
            return
        self.quotes = preview.quotes
        self.corpus_label.setText(f"{Path(path).name} · {len(preview.quotes)} 条")
        self._custom_quotes = True
        self._refresh_summary()

    def _reset_quotes(self) -> None:
        if self.running:
            return
        try:
            quotes = builtin_quotes()
        except (OSError, ValueError) as exc:
            QMessageBox.critical(self, "无法恢复内置语料", str(exc))
            return
        self.quotes = quotes
        self.corpus_label.setText(self._builtin_label())
        self._custom_quotes = False
        self._refresh_summary()

    def _choose_folder(self) -> None:
        if self.running:
            return
        selected = QFileDialog.getExistingDirectory(self, "选择日历保存位置", str(self.output_root))
        if not selected:
            return
        self._set_output_directory(Path(selected))

    def _reset_output_directory(self) -> None:
        if not self.running:
            self._set_output_directory(Path(OUTPUT_ROOT), reset=True)

    def _set_output_directory(self, directory: Path, *, reset: bool = False) -> None:
        self.output_root = directory
        self.output_path.setText(str(self.output_root))
        self.output_path.setToolTip(str(self.output_root))
        writable = self._check_output()
        if not writable and not reset:
            return
        if self.smoke_output is None:
            try:
                save_output_directory(None if reset else self.output_root)
                self._show_error(self.settings_warning, "")
                if writable:
                    self._set_status("已恢复默认目录；下次启动使用默认位置。" if reset else "保存位置已记住；下次启动仍会使用此目录。")
            except (OSError, ValueError) as exc:
                self._set_status(f"本次使用所选目录；无法保存偏好设置：{exc}", error=True)
        else:
            self._set_status("已更改本次保存位置。")

    def _show_history(self) -> None:
        if self.running:
            return
        dialog = HistoryDialog(self.output_root, self)
        try:
            if dialog.exec() == QDialog.DialogCode.Accepted and dialog.replay_path is not None:
                self._replay_manifest(dialog.replay_path)
        finally:
            dialog.deleteLater()

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
            self.latest_output_dir = None
            self._sync_controls()
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
        self._replay_manifest(Path(selected))

    def _replay_manifest(self, manifest: Path) -> None:
        if self.running:
            return
        if not self._check_output():
            return
        output_dir = unique_output_dir("replay", None, root=self.output_root)
        self._job_plan = None
        self.summary_period.setText(f"从清单恢复 · {manifest.name}")
        self.summary_pages.setText("正在读取清单…")
        self.summary_layout.setText("沿用清单中的实际版式")
        self.summary_quotes.setText("使用清单中的语录与出处")
        self._start_job(lambda: prepare_replay(manifest), output_dir, "正在读取批次清单…")

    def _content_key(self) -> tuple:
        days, _period_key, _label_text = self._selection()
        if self.content_panel.is_manual:
            content = self.content_panel.content()
            return ("manual", days[0], self.layout_choice.currentData(), self._seed_value(),
                    content.quote.strip(), content.source.strip())
        return (
            "corpus", self.period.currentText(), tuple(days), self.layout_choice.currentData(), self._seed_value(),
            tuple((item["quote"], item["source"], item["quote_id"]) for item in self.quotes),
        )

    def _discard_changed_plan(self) -> None:
        if self._prepared_plan is None:
            return
        try:
            unchanged = self._settings_valid and self._content_key() == self._plan_key
        except SettingsError:
            unchanged = False
        if not unchanged:
            self._clear_plan()
            self.sample_status.setText("设置或语料已更改，请重新查看首张效果。")

    def _clear_plan(self) -> None:
        self._prepared_plan = None
        self._plan_key = None
        self._sample_plan = None
        self._sample_image = None

    def _plan_for_settings(self) -> GenerationPlan:
        key = self._content_key()
        if self._prepared_plan is None or key != self._plan_key:
            days, _period_key, _label_text = self._selection()
            self._check_capacity(len(days))
            seed = self._seed_value()
            choice = self.layout_choice.currentData()
            layout = "RANDOM" if choice == "随机" else str(choice)
            if self.content_panel.is_manual:
                try:
                    plan = plan_manual_page(days[0], self.content_panel.content(), layout, seed)
                except ManualQuoteError as exc:
                    self._manual_fit_failure = (key, exc)
                    self._refresh_summary()
                    raise
            else:
                plan = GenerationPlan(tuple(plan_pages(days, self.quotes, layout, seed)), seed)
            self._prepared_plan = plan
            self._plan_key = key
            self._sample_image = None
        return self._prepared_plan

    def _show_layouts(self) -> None:
        if self.running:
            return
        dialog = LayoutChooserDialog(str(self.layout_choice.currentData()), self)
        self._layout_dialog = dialog
        dialog.accepted.connect(lambda: self.layout_choice.setCurrentIndex(
            self.layout_choice.findData(dialog.selected_layout),
        ))
        dialog.finished.connect(lambda _result: self._finish_layout_dialog(dialog))
        if self._layout_images is not None:
            dialog.set_images(self._layout_images)
        else:
            try:
                self._start_preview_job("layouts", self._layout_example_pages())
            except (OSError, ValueError) as exc:
                dialog.show_error(str(exc))
        dialog.open()

    @staticmethod
    def _layout_example_pages() -> tuple[CalendarPage, ...]:
        # A genuine, unmodified record from the bundled corpus, independent of imports.
        quote = builtin_quotes()[0]
        return tuple(CalendarPage(date(2027, 1, 1), letter, letter,
                                  quote["quote"], quote["source"], quote["quote_id"])
                     for letter in LAYOUT_LABELS)

    def _finish_layout_dialog(self, dialog: LayoutChooserDialog) -> None:
        if self._layout_dialog is dialog:
            self._layout_dialog = None
        if self.running and self._task_kind == "layouts":
            self._cancel()
        dialog.deleteLater()

    def _start_sample(self) -> None:
        if self.running:
            return
        self._refresh_summary()
        if not self._settings_valid:
            return
        try:
            plan = self._plan_for_settings()
            if self._sample_image is not None:
                self._show_sample(plan)
                return
            self._sample_plan = plan
            self._start_preview_job("sample", plan.pages[:1])
        except ManualQuoteError as exc:
            self._set_status(str(exc), error=True)
            if self.smoke_output is not None:
                self._finish_smoke(exc)
        except (OSError, ValueError) as exc:
            QMessageBox.warning(self, "无法预览首张", str(exc))

    def _show_sample(self, plan: GenerationPlan) -> None:
        dialog = FirstPageDialog(plan.pages[0], self._sample_image, len(plan.pages), self)
        try:
            dialog.exec()
        finally:
            dialog.deleteLater()

    def _start_preview_job(self, kind: str, pages: tuple[CalendarPage, ...]) -> None:
        self._task_kind = kind
        self.cancel_event.clear()
        self.running = True
        self._sync_controls()
        self.progress.setRange(0, len(pages))
        self.progress.setValue(0)
        self._set_status("正在准备版式示意…" if kind == "layouts" else "正在渲染首张效果…")
        threading.Thread(target=run_preview_job, args=(pages, self.cancel_event, self.events), daemon=True).start()

    def _start(self) -> None:
        if self.running:
            return
        self._refresh_summary()
        if not self._settings_valid:
            self._set_status("请先修正标出的设置，再生成日历。", error=True)
            if self.smoke_output is not None:
                self._finish_smoke(ValueError(self.date_error.text() or self.seed_error.text()))
            return
        if not self._check_output():
            if self.smoke_output is not None:
                self._finish_smoke(OSError(self._output_error))
            return
        try:
            days, period_key, label = self._selection()
            self._check_capacity(len(days))
            layout_data = self.layout_choice.currentData()
            layout = "RANDOM" if layout_data == "随机" else str(layout_data)
            plan = self._plan_for_settings()
            output_dir = unique_output_dir(period_key, layout, root=self.output_root)
        except ManualQuoteError as exc:
            self._set_status(str(exc), error=True)
            if self.smoke_output is not None:
                self._finish_smoke(exc)
            return
        except (ValueError, OSError) as exc:
            if self.smoke_output is not None:
                self._finish_smoke(exc)
                return
            QMessageBox.warning(self, "检查生成设置", str(exc))
            return
        self._job_plan = plan
        self._start_job(lambda: (list(plan.pages), plan.seed), output_dir, f"正在准备 {label} · {len(plan.pages)} 页…")

    def _start_job(self, prepare: PagePreparation, output_dir: Path, status: str) -> None:
        self._task_kind = "generation"
        self.cancel_event.clear()
        self.running = True
        self._sync_controls()
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
                    if self._task_kind != "generation":
                        text = (f"正在渲染版式示意 · {event.completed}/{event.total}"
                                if self._task_kind == "layouts" else "正在渲染首张效果…")
                        self._set_status(text)
                        if self._task_kind == "layouts" and self._layout_dialog is not None:
                            self._layout_dialog.status.setText(text)
                        continue
                    self.summary_pages.setText(f"{event.total} 页")
                    if event.completed:
                        self._set_status(f"正在生成页面 · {event.completed}/{event.total}")
                    else:
                        self._set_status(f"正在预检 {event.total} 个页面…")
                    continue

                self.running = False
                self._refresh_summary(update_summary=self._task_kind == "layouts")
                if self.closing:
                    self.close()
                    return
                if isinstance(event, PreviewCompleted):
                    if self.cancel_event.is_set():
                        event = GenerationCancelled()
                    else:
                        self.progress.setRange(0, 100)
                        self.progress.setValue(100)
                        try:
                            if self._task_kind == "layouts":
                                self._layout_images = event.images
                                if self._layout_dialog is not None:
                                    self._layout_dialog.set_images(event.images)
                                self._set_status("版式示意已就绪 · 选择后可查看真实首张")
                                if self.smoke_output is not None:
                                    self._start_sample()
                            elif self._prepared_plan is self._sample_plan:
                                self._sample_image = event.images[0][1]
                                self.sample_status.setText("首张已就绪 · 设置不变时与正式生成一致。")
                                self._set_status("首张效果已就绪 · 关闭预览后可生成整批")
                                if self.smoke_output is not None:
                                    self._start()
                                else:
                                    self._show_sample(self._prepared_plan)
                        except ValueError as exc:
                            self._sample_image = None
                            self._layout_images = None
                            QMessageBox.warning(self, "无法显示预览", str(exc))
                        continue
                if isinstance(event, GenerationCompleted):
                    self.progress.setRange(0, 100)
                    self.progress.setValue(100)
                    self.latest_output_dir = event.output_dir
                    self._sync_controls()
                    self.preview_button.setToolTip(f"查看上次成功批次：{event.output_dir}")
                    self._set_status(f"已生成 {event.output_dir} · 点击“预览日历”查看")
                    if self.smoke_output is not None:
                        page = self._job_plan.pages[0]
                        image_path = event.output_dir / "png" / f"{page.target_date.isoformat()}_layout-{page.layout}.png"
                        if image_path.read_bytes() != self._sample_image:
                            self._finish_smoke(ValueError("首张预览与正式生成的 PNG 不一致。"))
                            return
                        self._finish_smoke()
                        return
                    if self._job_plan is not None and self._prepared_plan is self._job_plan:
                        self._clear_plan()
                        self.sample_status.setText("本批已保存 · 下一批将重新抽选；固定种子仍可复现。")
                    self._job_plan = None
                elif isinstance(event, GenerationCancelled):
                    self.progress.setRange(0, 100)
                    self.progress.setValue(0)
                    self._set_status("已取消 · 未发布不完整批次" if self._task_kind == "generation" else "预览已取消 · 临时文件已清理，可重试")
                    if self._task_kind == "layouts" and self._layout_dialog is not None:
                        self._layout_dialog.show_error("已取消")
                    if self.smoke_output is not None:
                        self._finish_smoke(ValueError("桌面自检意外取消。"))
                        return
                elif isinstance(event, GenerationFailed):
                    self.progress.setRange(0, 100)
                    self.progress.setValue(0)
                    is_preview = self._task_kind != "generation"
                    self._set_status("预览未完成 · 请根据提示重试" if is_preview else "生成未完成 · 原有文件未被覆盖", error=True)
                    if self.smoke_output is not None:
                        self._finish_smoke(event.error)
                        return
                    if self._task_kind == "layouts" and self._layout_dialog is not None:
                        self._layout_dialog.show_error(str(event.error))
                    else:
                        QMessageBox.critical(self, "预览失败" if is_preview else "生成失败", generation_error_message(event.error))
        except queue.Empty:
            pass

    def _smoke(self) -> None:
        self.period.setCurrentText("年份" if self.smoke_year else "单日")
        self.start.setText("2028" if self.smoke_year else "20270101")
        self.layout_choice.setCurrentIndex(0 if self.smoke_year else 1)
        self.seed.setText("31415")
        if self.smoke_manual:
            quote = self.smoke_quote if self.smoke_quote is not None else '春风又绿江南岸\n明月 <日常> & "文字"'
            self.content_panel.quote_edit.setPlainText(quote)
            self.content_panel.selector.setCurrentIndex(1)
            self.layout_choice.setCurrentIndex(0)
        self.output_root = self.smoke_output or self.output_root
        self._start_preview_job("layouts", self._layout_example_pages())

    def _finish_smoke(self, error: object = None) -> None:
        if error is not None:
            self.exit_code = 1
            print(error, file=sys.stderr, flush=True)
        QApplication.instance().exit(self.exit_code)

    def _cancel(self) -> None:
        self.cancel_event.set()
        self._sync_controls()
        self._set_status("正在取消 · 等待当前页面清理…")
        if self._task_kind == "layouts" and self._layout_dialog is not None:
            self._layout_dialog.status.setText("正在取消 · 等待当前页面清理…")

    def closeEvent(self, event: object) -> None:
        if self.running:
            self.closing = True
            self._cancel()
            event.ignore()
            return
        event.accept()


def run(*, smoke_output: Path | None = None, smoke_year: bool = False,
        smoke_manual: bool = False, smoke_quote: str | None = None) -> int:
    app = QApplication.instance() or QApplication(sys.argv[:1])
    app.setApplicationName("每日文学日历")
    app.setWindowIcon(QIcon(str(RESOURCE_ROOT / "assets/calendar.ico")))
    app.setOrganizationName("CalendarWorkflow")
    app.setStyle("Fusion")
    app.setStyleSheet(APP_STYLE)
    app.setFont(QFont("Segoe UI", 10))
    window: CalendarWindow | None = None
    try:
        window = CalendarWindow(smoke_output=smoke_output, smoke_year=smoke_year,
                                smoke_manual=smoke_manual, smoke_quote=smoke_quote)
        window.show()
    except (OSError, ValueError, RuntimeError) as exc:
        if smoke_output is not None:
            print(exc, file=sys.stderr, flush=True)
            return 1
        QMessageBox.critical(None, "启动失败", str(exc))
        return 1
    result = app.exec()
    exit_code = window.exit_code
    window.poll_timer.stop()
    window.close()
    window.deleteLater()
    app.processEvents()
    return exit_code if smoke_output is not None else result
