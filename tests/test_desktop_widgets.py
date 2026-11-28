"""Actual pointer, wheel and keyboard checks for the shared selector."""

import os
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")

from PySide6.QtCore import QPoint, QPointF, Qt
from PySide6.QtGui import QWheelEvent
from PySide6.QtTest import QSignalSpy, QTest
from PySide6.QtWidgets import QApplication, QStyle, QStyleOptionComboBox

from desktop import APP_STYLE
from desktop_widgets import LayoutSelectionWidget, SelectionComboBox
from generate import LAYOUT_LABELS


def wheel_event(widget, delta):
    position = widget.rect().center()
    return QWheelEvent(
        QPointF(position), QPointF(widget.mapToGlobal(position)), QPoint(),
        QPoint(0, delta), Qt.MouseButton.NoButton, Qt.KeyboardModifier.NoModifier,
        Qt.ScrollPhase.NoScrollPhase, False,
    )


class SelectionComboBoxTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])
        cls.app.setStyle("Fusion")
        cls.app.setStyleSheet(APP_STYLE)

    def setUp(self):
        self.combo = SelectionComboBox()
        self.combo.addItems([f"Option {index}" for index in range(60)])
        self.combo.setCurrentIndex(1)
        self.combo.resize(240, 44)
        self.combo.show()
        self.app.processEvents()

    def tearDown(self):
        self.combo.hidePopup()
        self.combo.close()
        self.combo.deleteLater()
        self.app.processEvents()

    def test_closed_selector_does_not_change_with_wheel_even_when_focused(self):
        changes = QSignalSpy(self.combo.currentIndexChanged)
        for focused in (False, True):
            if focused:
                self.combo.setFocus()
            else:
                self.combo.clearFocus()
            for delta in (-120, 120, -240):
                event = wheel_event(self.combo, delta)
                QApplication.sendEvent(self.combo, event)
                self.assertEqual(self.combo.currentIndex(), 1)
                self.assertFalse(event.isAccepted())
        self.assertEqual(changes.count(), 0)
        self.assertEqual(self.combo.focusPolicy(), Qt.FocusPolicy.StrongFocus)

    def test_arrow_click_opens_popup_and_list_click_selects(self):
        option = QStyleOptionComboBox()
        self.combo.initStyleOption(option)
        arrow = self.combo.style().subControlRect(
            QStyle.ComplexControl.CC_ComboBox, option,
            QStyle.SubControl.SC_ComboBoxArrow, self.combo,
        )
        QTest.mouseClick(self.combo, Qt.MouseButton.LeftButton, pos=arrow.center())
        self.app.processEvents()
        self.assertTrue(self.combo.view().isVisible())
        index = self.combo.model().index(2, 0)
        rectangle = self.combo.view().visualRect(index)
        QTest.mouseMove(self.combo.view().viewport(), rectangle.center())
        QTest.qWait(200)
        QTest.mouseClick(
            self.combo.view().viewport(), Qt.MouseButton.LeftButton,
            pos=rectangle.center(), delay=20,
        )
        self.app.processEvents()
        self.assertEqual(self.combo.currentIndex(), 2)
        self.assertFalse(self.combo.view().isVisible())

    def test_open_popup_still_scrolls(self):
        self.combo.showPopup()
        self.app.processEvents()
        view = self.combo.view()
        scrollbar = view.verticalScrollBar()
        self.assertGreater(scrollbar.maximum(), 0)
        before = scrollbar.value()
        QApplication.sendEvent(view.viewport(), wheel_event(view.viewport(), -120))
        self.app.processEvents()
        self.assertGreater(scrollbar.value(), before)
        self.assertTrue(view.isVisible())

    def test_keyboard_navigation_still_changes_selection(self):
        self.combo.setFocus()
        QTest.keyClick(self.combo, Qt.Key.Key_Down)
        self.assertEqual(self.combo.currentIndex(), 2)


class LayoutSelectionWidgetTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def setUp(self):
        self.widget = LayoutSelectionWidget(LAYOUT_LABELS)
        self.widget.show()
        self.app.processEvents()

    def tearDown(self):
        self.widget.close()
        self.widget.deleteLater()
        self.app.processEvents()

    def test_pointer_multiselect_random_all_and_last_unchecked(self):
        changes = QSignalSpy(self.widget.selectionChanged)
        self.assertEqual(self.widget.selection(), "RANDOM")
        for letter in "FCA":
            checkbox = self.widget.checkboxes[letter]
            QTest.mouseClick(checkbox, Qt.MouseButton.LeftButton, pos=QPoint(7, checkbox.height() // 2))
        self.assertEqual(self.widget.selection(), "A+C+F")
        self.assertEqual(changes.count(), 3)
        self.assertFalse(self.widget.random_checkbox.isChecked())
        self.widget.all_button.click()
        self.assertEqual(self.widget.selected_layouts(), tuple(LAYOUT_LABELS))
        self.widget.random_checkbox.click()
        self.assertEqual(self.widget.selection(), "RANDOM")
        self.assertTrue(all(not checkbox.isChecked() for checkbox in self.widget.checkboxes.values()))
        self.widget.checkboxes["C"].click()
        self.widget.checkboxes["C"].click()
        self.assertEqual(self.widget.selection(), "RANDOM")
        self.widget.random_checkbox.click()
        self.assertTrue(self.widget.random_checkbox.isChecked())

    def test_wheel_never_toggles_layout_and_keyboard_space_does(self):
        self.widget.set_selection("A+C")
        checkbox = self.widget.checkboxes["F"]
        checkbox.setFocus()
        QApplication.sendEvent(checkbox, wheel_event(checkbox, -120))
        self.assertEqual(self.widget.selection(), "A+C")
        QTest.keyClick(checkbox, Qt.Key.Key_Space)
        self.assertEqual(self.widget.selection(), "A+C+F")


if __name__ == "__main__":
    unittest.main()
