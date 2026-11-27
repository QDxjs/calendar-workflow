"""Visible date labels must describe the page, independent of its batch."""

from datetime import date
import unittest
import xml.etree.ElementTree as ET

from generate import RENDERERS, metadata


class TemplateMetadataTests(unittest.TestCase):
    def labels(self, layout, day):
        svg = RENDERERS[layout](metadata(day, layout, "山高月小，水落石出。", "苏轼"))
        return ["".join(node.itertext()) for node in ET.fromstring(svg).iter("{http://www.w3.org/2000/svg}text")]

    def test_year_labels_follow_non_2027_dates(self):
        for day in (date(2026, 12, 31), date(2028, 2, 29), date(2028, 12, 31)):
            with self.subTest(day=day):
                self.assertIn(f"VOLUME {day.year}", self.labels("B", day))
                self.assertIn(str(day.year), self.labels("E", day))
                for layout in "ABCDEFGHI":
                    labels = self.labels(layout, day)
                    self.assertNotIn("VOLUME 2027", labels)
                    self.assertNotIn("2027", labels)

    def test_daily_indices_use_zero_padded_day_of_year(self):
        for day, expected in ((date(2027, 1, 1), "001"), (date(2028, 2, 29), "060"), (date(2028, 12, 31), "366")):
            for layout, prefix in (("A", "DAY / "), ("B", "ARCHIVE "), ("C", "NO. "), ("D", "READING / "), ("E", "NO. ")):
                with self.subTest(day=day, layout=layout):
                    self.assertIn(prefix + expected, self.labels(layout, day))
        self.assertIn("EDITION 001", self.labels("B", date(2028, 12, 31)))
