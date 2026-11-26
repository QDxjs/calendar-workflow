"""Compact, user-invoked dialogs for layout examples and actual page previews."""

from __future__ import annotations

from PySide6.QtCore import QEvent, QSize, Qt
from PySide6.QtGui import QIcon, QPixmap
from PySide6.QtWidgets import (
    QApplication, QComboBox, QDialog, QDialogButtonBox, QGridLayout,
    QHBoxLayout, QLabel, QPushButton, QScrollArea, QToolButton,
    QVBoxLayout, QWidget,
)

from calendar_models import CalendarPage
from generate import LAYOUT_LABELS


def _size_dialog(dialog: QDialog, width: int, height: int) -> None:
    screen = QApplication.primaryScreen()
    available = screen.availableGeometry().size() if screen else QSize(1280, 800)
    dialog.resize(min(width, available.width() - 40), min(height, available.height() - 60))


class LayoutChooserDialog(QDialog):
    def __init__(self, selected: str, parent: QWidget) -> None:
        super().__init__(parent)
        self.setWindowTitle("查看版式示意")
        self.setMinimumSize(540, 420)
        _size_dialog(self, 680, 720)
        self.selected_layout = selected
        outer = QVBoxLayout(self)
        outer.setContentsMargins(18, 18, 18, 16)
        hint = QLabel("版式示意 · 九种版式使用同一条内置语录，与本次抽选内容无关。\n点击缩略图选择；本次真实内容请使用“查看首张效果”。")
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
            button.setChecked(selected == letter)
            button.setEnabled(False)
            button.setAccessibleName(f"选择版式 {letter} · {name}")
            button.clicked.connect(lambda _checked=False, choice=letter: self._select(choice))
            grid.addWidget(button, index // 3, index % 3)
            self.buttons[letter] = button
        scroll.setWidget(content)
        outer.addWidget(scroll, 1)
        actions = QHBoxLayout()
        self.random_button = QPushButton("使用随机版式")
        self.random_button.clicked.connect(lambda: self._select("随机"))
        actions.addWidget(self.random_button)
        actions.addStretch(1)
        self.close_button = QPushButton("取消")
        self.close_button.clicked.connect(self.reject)
        actions.addWidget(self.close_button)
        outer.addLayout(actions)

    def _select(self, layout: str) -> None:
        self.selected_layout = layout
        self.accept()

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
        self.close_button.setText("关闭")

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
        self.zoom = QComboBox()
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
