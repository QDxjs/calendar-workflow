"""Corpus search and nonrepeating recommendations operate on original records."""

import unittest

from quote_selection import CandidateSampler, QuoteSearch


class QuoteSelectionTests(unittest.TestCase):
    def setUp(self):
        self.quotes = [
            {"quote": "明月几时有？把酒问青天。", "source": "《水调歌头》 · 苏轼", "quote_id": "first"},
            {"quote": "海上生明月，天涯共此时。", "source": "《望月怀远》 · 张九龄", "quote_id": "second"},
            {"quote": "Hello，World！", "source": "ＦＯＯ · Bar", "quote_id": "third"},
        ]
        self.index = QuoteSearch(self.quotes)

    def test_fragment_keywords_attribution_and_normalization(self):
        for query, expected in (("明月 几时有", [0]), ("苏轼 明月", [0]), ("水调歌头", [0]),
                                ("明月", [0, 1]), ("ｈｅｌｌｏ world", [2]),
                                ("foo BAR", [2]), ("明月，几时有！", [0])):
            with self.subTest(query=query):
                self.assertEqual(self.index.search(query), [self.quotes[index] for index in expected])
        self.assertEqual(self.index.search("不存在的文字"), [])
        self.assertEqual(self.index.search("，？！"), [])
        self.assertEqual(self.index.search(""), self.quotes)
        self.assertIs(self.index.search("苏轼")[0], self.quotes[0])

    def test_strong_matches_rank_first_without_changing_original_text(self):
        exact = {"quote": "明月", "source": "来源", "quote_id": "exact"}
        index = QuoteSearch(self.quotes + [exact])
        self.assertIs(index.search("明月")[0], exact)
        self.assertEqual(index.search("HELLO")[0]["quote"], "Hello，World！")

    def test_recommendations_exhaust_remaining_before_starting_new_cycle(self):
        sampler = CandidateSampler(17)
        first = sampler.recommend(self.quotes, 2)
        last = sampler.recommend(self.quotes, 5)
        self.assertEqual(len(first), 2)
        self.assertEqual(len(last), 1)
        self.assertFalse(sampler.restarted)
        self.assertEqual({item["quote_id"] for item in first + last}, {"first", "second", "third"})
        self.assertEqual(len(sampler.recommend(self.quotes, 5)), 3)
        self.assertTrue(sampler.restarted)
        self.assertEqual(sampler.recommend([], 5), [])
        self.assertFalse(sampler.restarted)

    def test_search_scope_never_recommends_unmatched_records_or_pads(self):
        sampler = CandidateSampler(9)
        result = sampler.recommend(self.index.search("苏轼 明月"), 5)
        self.assertEqual(result, self.quotes[:1])
        self.assertEqual(sampler.recommend(self.index.search("找不到"), 5), [])


if __name__ == "__main__":
    unittest.main()
