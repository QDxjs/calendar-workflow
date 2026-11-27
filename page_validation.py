"""Validate calendar page data before layout rendering or publication."""

from __future__ import annotations

from collections.abc import Mapping
from datetime import date
import re

from calendar_models import CalendarPage
from quote_library import normalize_quote_key


INVALID_XML_TEXT = re.compile(r"[^\x09\x0a\x0d\x20-\ud7ff\ue000-\ufffd\U00010000-\U0010ffff]")


def validate_pages(pages: list[CalendarPage], *, renderers: Mapping[str, object]) -> None:
    if not pages:
        raise ValueError("没有可生成的日历页。")

    seen_filenames: set[str] = set()
    seen_quotes: dict[str, date] = {}
    for index, page in enumerate(pages, start=1):
        target_date = page.target_date
        layout_selection = page.layout_selection
        layout = page.layout
        quote = page.quote
        if not isinstance(target_date, date):
            raise ValueError(f"第 {index} 页日期无效。")
        if layout not in renderers:
            raise ValueError(f"第 {index} 页版式无效：{layout!r}；应为 A–I。")
        if layout_selection not in (*renderers, "random"):
            raise ValueError(f"第 {index} 页版式选择无效：{layout_selection!r}。")
        for label, value in (("语录正文", quote), ("出处", page.source)):
            invalid = INVALID_XML_TEXT.search(value)
            if invalid is not None:
                raise ValueError(f"第 {index} 页{label}含 SVG 不支持的字符 U+{ord(invalid.group()):04X}。")
        normalized_quote = quote.strip()
        quote_key = normalize_quote_key(normalized_quote)
        if not normalized_quote:
            # Authored blank pages carry no corpus UUID. Keep them replayable
            # without treating an absent quote as duplicate content.
            if page.quote_id.strip():
                raise ValueError(f"第 {index} 页带有语料编号却没有正文，请检查清单。")
        elif not quote_key:
            raise ValueError(f"第 {index} 页语录正文只包含标点。")
        else:
            previous_date = seen_quotes.get(quote_key)
            if previous_date is not None and previous_date != target_date:
                raise ValueError(
                    f"第 {index} 页语录与 {previous_date.isoformat()} 重复；不同日期不能使用相同语录。"
                )
            seen_quotes[quote_key] = target_date
        basename = f"{target_date.isoformat()}_layout-{layout}"
        if basename in seen_filenames:
            raise ValueError(f"第 {index} 页与前面页面的日期和版式相同，文件名会冲突：{basename}")
        seen_filenames.add(basename)
