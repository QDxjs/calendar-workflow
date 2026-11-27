"""Manual content contracts, actual SVG eligibility and lossless publication."""

from datetime import date, timedelta
from pathlib import Path
import random
import tempfile
import unittest
from unittest.mock import patch
import xml.etree.ElementTree as ET

from batch_history import inspect_batch
from calendar_models import CalendarPage
from content_sources import ManualQuoteError, ManualQuoteSource, plan_manual_page, validate_manual_source
from generate import RENDERERS, metadata, prepare_pages, prepare_replay, validate_pages, validate_png, write_batch


class ManualQuoteTests(unittest.TestCase):
    day = date(2028, 2, 29)

    def test_effective_character_and_xml_rules_are_field_specific(self):
        for value in ("，。！？…", "\x00正文", "正文\ud800", "\x0b", "\x0c"):
            with self.subTest(value=repr(value)), self.assertRaises(ManualQuoteError) as error:
                validate_manual_source(ManualQuoteSource(value))
            self.assertEqual(error.exception.field, "quote")
        with self.assertRaises(ManualQuoteError) as error:
            validate_manual_source(ManualQuoteSource("春", "出处\x00"))
        self.assertEqual(error.exception.field, "source")
        self.assertEqual(validate_manual_source(ManualQuoteSource("  春  ", "  原样署名  ")),
                         ManualQuoteSource("春", "原样署名"))

    def test_empty_whitespace_and_source_only_are_valid_authored_content(self):
        for quote in ("", " \n\t ", "\r\n"):
            for source in ("", "  自己的署名  "):
                with self.subTest(quote=repr(quote), source=source):
                    content = validate_manual_source(ManualQuoteSource(quote, source))
                    self.assertEqual(content, ManualQuoteSource("", source.strip()))
                    plan = plan_manual_page(self.day, content, "RANDOM", 17)
                    self.assertEqual((plan.pages[0].quote, plan.pages[0].source, plan.pages[0].quote_id),
                                     ("", source.strip(), ""))
                    self.assertEqual(plan.pages[0].layout, random.Random(17).choice(sorted(RENDERERS)))

    def test_blank_pages_do_not_bypass_corpus_id_or_filename_checks(self):
        with self.assertRaisesRegex(ValueError, "语料编号"):
            validate_pages([CalendarPage(self.day, "A", "A", "", "", "corpus-id")])
        page = plan_manual_page(self.day, ManualQuoteSource(""), "A", 17).pages[0]
        with self.assertRaisesRegex(ValueError, "文件名会冲突"):
            validate_pages([page, page])
        with tempfile.TemporaryDirectory() as temporary:
            path = Path(temporary) / "input.csv"
            path.write_text("date,quote,source,layout\n2028-02-29,,,A\n", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "缺少 quote"):
                prepare_pages(path)

    def test_blank_and_source_only_nine_pngs_and_multi_date_replay(self):
        with tempfile.TemporaryDirectory() as temporary:
            for index, source in enumerate(("", "自己的署名")):
                pages = [plan_manual_page(self.day + timedelta(days=offset),
                                          ManualQuoteSource(" \n\t ", source), letter, 17).pages[0]
                         for offset, letter in enumerate(RENDERERS)]
                batch = Path(temporary) / f"blank-{index}"
                write_batch(pages, batch, seed=17, on_progress=lambda *_: None)
                self.assertEqual(prepare_replay(batch / "manifest.csv"), (pages, 17))
                summary = inspect_batch(batch)
                self.assertEqual(summary.pages, tuple(pages))
                self.assertEqual(summary.status, "文件齐全")
                replay = Path(temporary) / f"replayed-{index}"
                write_batch(list(summary.pages), replay, seed=summary.seed, on_progress=lambda *_: None)
                for page in pages:
                    name = f"{page.target_date}_layout-{page.layout}"
                    validate_png(batch / "png" / f"{name}.png")
                    root = ET.parse(batch / "svg" / f"{name}.svg").getroot()
                    texts = ["".join(element.itertext()) for element in root.iter()
                             if element.tag.rsplit("}", 1)[-1] == "text"]
                    self.assertNotIn("“", texts)
                    self.assertNotIn("", texts)
                    if source:
                        self.assertIn(source, "".join(texts))
                    for kind in ("svg", "png"):
                        filename = f"{name}.{kind}"
                        self.assertEqual((batch / kind / filename).read_bytes(), (replay / kind / filename).read_bytes())

    def test_plan_keeps_internal_newlines_optional_source_and_empty_id(self):
        content = ManualQuoteSource(" \n春风又绿江南岸\n明月何时照我还\n ", "  ")
        plan = plan_manual_page(self.day, content, "A", 17)
        page = plan.pages[0]
        self.assertEqual((page.quote, page.source, page.quote_id),
                         ("春风又绿江南岸\n明月何时照我还", "", ""))
        self.assertEqual((page.layout_selection, plan.seed), ("A", 17))

    def test_over_58_is_soft_limit_and_uses_no_rasterizer(self):
        with patch("generate.svg_to_png", side_effect=AssertionError("must not rasterize")):
            plan = plan_manual_page(self.day, ManualQuoteSource("春" * 65), "RANDOM", 17)
        self.assertEqual(len(plan.pages[0].quote), 65)

    def test_random_layout_trials_match_actual_eligibility_and_seed(self):
        content = ManualQuoteSource("\n".join(["春风又绿江南岸"] * 5))
        eligible = []
        for layout in RENDERERS:
            try:
                plan_manual_page(self.day, content, layout, 17)
            except ManualQuoteError:
                pass
            else:
                eligible.append(layout)
        self.assertEqual(eligible, ["A", "E"])
        for seed in range(20):
            plan = plan_manual_page(self.day, content, "RANDOM", seed)
            self.assertEqual(plan.pages[0].layout, random.Random(seed).choice(eligible))
            self.assertEqual(plan, plan_manual_page(self.day, content, "RANDOM", seed))
            self.assertEqual(plan.pages[0].layout_selection, "random")
        # Determinism must not depend on caller mapping insertion order.
        self.assertEqual(plan_manual_page(self.day, content, "RANDOM", 17),
                         plan_manual_page(self.day, content, "RANDOM", 17,
                                          renderers=dict(reversed(list(RENDERERS.items())))))

    def test_fixed_and_all_layout_overflow_are_clear_and_do_not_publish(self):
        content = ManualQuoteSource("\n".join(["春风"] * 6))
        for layout, message in (("B", "版式 B"), ("RANDOM", "全部版式")):
            with self.subTest(layout=layout), self.assertRaisesRegex(ManualQuoteError, message):
                plan_manual_page(self.day, content, layout, 17)

    def test_empty_source_and_xml_escaping_across_nine_actual_pngs(self):
        content = ManualQuoteSource('春风 & <script>文字</script>\n明月 "你好"')
        pages = [plan_manual_page(self.day, content, letter, 17).pages[0] for letter in RENDERERS]
        for page in pages:
            svg = RENDERERS[page.layout](metadata(self.day, page.layout, page.quote, page.source))
            root = ET.fromstring(svg)
            self.assertFalse(any(element.tag.rsplit("}", 1)[-1] == "script" for element in root.iter()))
            self.assertNotIn("SOURCE / CITATION", svg)
        with tempfile.TemporaryDirectory() as temporary:
            batch = Path(temporary) / "manual"
            write_batch(pages, batch, seed=17, on_progress=lambda *_: None)
            restored, seed = prepare_replay(batch / "manifest.csv")
            self.assertEqual((restored, seed), (pages, 17))
            history = inspect_batch(batch)
            self.assertEqual(history.pages, tuple(pages))
            self.assertEqual(history.status, "文件齐全")
            for page in pages:
                validate_png(batch / "png" / f"{self.day}_layout-{page.layout}.png")
            replay = Path(temporary) / "replay"
            write_batch(restored, replay, seed=seed, on_progress=lambda *_: None)
            for kind in ("svg", "png"):
                for original in (batch / kind).iterdir():
                    self.assertEqual(original.read_bytes(), (replay / kind / original.name).read_bytes())
