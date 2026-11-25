from __future__ import annotations

import json
import re
import sys
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path


RESOURCE_ROOT = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parent))
QUOTE_DIRECTORY = RESOURCE_ROOT / "data" / "hitokoto"
QUOTE_CATEGORIES = ("b", "d", "h", "k")
GENERIC_SOURCE_LABELS = frozenset({"名人名言", "网络", "佚名", "某电视剧"})
MIN_QUOTE_LENGTH = 4
MAX_QUOTE_LENGTH = 58


@dataclass(frozen=True)
class QuoteImportPreview:
    quotes: list[dict[str, str]]
    total_count: int
    duplicate_count: int
    invalid_count: int


def display_attribution(source: str, attributed_person: str | None) -> str:
    source = source.strip() if isinstance(source, str) else ""
    attributed_person = attributed_person.strip() if isinstance(attributed_person, str) else ""
    source = re.sub(r"[，,；;]\s*[^，,；;]*出版社\s*$", "", source).strip()
    parts = []
    if source and source not in GENERIC_SOURCE_LABELS:
        work_title = source if source.startswith("《") and source.endswith("》") else f"《{source}》"
        parts.append(work_title)
    if attributed_person and attributed_person not in GENERIC_SOURCE_LABELS and attributed_person != source:
        parts.append(attributed_person)
    return " · ".join(parts)


def builtin_quotes() -> list[dict[str, str]]:
    """Load the pinned offline Hitokoto categories used by the calendar."""
    entries: list[dict[str, str]] = []
    for category in QUOTE_CATEGORIES:
        path = QUOTE_DIRECTORY / f"{category}.json"
        if not path.is_file():
            raise FileNotFoundError(f"找不到内置一言语料：{path}")
        document = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(document, list):
            raise ValueError(f"一言分类文件必须是 JSON 数组：{path}")
        for record in document:
            if not isinstance(record, dict) or record.get("type") != category:
                continue
            quote = record.get("hitokoto")
            source = record.get("from")
            author = record.get("from_who")
            uuid = record.get("uuid")
            if not all(isinstance(value, str) for value in (quote, source, uuid)) or not source.strip() or not uuid.strip():
                continue
            attribution = display_attribution(source, author)
            if not attribution:
                continue
            entries.append({
                "name": quote,
                "from": attribution,
                "_id": uuid,
            })
    return _inspect_entries(entries).quotes


def normalize_quote_key(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE)


def load_quotes(path: Path) -> list[dict[str, str]]:
    """Load an attributed JSON array, one JSON object per line, or one JSON object."""
    return inspect_quotes(path).quotes


def inspect_quotes(path: Path) -> QuoteImportPreview:
    """Validate an import and summarize accepted, duplicate, and rejected entries."""
    if not path.exists():
        raise FileNotFoundError(f"找不到本地语录库：{path}")

    raw = path.read_text(encoding="utf-8-sig")
    stripped = raw.lstrip()
    if path.suffix.lower() != ".jsonl" and stripped:
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            if not stripped.startswith("{") or exc.msg != "Extra data":
                raise ValueError(f"语录库 JSON 在第 {exc.lineno} 行第 {exc.colno} 列格式错误。") from exc
        else:
            if isinstance(document, dict):
                entries: Iterable[object] = (document,)
            elif isinstance(document, list):
                entries = document
            else:
                raise ValueError("语录库 JSON 顶层必须是对象或数组。")
            return _inspect_entries(entries)

    entries = []
    for line_number, raw_line in enumerate(raw.split("\n"), start=1):
        if not raw_line.strip():
            continue
        try:
            entries.append(json.loads(raw_line))
        except json.JSONDecodeError as exc:
            raise ValueError(f"语录库第 {line_number} 行不是有效 JSON。") from exc
    return _inspect_entries(entries)


def _inspect_entries(entries: Iterable[object]) -> QuoteImportPreview:
    quotes: list[dict[str, str]] = []
    seen: set[str] = set()
    duplicate_count = 0
    invalid_count = 0
    for entry in entries:
        if not isinstance(entry, dict):
            invalid_count += 1
            continue

        raw_quote = entry.get("name")
        raw_attribution = entry.get("from")
        if not isinstance(raw_quote, str) or not isinstance(raw_attribution, str):
            invalid_count += 1
            continue
        quote = raw_quote.strip()
        attribution = raw_attribution.strip()
        if not attribution or not MIN_QUOTE_LENGTH <= len(quote) <= MAX_QUOTE_LENGTH:
            invalid_count += 1
            continue
        quote_key = normalize_quote_key(quote)
        if not quote_key:
            invalid_count += 1
            continue
        if quote_key in seen:
            duplicate_count += 1
            continue
        seen.add(quote_key)

        raw_id = entry.get("_id", "")
        if isinstance(raw_id, dict):
            raw_id = raw_id.get("$oid", "")
        if not isinstance(raw_id, (str, int)):
            raw_id = ""
        quotes.append({
            "quote": quote,
            "source": attribution,
            "quote_id": str(raw_id),
        })

    if not quotes:
        raise ValueError("语录库中没有找到带出处、长度适合排版的语录。")
    return QuoteImportPreview(
        quotes=quotes,
        total_count=len(quotes) + duplicate_count + invalid_count,
        duplicate_count=duplicate_count,
        invalid_count=invalid_count,
    )
