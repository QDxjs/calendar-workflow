"""Validate generated SVG markup before rendering or delivery."""

from __future__ import annotations

from collections.abc import Callable, Mapping
import xml.etree.ElementTree as ET

from calendar_models import CalendarPage


def validate_rendering(
    pages: list[CalendarPage],
    *,
    renderers: Mapping[str, Callable[[dict[str, object]], str]],
    metadata: Callable[[object, str, str, str], dict[str, object]],
    validate_pages: Callable[[list[CalendarPage]], None],
    exhaustive_random_layouts: bool = False,
    check_cancel: Callable[[], None] | None = None,
) -> None:
    validate_pages(pages)
    for page in pages:
        if check_cancel is not None:
            check_cancel()
        candidate_layouts = (renderers if page.layout_selection == "random" and exhaustive_random_layouts
                             else {page.layout: renderers[page.layout]})
        for candidate_layout, renderer in candidate_layouts.items():
            if check_cancel is not None:
                check_cancel()
            try:
                svg_content = renderer(metadata(page.target_date, candidate_layout, page.quote, page.source))
                if not isinstance(svg_content, str):
                    raise ValueError("模板没有返回 SVG 文本。")
                svg_root = ET.fromstring(svg_content)
                if svg_root.tag.rsplit("}", 1)[-1] != "svg":
                    raise ValueError("模板输出根元素不是 <svg>。")
            except (ET.ParseError, ValueError, RuntimeError) as exc:
                raise ValueError(
                    f"日期 {page.target_date.isoformat()}（版式 {candidate_layout}）排版校验失败：{exc}"
                ) from exc
