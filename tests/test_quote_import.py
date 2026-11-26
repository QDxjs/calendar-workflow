"""Regression tests for quote import validation and diagnostics."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
import tempfile
import unittest

from quote_library import (
    MAX_QUOTE_LENGTH,
    MIN_QUOTE_LENGTH,
    QuoteImportPreview,
    builtin_quotes,
    inspect_quotes,
    load_quotes,
)


class QuoteImportTests(unittest.TestCase):
    def setUp(self) -> None:
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)

    def write_json(self, name: str, value: object) -> Path:
        path = self.root / name
        path.write_text(json.dumps(value, ensure_ascii=False), encoding="utf-8")
        return path

    def test_length_boundaries_and_strip_behavior_are_preserved(self) -> None:
        path = self.write_json("quotes.json", [
            {"name": "  abcd  ", "from": " source "},
            {"name": "x" * MAX_QUOTE_LENGTH, "from": "source"},
            {"name": "abc", "from": "source"},
            {"name": "x" * (MAX_QUOTE_LENGTH + 1), "from": "source"},
        ])

        preview = inspect_quotes(path, allow_empty=True)

        self.assertEqual(MIN_QUOTE_LENGTH, 4)
        self.assertEqual(MAX_QUOTE_LENGTH, 58)
        self.assertEqual([len(item["quote"]) for item in preview.quotes], [4, 58])
        self.assertEqual([item["source"] for item in preview.quotes], ["source", "source"])
        self.assertEqual(preview.accepted_locations, ("第 1 条", "第 2 条"))
        self.assertEqual(preview.invalid_count, 2)
        self.assertIn("长度为 3", preview.issues[0].reason)
        self.assertIn("长度为 59", preview.issues[1].reason)
        self.assertEqual(preview.issues[0].quote, "abc")

    def test_empty_attribution_and_invalid_fields_have_specific_safe_details(self) -> None:
        path = self.write_json("fields.json", [
            {"name": "abcd", "from": "   "},
            {"name": ["a", {"large": "value"}], "from": {"nested": [1, 2]}},
            {"name": "abcd", "from": None},
            {"from": "kept source"},
            {"name": "kept quote"},
            42,
        ])

        preview = inspect_quotes(path, allow_empty=True)

        self.assertEqual(preview.invalid_count, 6)
        self.assertIn("出处为空", preview.issues[0].reason)
        self.assertEqual(preview.issues[0].source, "   ")
        self.assertIn("name", preview.issues[1].reason)
        self.assertIn("from", preview.issues[1].reason)
        self.assertEqual((preview.issues[1].quote, preview.issues[1].source), ("", ""))
        self.assertIn("from", preview.issues[2].reason)
        self.assertEqual(preview.issues[2].quote, "abcd")
        self.assertIn("缺少 name", preview.issues[3].reason)
        self.assertEqual(preview.issues[3].source, "kept source")
        self.assertIn("缺少 from", preview.issues[4].reason)
        self.assertEqual(preview.issues[4].quote, "kept quote")
        self.assertEqual(preview.issues[5].reason, "记录不是 JSON 对象")

    def test_array_object_and_jsonl_locations_match_source_positions(self) -> None:
        array_path = self.write_json("array.json", [
            {"name": "first quote", "from": "book"},
            "not an object",
            {"name": "third quote", "from": "book"},
        ])
        array_preview = inspect_quotes(array_path, allow_empty=True)
        self.assertEqual(array_preview.accepted_locations, ("第 1 条", "第 3 条"))
        self.assertEqual(array_preview.issues[0].location, "第 2 条")

        object_path = self.write_json("object.json", {"name": "single quote", "from": "book"})
        object_preview = inspect_quotes(object_path)
        self.assertEqual(object_preview.accepted_locations, ("第 1 条",))

        jsonl_path = self.root / "lines.jsonl"
        jsonl_path.write_text(
            '\n{"name":"line two","from":"book"}\n\n'
            '{"name":3,"from":"book"}\n{"name":"line five","from":"book"}\n',
            encoding="utf-8",
        )
        jsonl_preview = inspect_quotes(jsonl_path, allow_empty=True)
        self.assertEqual(jsonl_preview.total_count, 3)
        self.assertEqual(jsonl_preview.accepted_locations, ("第 2 行", "第 5 行"))
        self.assertEqual(jsonl_preview.issues[0].location, "第 4 行")

    def test_extensionless_consecutive_object_fallback_keeps_physical_lines(self) -> None:
        path = self.root / "quotes"
        path.write_text(
            '\n{"name":"first quote","from":"book"}\n\n'
            '{"name":"second quote","from":"book"}\n',
            encoding="utf-8",
        )

        preview = inspect_quotes(path)

        self.assertEqual(preview.total_count, 2)
        self.assertEqual(preview.accepted_locations, ("第 2 行", "第 4 行"))

    def test_duplicate_issue_points_to_first_accepted_record(self) -> None:
        path = self.write_json("duplicates.json", [
            {"name": "雨后，记得开窗", "from": "book"},
            {"name": "雨后 记得开窗！", "from": "other book"},
        ])

        preview = inspect_quotes(path)

        self.assertEqual(len(preview.quotes), 1)
        self.assertEqual(preview.accepted_locations, ("第 1 条",))
        self.assertEqual(preview.duplicate_count, 1)
        duplicate = preview.issues[0]
        self.assertEqual(duplicate.location, "第 2 条")
        self.assertEqual(duplicate.duplicate_of, "第 1 条")
        self.assertIn("归一化", duplicate.reason)
        self.assertIn("标点", duplicate.reason)
        self.assertIn("空白", duplicate.reason)

    def test_all_invalid_and_empty_inputs_are_inspectable_but_strict_calls_fail(self) -> None:
        invalid_path = self.write_json("invalid.json", [
            {"name": "abc", "from": "book"},
            {"name": "abcd", "from": "  "},
        ])

        preview = inspect_quotes(invalid_path, allow_empty=True)
        self.assertEqual(preview.quotes, [])
        self.assertEqual(preview.total_count, 2)
        self.assertEqual(preview.invalid_count, 2)
        self.assertEqual(len(preview.issues), 2)
        self.assertEqual(preview.accepted_locations, ())
        with self.assertRaises(ValueError):
            inspect_quotes(invalid_path)
        with self.assertRaises(ValueError):
            load_quotes(invalid_path)

        empty_path = self.root / "empty.json"
        empty_path.write_bytes(b"")
        empty_preview = inspect_quotes(empty_path, allow_empty=True)
        self.assertEqual(
            (empty_preview.quotes, empty_preview.total_count, empty_preview.duplicate_count,
             empty_preview.invalid_count, empty_preview.issues, empty_preview.accepted_locations),
            ([], 0, 0, 0, (), ()),
        )
        with self.assertRaises(ValueError):
            inspect_quotes(empty_path)

        legacy_preview = QuoteImportPreview([], 0, 0, 0)
        self.assertEqual((legacy_preview.issues, legacy_preview.accepted_locations), ((), ()))

    def test_bom_is_supported_and_inspection_does_not_change_source_bytes(self) -> None:
        path = self.root / "bom.json"
        original = b'\xef\xbb\xbf{"name":"bom quote","from":"book"}'
        path.write_bytes(original)

        preview = inspect_quotes(path)

        self.assertEqual(preview.quotes[0]["quote"], "bom quote")
        self.assertEqual(path.read_bytes(), original)

    def test_json_and_jsonl_syntax_errors_include_line_and_column(self) -> None:
        json_path = self.root / "broken.json"
        json_path.write_text('{"name": }', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, r"第 1 行第 \d+ 列"):
            inspect_quotes(json_path, allow_empty=True)

        jsonl_path = self.root / "broken.jsonl"
        jsonl_path.write_text('\n{"name":"valid","from":"book"}\n{"name": }', encoding="utf-8")
        with self.assertRaisesRegex(ValueError, r"第 3 行第 \d+ 列"):
            inspect_quotes(jsonl_path, allow_empty=True)

    def test_raw_id_compatibility_and_builtin_corpus_metadata_are_unchanged(self) -> None:
        path = self.write_json("ids.json", [
            {"name": "string id", "from": "book", "_id": "text"},
            {"name": "object id", "from": "book", "_id": {"$oid": "wrapped"}},
            {"name": "integer id", "from": "book", "_id": 7},
            {"name": "invalid id", "from": "book", "_id": [1, 2]},
        ])
        self.assertEqual([item["quote_id"] for item in inspect_quotes(path).quotes], [
            "text", "wrapped", "7", "",
        ])

        quotes = builtin_quotes()
        payload = json.dumps(quotes, ensure_ascii=False, separators=(",", ":"), sort_keys=True).encode("utf-8")
        self.assertEqual(len(quotes), 2399)
        self.assertTrue(all(set(item) == {"quote", "source", "quote_id"} for item in quotes))
        self.assertEqual(
            hashlib.sha256(payload).hexdigest(),
            "c32ab6a58d772fb1245e6c346ae59befcac6903674a182966cd79514531adc84",
        )


if __name__ == "__main__":
    unittest.main()
