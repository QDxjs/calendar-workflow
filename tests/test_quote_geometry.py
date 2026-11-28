"""Keep quotation text, separator and attribution inside their original canvas."""

from datetime import date
import unittest
import xml.etree.ElementTree as ET

from generate import RENDERERS, metadata
from quote_library import builtin_quotes
from svg_primitives import label_block


SVG_NS = "{http://www.w3.org/2000/svg}"
QUOTE_BOUNDS = {
    "A": (800, 1208), "B": (816, 1044), "C": (930, 1232),
    "D": (936, 1186), "E": (610, 1142), "F": (810, 1224),
    "G": (842, 1162), "H": (834, 1164), "I": (868, 1166),
}


def text_bounds(element):
    size = float(element.attrib["font-size"])
    baseline = float(element.attrib["y"])
    offsets = [float(span.attrib.get("dy", 0)) for span in element.findall(f"{SVG_NS}tspan")]
    return baseline - size, baseline + sum(offsets) + size * 0.25


class QuoteGeometryTests(unittest.TestCase):
    def assert_geometry(self, layout, quote, source):
        root = ET.fromstring(RENDERERS[layout](metadata(date(2026, 11, 28), layout, quote, source, "书房")))
        self.assertEqual((root.attrib["width"], root.attrib["height"], root.attrib["viewBox"]),
                         ("1122", "1402", "0 0 1122 1402"))
        group = root.find(f"{SVG_NS}g[@data-role='quote-block']")
        self.assertIsNotNone(group)
        elements = group.findall(f"{SVG_NS}text")
        lower, upper = QUOTE_BOUNDS[layout]
        for element in elements:
            first, last = text_bounds(element)
            self.assertGreaterEqual(first + 0.001, lower)
            self.assertLessEqual(last, upper + 0.001)
        if source and layout != "B":
            self.assertEqual(len(elements), 2)
            body, attribution = elements
            rule = group.find(f"{SVG_NS}line")
            rule_y = float(rule.attrib["y1"])
            self.assertGreaterEqual(rule_y - text_bounds(body)[1], 21.9)
            self.assertGreaterEqual(text_bounds(attribution)[0] - rule_y, 17.9)
            self.assertEqual("".join(attribution.itertext()).replace("\n", ""), source.replace("\n", ""))
        return group

    def test_screenshot_quote_keeps_rule_below_the_last_line(self):
        quote = next(item for item in builtin_quotes() if item["quote"].startswith("我们不能轻易将"))
        group = self.assert_geometry("C", quote["quote"], quote["source"])
        body = group.find(f"{SVG_NS}text")
        self.assertEqual(len(body.findall(f"{SVG_NS}tspan")), 3)
        self.assertEqual(float(body.attrib["font-size"]), 39)

    def test_short_long_multiline_quotes_and_two_line_sources_across_layouts(self):
        for layout in RENDERERS:
            limit = 5 if layout in "AE" else 4
            for quote in ("山高月小，水落石出。", "春风" * 29, "\n".join(["春风又绿江南岸"] * limit)):
                for source in ("", "原样出处", "作品名称" * 15 + " · 作者"):
                    with self.subTest(layout=layout, quote=quote, source=source):
                        self.assert_geometry(layout, quote, source)

    def test_excessive_attribution_is_rejected_instead_of_overflowing(self):
        with self.assertRaisesRegex(ValueError, "出处无法"):
            label_block("来源" * 1000, x=0, y=0, width=100, font_size=20)
