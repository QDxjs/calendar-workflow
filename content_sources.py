"""Qt-free single-day content validation and deterministic layout planning."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from dataclasses import dataclass
from datetime import date
import random

from calendar_models import CalendarPage, GenerationPlan
from page_validation import INVALID_XML_TEXT
from quote_library import normalize_quote_key


class ManualQuoteError(ValueError):
    def __init__(self, field: str, message: str) -> None:
        super().__init__(message)
        self.field = field


@dataclass(frozen=True)
class ManualQuoteSource:
    quote: str
    source: str = ""


def validate_manual_source(content: ManualQuoteSource) -> ManualQuoteSource:
    """Strip only outer whitespace; keep internal line breaks and attribution."""
    normalized = ManualQuoteSource(content.quote.strip(), content.source.strip())
    for field, label, value in (("quote", "正文", content.quote),
                                ("source", "出处", content.source)):
        invalid = INVALID_XML_TEXT.search(value)
        if invalid is not None:
            raise ManualQuoteError(field, f"{label}含 SVG 不支持的字符 U+{ord(invalid.group()):04X}，请删除后重试。")
    if normalized.quote and not normalize_quote_key(normalized.quote):
        raise ManualQuoteError("quote", "正文不能只有标点；请输入有效文字，或留空生成留白日历。")
    return normalized


def plan_manual_page(
    target_date: date, content: ManualQuoteSource, layout_selection: str,
    seed: int | None = None, *,
    renderers: Mapping[str, Callable[[dict[str, object]], str]] | None = None,
) -> GenerationPlan:
    """Try SVGs in memory, then choose only among layouts that actually fit."""
    from generate import RENDERERS, metadata
    from page_validation import validate_pages
    from svg_validation import validate_rendering

    content = validate_manual_source(content)
    renderers = RENDERERS if renderers is None else renderers
    if layout_selection != "RANDOM" and layout_selection not in renderers:
        raise ManualQuoteError("quote", "版式应为 A–I 或 RANDOM。")
    candidates = sorted(renderers) if layout_selection == "RANDOM" else [layout_selection]
    selection = "random" if layout_selection == "RANDOM" else layout_selection
    eligible = []
    last_error = ""
    for layout in candidates:
        page = CalendarPage(target_date, selection, layout, content.quote, content.source, "")
        try:
            validate_rendering([page], renderers=renderers, metadata=metadata,
                               validate_pages=lambda pages: validate_pages(pages, renderers=renderers))
        except ValueError as exc:
            last_error = str(exc)
        else:
            eligible.append(page)
    if not eligible:
        message = ("当前正文或出处超出全部版式上限，请适当精简或调整换行。"
                   if layout_selection == "RANDOM" else
                   f"当前正文或出处无法排入版式 {layout_selection}，请精简文字、调整换行或改用随机版式。")
        raise ManualQuoteError("quote", f"{message}\n{last_error}")
    page = random.Random(seed).choice(eligible)
    return GenerationPlan((page,), seed)
