"""Compact, user-invoked dialogs for layout examples and actual page previews."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QDialog, QDialogButtonBox, QGridLayout,
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QToolButton,
    QVBoxLayout, QWidget,
)

from calendar_models import CalendarPage
from desktop_widgets import SelectionComboBox
from generate import LAYOUT_LABELS
from layout_selection import resolve_layouts


def _size_dialog(dialog: QDialog, width: int, height: int) -> None:
    screen = QApplication.primaryScreen()
    available = screen.availableGeometry().size() if screen else QSize(1280, 800)
    dialog.resize(min(width, available.width() - 40), min(height, available.height() - 60))


class LayoutChooserDialog(QDialog):
    def __init__(self, selected: str, parent: QWidget, *, random_mode: bool = False) -> None:
        super().__init__(parent)
        self.setWindowTitle("查看版式示意")
        self.setMinimumSize(540, 420)
        _size_dialog(self, 680, 720)
        self.selected_layouts = set(resolve_layouts(selected, LAYOUT_LABELS))
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 16)
        purpose = ("本次为随机制作：勾选项作为随机范围，总张数由“张 / per Date”控制。" if random_mode else
                   "本次为同语录换版式：所选版式各出一张，同一天使用同一条语录。")
        hint = QLabel(f"版式示意 · 九种版式使用同一条内置语录，与本次抽选内容无关。\n点击缩略图可多选，再点“确认使用”。{purpose}")
        hint.setWordWrap(True)
        outer.addWidget(hint)
        self.status = QLabel("正在准备九种版式示意，可随时取消。")
        self.status.setWordWrap(True)
        outer.addWidget(self.status)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        content = QWidget()
        grid = QGridLayout(content)
        grid.setSpacing(10)
        self.buttons: dict[str, QToolButton] = {}
        for index, (letter, name) in enumerate(LAYOUT_LABELS.items()):
            button = QToolButton()
            button.setText(f"{letter} · {name}")
            button.setToolButtonStyle(Qt.ToolButtonStyle.ToolButtonTextUnderIcon)
            button.setIconSize(QSize(140, 175))
            button.setMinimumHeight(215)
            button.setCheckable(True)
            button.setChecked(letter in self.selected_layouts)
            button.setEnabled(False)
            button.setAccessibleName(f"选择版式 {letter} · {name}")
            button.clicked.connect(lambda checked=False, choice=letter: self._toggle_layout(choice, checked))
            grid.addWidget(button, index // 3, index % 3)
            self.buttons[letter] = button
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        actions = QHBoxLayout()
        self.random_button = QPushButton("使用随机版式")
        self.random_button.clicked.connect(self._use_random)
        actions.addWidget(self.random_button)
        self.all_button = QPushButton("全选")
        self.all_button.clicked.connect(self._select_all)
        actions.addWidget(self.all_button)
        actions.addStretch(1)
        self.apply_button = QPushButton("确认使用")
        self.apply_button.setEnabled(False)
        self.apply_button.clicked.connect(self.accept)
        actions.addWidget(self.apply_button)
        self.close_button = QPushButton("取消")
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        outer.addLayout(actions)

    def selection(self) -> str:
        return "+".join(sorted(self.selected_layouts)) if self.selected_layouts else "RANDOM"

    def _use_random(self) -> None:
        self.selected_layouts.clear()
        self.accept()

    def _toggle_layout(self, layout: str, checked: bool) -> None:
        if checked:
            self.selected_layouts.add(layout)
        else:
            self.selected_layouts.discard(layout)
        self._sync_selection()

    def _select_all(self) -> None:
        self.selected_layouts = set(LAYOUT_LABELS)
        self._sync_selection()

    def _sync_selection(self) -> None:
        for letter, button in self.buttons.items():
            button.setChecked(letter in self.selected_layouts)
        count = len(self.selected_layouts)
        self.apply_button.setEnabled(count > 0)
        self.apply_button.setText(f"确认使用（{count} 种）" if count else "请选择版式")

    def set_images(self, images: tuple[tuple[str, bytes], ...]) -> None:
        for letter, data in images:
            pixmap = QPixmap()
            if not pixmap.loadFromData(data, "PNG"):
                raise ValueError("版式示意图片无法读取，请关闭后重试。")
            self.buttons[letter].setIcon(QIcon(pixmap.scaled(
                QSize(280, 350), Qt.AspectRatioMode.KeepAspectRatio,
                Qt.TransformationMode.SmoothTransformation,
            )))
            self.buttons[letter].setEnabled(True)
        self.status.setText("版式示意 · 可滚动查看全部九种版式。")
        self._sync_selection()

    def show_error(self, message: str) -> None:
        self.status.setText(f"版式示意未完成：{message}\n请关闭后重试。")
        self.close_button.setText("关闭")


class FirstPageDialog(QDialog):
    def __init__(self, page: CalendarPage, image: bytes, page_count: int, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("查看首张效果")
        self.setMinimumSize(440, 400)
        _size_dialog(self, 690, 760)
        self.pixmap = QPixmap()
        if not self.pixmap.loadFromData(image, "PNG"):
            raise ValueError("首张预览图片无法读取，请重试。")
        outer = QVBoxLayout(self)
        title = QLabel(f"本次首张效果 · {page.target_date.isoformat()} · {page.layout} · {LAYOUT_LABELS[page.layout]}")
        title.setWordWrap(True)
        outer.addWidget(title)
        hint = QLabel(f"本次共 {page_count} 页。设置不变时，正式生成的首张与此一致。\n此处尚未保存日历；关闭后点击“生成日历”导出整批。")
        hint.setWordWrap(True)
        outer.addWidget(hint)
        controls = QHBoxLayout()
        controls.addWidget(QLabel("显示比例"))
        self.zoom = SelectionComboBox()
        self.zoom.setAccessibleName("首张预览显示比例")
        self.zoom.addItems(("适应窗口", "100% · 原始尺寸"))
        controls.addWidget(self.zoom)
        controls.addStretch(1)
        outer.addLayout(controls)
        self.scroll = QScrollArea()
        self.scroll.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.image = QLabel()
        self.scroll.setWidget(self.image)
        self.scroll.viewport().installEventFilter(self)
        outer.addWidget(self.scroll, 1)
        self.zoom.currentIndexChanged.connect(self._resize_image)
        buttons = QDialogButtonBox(QDialogButtonBox.StandardButton.Close)
        buttons.button(QDialogButtonBox.StandardButton.Close).setText("关闭")
        buttons.rejected.connect(self.reject)
        outer.addWidget(buttons)
        self._resize_image()

    def eventFilter(self, watched: object, event: object) -> bool:
        if watched is self.scroll.viewport() and event.type() == QEvent.Type.Resize:
            self._resize_image()
        return super().eventFilter(watched, event)

    def _resize_image(self, *_args: object) -> None:
        size = self.pixmap.size() if self.zoom.currentIndex() else self.scroll.viewport().size() - QSize(4, 4)
        scaled = self.pixmap.scaled(
            size.expandedTo(QSize(1, 1)), Qt.AspectRatioMode.KeepAspectRatio,
            Qt.TransformationMode.SmoothTransformation,
        )
        self.image.setPixmap(scaled)
        self.image.resize(scaled.size())


class BatchPreviewDialog(FirstPageDialog):
    def __init__(self, pages: tuple[CalendarPage, ...], images: tuple[tuple[str, bytes], ...],
                 parent: QWidget) -> None:
        if not pages or len(pages) != len(images):
            raise ValueError("本批预览页数不完整，请重新预览。")
        super().__init__(pages[0], images[0][1], len(pages), parent)
        self.setWindowTitle("预览本批")
        self.pages, self.images, self.index = pages, images, 0
        outer = self.layout()
        outer.itemAt(0).widget().setText("本批全部页面 · 设置不变时，导出内容与预览一致。")
        outer.itemAt(1).widget().setText("关闭预览后点击“生成日历”保存；如需更换内容，点击主窗口的“重抽本批”。")
        self.navigation = QHBoxLayout()
        self.previous_button = QPushButton("上一张")
        self.next_button = QPushButton("下一张")
        self.position = QLabel()
        self.position.setWordWrap(True)
        self.navigation.addWidget(self.previous_button)
        self.navigation.addWidget(self.position, 1)
        self.navigation.addWidget(self.next_button)
        outer.insertLayout(2, self.navigation)
        self.previous_button.clicked.connect(lambda: self.show_page(self.index - 1))
        self.next_button.clicked.connect(lambda: self.show_page(self.index + 1))
        self.zoom.setAccessibleName("本批预览显示比例")
        self.show_page(0)

    def show_page(self, index: int) -> None:
        if not 0 <= index < len(self.pages):
            return
        page = self.pages[index]
        pixmap = QPixmap()
        if not pixmap.loadFromData(self.images[index][1], "PNG"):
            raise ValueError(f"第 {index + 1} 张预览无法读取，请重试。")
        self.index, self.pixmap = index, pixmap
        self.position.setText(f"{index + 1} / {len(self.pages)} 张 · {page.target_date} · 版式 {page.layout}")
        self.previous_button.setEnabled(index > 0)
        self.next_button.setEnabled(index < len(self.pages) - 1)
        self._resize_image()
