"""Protect complete, literal import diagnostics and the empty-import guard."""

import json
import os
from pathlib import Path
import tempfile
import unittest

os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
from PySide6.QtCore import Qt
from PySide6.QtWidgets import QApplication, QDialog

from quote_import_dialog import QuotePreviewDialog
from quote_library import inspect_quotes


class QuoteDialogTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.app = QApplication.instance() or QApplication([])

    def test_full_content_and_attribution_are_literal_and_rejections_are_locatable(self):
        quote = "正文" * 27 + "末尾完整"
        source = "《<测试作品>》 · 用户提供的人物"
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "input.json"
            path.write_text(json.dumps([
                {"name": quote, "from": source}, {"name": quote, "from": "重复出处"},
                {"name": "过" * 59, "from": "过长出处"},
            ], ensure_ascii=False), encoding="utf-8")
            preview = inspect_quotes(path, allow_empty=True)
            dialog = QuotePreviewDialog(preview, "<input>.json")
            try:
                self.assertTrue(dialog.confirm_button.isEnabled())
                self.assertIn(quote, dialog.details.toPlainText())
                self.assertIn(source, dialog.details.toPlainText())
                dialog.tabs.setCurrentIndex(1)
                self.assertIn(preview.issues[0].location, dialog.details.toPlainText())
                self.assertIn(preview.issues[0].duplicate_of, dialog.details.toPlainText())
                dialog.issues_view.selectRow(1)
                self.assertIn("过" * 59, dialog.details.toPlainText())
                model = dialog.accepted_view.model()
                self.assertEqual(model.data(model.index(0, 3), Qt.ItemDataRole.DisplayRole), source)
                self.assertTrue(dialog.details.isReadOnly())
            finally:
                dialog.close()
                dialog.deleteLater()

    def test_no_valid_rows_show_diagnostics_and_cannot_be_accepted(self):
        with tempfile.TemporaryDirectory() as scratch:
            path = Path(scratch) / "empty.json"
            path.write_text('[{"name":"短","from":"出处"}]', encoding="utf-8")
            dialog = QuotePreviewDialog(inspect_quotes(path, allow_empty=True), path.name)
            try:
                self.assertFalse(dialog.confirm_button.isEnabled())
                self.assertEqual(dialog.tabs.currentIndex(), 1)
                self.assertIn("第 1 条", dialog.details.toPlainText())
                dialog.accept()
                self.assertEqual(dialog.result(), QDialog.DialogCode.Rejected)
            finally:
                dialog.close()
                dialog.deleteLater()
