"""Shared desktop controls with explicit, deliberate selection behavior."""

from collections.abc import Mapping

from PySide6.QtCore import QPointF, QRegularExpression, QSignalBlocker, Qt, Signal
from PySide6.QtGui import QColor, QPainter, QPolygonF, QRegularExpressionValidator, QWheelEvent
from PySide6.QtWidgets import (
    QAbstractScrollArea, QApplication, QCheckBox, QComboBox, QGridLayout, QLineEdit,
    QStyle, QStyleOptionComboBox, QToolButton, QWidget,
)

from layout_selection import resolve_layouts


class PositiveIntegerEdit(QLineEdit):
    def __init__(self, parent=None) -> None:
        super().__init__("1", parent)
        self.setValidator(QRegularExpressionValidator(QRegularExpression("[1-9][0-9]*"), self))
        self.setAccessibleName("数量（张 / per Date），仅正整数")
        self.setToolTip("每个日期生成的总张数；只接受 1、2、3…，不接受 0、小数或负数。")

    def value(self) -> int:
        if not self.hasAcceptableInput():
            raise ValueError("数量必须是正整数（1、2、3…），单位：张 / per Date。")
        return int(self.text())


class SelectionComboBox(QComboBox):
    def __init__(self, parent=None) -> None:
        super().__init__(parent)
        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setCursor(Qt.CursorShape.PointingHandCursor)

    def wheelEvent(self, event) -> None:
        if self.view().isVisible():
            super().wheelEvent(event)
            return
        ancestor = self.parentWidget()
        while ancestor is not None and not isinstance(ancestor, QAbstractScrollArea):
            ancestor = ancestor.parentWidget()
        if ancestor is None:
            event.ignore()
            return
        viewport = ancestor.viewport()
        forwarded = QWheelEvent(
            QPointF(viewport.mapFromGlobal(event.globalPosition().toPoint())),
            event.globalPosition(), event.pixelDelta(), event.angleDelta(),
            event.buttons(), event.modifiers(), event.phase(), event.inverted(),
        )
        QApplication.sendEvent(viewport, forwarded)
        event.setAccepted(forwarded.isAccepted())

    def paintEvent(self, event) -> None:
        super().paintEvent(event)
        option = QStyleOptionComboBox()
        self.initStyleOption(option)
        arrow = self.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, option,
            QStyle.SubControl.SC_ComboBoxArrow, self,
        )
        center = arrow.center()
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        painter.setPen(Qt.PenStyle.NoPen)
        painter.setBrush(QColor("#6755a8" if self.isEnabled() else "#a0a6b5"))
        painter.drawPolygon(QPolygonF([
            QPointF(center.x() - 4, center.y() - 2),
            QPointF(center.x() + 4, center.y() - 2),
            QPointF(center.x(), center.y() + 3),
        ]))
        painter.end()


class LayoutSelectionWidget(QWidget):
    selectionChanged = Signal()

    def __init__(self, choices: Mapping[str, str], parent=None) -> None:
        super().__init__(parent)
        self.choices = dict(choices)
        self._selection = "RANDOM"
        grid = QGridLayout(self)
        grid.setContentsMargins(0, 0, 0, 0)
        grid.setHorizontalSpacing(8)
        grid.setVerticalSpacing(7)
        self.random_checkbox = QCheckBox("随机（每天 1 张）")
        self.random_checkbox.setChecked(True)
        self.random_checkbox.toggled.connect(self._random_changed)
        grid.addWidget(self.random_checkbox, 0, 0, 1, 4)
        self.all_button = QToolButton()
        self.all_button.setText("全选")
        self.all_button.setToolTip("每天生成 A–I 全部九种版式，使用同一条语录。")
        self.all_button.clicked.connect(lambda: self.set_selection("+".join(self.choices)))
        grid.addWidget(self.all_button, 0, 4)
        self.checkboxes: dict[str, QCheckBox] = {}
        for index, (letter, name) in enumerate(self.choices.items()):
            checkbox = QCheckBox(letter)
            checkbox.setToolTip(f"{letter} · {name}；勾选后每天单独生成一张。")
            checkbox.setAccessibleName(f"版式 {letter} · {name}")
            checkbox.toggled.connect(
                lambda checked, layout=letter: self._layout_changed(layout, checked),
            )
            grid.addWidget(checkbox, 1 + index // 5, index % 5)
            self.checkboxes[letter] = checkbox

    def set_random_mode(self, enabled: bool) -> None:
        self.random_checkbox.setText("全部 A–I 随机" if enabled else "随机选 1 种版式")
        self.all_button.setToolTip("选择 A–I 作为随机范围。" if enabled else "每天生成 A–I 全部九种版式，使用同一条语录。")
        for letter, checkbox in self.checkboxes.items():
            checkbox.setToolTip(
                f"{letter} · {self.choices[letter]}；仅从勾选的版式中随机。" if enabled else
                f"{letter} · {self.choices[letter]}；每天单独生成一张。"
            )

    def selection(self) -> str:
        return self._selection

    def selected_layouts(self) -> tuple[str, ...]:
        return resolve_layouts(self._selection, self.choices)

    def selection_text(self) -> str:
        layouts = self.selected_layouts()
        if not layouts:
            return "随机版式 · 每天 1 张"
        if len(layouts) == 1:
            return f"{layouts[0]} · {self.choices[layouts[0]]}"
        return f"多选版式 {'、'.join(layouts)} · 每天 {len(layouts)} 张"

    def set_selection(self, selection: str) -> None:
        layouts = resolve_layouts(selection, self.choices)
        normalized = "+".join(layouts) if layouts else "RANDOM"
        changed = normalized != self._selection
        self._selection = normalized
        with QSignalBlocker(self.random_checkbox):
            self.random_checkbox.setChecked(not layouts)
        for letter, checkbox in self.checkboxes.items():
            with QSignalBlocker(checkbox):
                checkbox.setChecked(letter in layouts)
        if changed:
            self.selectionChanged.emit()

    def _random_changed(self, checked: bool) -> None:
        if checked or not self.selected_layouts():
            self.set_selection("RANDOM")

    def _layout_changed(self, letter: str, checked: bool) -> None:
        layouts = set(self.selected_layouts())
        if checked:
            layouts.add(letter)
        else:
            layouts.discard(letter)
        self.set_selection("+".join(sorted(layouts)) if layouts else "RANDOM")
