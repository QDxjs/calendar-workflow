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
class QuoteImportIssue:
    location: str
    reason: str
    quote: str = ""
    source: str = ""
    duplicate_of: str | None = None


@dataclass(frozen=True)
class QuoteImportPreview:
    quotes: list[dict[str, str]]
    total_count: int
    duplicate_count: int
    invalid_count: int
    issues: tuple[QuoteImportIssue, ...] = ()
    accepted_locations: tuple[str, ...] = ()


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
    records = ((f"第 {index} 条", entry) for index, entry in enumerate(entries, start=1))
    return _inspect_entries(records).quotes


def normalize_quote_key(value: str) -> str:
    return re.sub(r"[\W_]+", "", value, flags=re.UNICODE)


def load_quotes(path: Path) -> list[dict[str, str]]:
    """Load an attributed JSON array, one JSON object per line, or one JSON object."""
    return inspect_quotes(path).quotes


def inspect_quotes(path: Path, *, allow_empty: bool = False) -> QuoteImportPreview:
    """Validate an import and summarize accepted, duplicate, and rejected entries."""
    if not path.exists():
        raise FileNotFoundError(f"找不到本地语录库：{path}")

    raw = path.read_text(encoding="utf-8-sig")
    stripped = raw.lstrip()
    if path.suffix.lower() == ".jsonl":
        return _inspect_entries(_jsonl_records(raw), allow_empty=allow_empty)

    if stripped:
        try:
            document = json.loads(raw)
        except json.JSONDecodeError as exc:
            if not stripped.startswith("{") or exc.msg != "Extra data":
                raise ValueError(
                    f"语录库 JSON 在第 {exc.lineno} 行第 {exc.colno} 列格式错误。"
                ) from exc
        else:
            if isinstance(document, dict):
                records = (("第 1 条", document),)
            elif isinstance(document, list):
                records = ((f"第 {index} 条", entry) for index, entry in enumerate(document, start=1))
            else:
                raise ValueError("语录库 JSON 顶层必须是对象或数组。")
            return _inspect_entries(records, allow_empty=allow_empty)

    # Preserve the historical fallback for newline-delimited objects even when
    # the caller gave the file a .json or extensionless name.
    if stripped:
        return _inspect_entries(_jsonl_records(raw), allow_empty=allow_empty)
    return _inspect_entries((), allow_empty=allow_empty)


def _jsonl_records(raw: str) -> Iterable[tuple[str, object]]:
    for line_number, raw_line in enumerate(raw.split("\n"), start=1):
        if not raw_line.strip():
            continue
        try:
            entry = json.loads(raw_line)
        except json.JSONDecodeError as exc:
            error_line = line_number + exc.lineno - 1
            raise ValueError(
                f"语录库第 {error_line} 行第 {exc.colno} 列 JSON 格式错误。"
            ) from exc
        yield f"第 {line_number} 行", entry


def _inspect_entries(
    records: Iterable[tuple[str, object]], *, allow_empty: bool = False,
) -> QuoteImportPreview:
    quotes: list[dict[str, str]] = []
    accepted_locations: list[str] = []
    seen: dict[str, str] = {}
    issues: list[QuoteImportIssue] = []
    duplicate_count = 0
    invalid_count = 0
    total_count = 0
    for location, entry in records:
        total_count += 1
        if not isinstance(entry, dict):
            invalid_count += 1
            issues.append(QuoteImportIssue(location, "记录不是 JSON 对象"))
            continue

        raw_quote = entry.get("name")
        raw_attribution = entry.get("from")
        quote_detail = raw_quote if isinstance(raw_quote, str) else ""
        source_detail = raw_attribution if isinstance(raw_attribution, str) else ""
        field_errors = []
        for field, raw_value in (("name", raw_quote), ("from", raw_attribution)):
            if field not in entry:
                field_errors.append(f"缺少 {field} 字段")
            elif not isinstance(raw_value, str):
                field_errors.append(f"{field} 必须是字符串")
        if field_errors:
            invalid_count += 1
            issues.append(QuoteImportIssue(
                location, "；".join(field_errors), quote_detail, source_detail,
            ))
            continue

        quote = raw_quote.strip()
        attribution = raw_attribution.strip()
        validation_errors = []
        if not MIN_QUOTE_LENGTH <= len(quote) <= MAX_QUOTE_LENGTH:
            validation_errors.append(
                f"去除首尾空白后正文长度为 {len(quote)} 个字符，须为 {MIN_QUOTE_LENGTH}～{MAX_QUOTE_LENGTH} 个字符"
            )
        if not attribution:
            validation_errors.append("出处为空（去除首尾空白后）")
        quote_key = normalize_quote_key(quote)
        if not quote_key and MIN_QUOTE_LENGTH <= len(quote) <= MAX_QUOTE_LENGTH:
            validation_errors.append("正文规范化后为空（仅含标点、空白或其他被忽略符号）")
        if validation_errors:
            invalid_count += 1
            issues.append(QuoteImportIssue(
                location, "；".join(validation_errors), quote_detail, source_detail,
            ))
            continue
        if quote_key in seen:
            duplicate_count += 1
            first_location = seen[quote_key]
            issues.append(QuoteImportIssue(
                location,
                f"重复：归一化会忽略标点和空白等符号，与 {first_location} 的正文相同",
                quote_detail,
                source_detail,
                duplicate_of=first_location,
            ))
            continue
        seen[quote_key] = location

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
        accepted_locations.append(location)

    if not quotes and not allow_empty:
        raise ValueError("语录库中没有找到带出处、长度适合排版的语录。")
    return QuoteImportPreview(
        quotes=quotes,
        total_count=total_count,
        duplicate_count=duplicate_count,
        invalid_count=invalid_count,
        issues=tuple(issues),
        accepted_locations=tuple(accepted_locations),
    )
