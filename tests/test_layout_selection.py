"""Multiple layouts expand per day without changing quote or replay contracts."""

from datetime import date, timedelta
import unittest

from content_sources import ManualQuoteError, ManualQuoteSource, plan_manual_page
from generate import RENDERERS, validate_pages
from launcher import plan_pages
from layout_selection import resolve_layouts


class LayoutSelectionTests(unittest.TestCase):
    def test_selections_are_validated_and_ordered(self):
        self.assertEqual(resolve_layouts("F+A+C+A", RENDERERS), ("A", "C", "F"))
        self.assertEqual(resolve_layouts("random", RENDERERS), ())
        for value in ("", "A+", "Z", "RANDOM+A", "A+Z"):
            with self.subTest(value=value), self.assertRaises(ValueError):
                resolve_layouts(value, RENDERERS)

    def test_dates_expand_with_one_distinct_quote_per_day(self):
        days = [date(2026, 11, 27) + timedelta(days=offset) for offset in range(2)]
        quotes = [{"quote": "今天的第一条语录", "source": "甲", "quote_id": "one"},
                  {"quote": "今天的第二条语录", "source": "乙", "quote_id": "two"}]
        pages = plan_pages(days, quotes, "F+A+C", 17, creator="书房")
        self.assertEqual(len(pages), 6)
        self.assertEqual(pages, plan_pages(days, quotes, "A+C+F", 17, creator="书房"))
        validate_pages(pages)
        single = plan_pages(days, quotes, "A", 17, creator="书房")
        for index, day in enumerate(days):
            variants = pages[index * 3:(index + 1) * 3]
            self.assertEqual(variants[0], single[index])
            self.assertEqual([page.layout for page in variants], ["A", "C", "F"])
            self.assertTrue(all(page.creator == "书房" and page.target_date == day for page in variants))
            self.assertEqual(len({(page.quote, page.source, page.quote_id) for page in variants}), 1)
        self.assertNotEqual(pages[0].quote_id, pages[3].quote_id)
        with self.assertRaisesRegex(ValueError, "少于"):
            plan_pages(days, quotes[:1], "A+C+F", 17)

    def test_random_keeps_one_page_per_day_and_avoids_adjacent_repeats(self):
        days = [date(2026, 11, 27) + timedelta(days=offset) for offset in range(2)]
        quotes = [{"quote": f"日历语录{offset}", "source": "来源", "quote_id": str(offset)} for offset in range(2)]
        pages = plan_pages(days, quotes, "RANDOM", 17)
        self.assertEqual(len(pages), 2)
        self.assertTrue(all(page.layout_selection == "random" for page in pages))
        self.assertNotEqual(pages[0].layout, pages[1].layout)

    def test_manual_multiselect_includes_all_or_reports_each_failed_layout(self):
        day = date(2026, 11, 28)
        plan = plan_manual_page(day, ManualQuoteSource("同一段文字", "原样出处"), "F+A+C", 17)
        self.assertEqual([page.layout for page in plan.pages], ["A", "C", "F"])
        self.assertTrue(all(page.quote == "同一段文字" and page.source == "原样出处" for page in plan.pages))
        validate_pages(list(plan.pages))
        content = ManualQuoteSource("\n".join(["春风又绿江南岸"] * 5))
        self.assertEqual(len(plan_manual_page(day, content, "A+E", 17).pages), 2)
        with self.assertRaisesRegex(ManualQuoteError, "版式 B、C"):
            plan_manual_page(day, content, "A+B+C", 17)
        self.assertEqual(len(plan_manual_page(day, ManualQuoteSource("", ""), "A+C+F").pages), 3)
