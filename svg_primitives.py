"""Shared SVG geometry, typography, and calendar metadata primitives."""

from __future__ import annotations

import calendar
import html
import random
import unicodedata
from datetime import date

from calendar_models import WEEKDAYS


W, H = 1122, 1402
PAPER = "#f3f0e8"
INK = "#171716"
MID = "#c9c7c1"
PALE = "#e4e2dc"
CLAY = "#9b6e59"
SERIF = "'FangSong','SimSun',serif"
LATIN = "'Times New Roman',Georgia,serif"
SANS = "'Microsoft YaHei','Noto Sans SC',Arial,sans-serif"
MONTHS = ["JANUARY", "FEBRUARY", "MARCH", "APRIL", "MAY", "JUNE",
          "JULY", "AUGUST", "SEPTEMBER", "OCTOBER", "NOVEMBER", "DECEMBER"]
BRAND = "Every day has a margin."
QUOTE_PUNCTUATION = set("，。；：、,.!?！？;:)]}）》」』”’…")


def esc(value: object) -> str:
    return html.escape(str(value), quote=True)


def text_width_units(value: str) -> float:
    units = 0.0
    for char in value:
        if unicodedata.east_asian_width(char) in ("F", "W"):
            units += 1.0
        elif char.isspace():
            units += 0.34
        elif char in "MW@#%&":
            units += 0.86
        elif char in "ilI.,:;!'|":
            units += 0.32
        elif char.isupper():
            units += 0.68
        else:
            units += 0.56
    return units


def line(x1: float, y1: float, x2: float, y2: float, width: float = 1.5,
         color: str = INK) -> str:
    return (f'<line x1="{x1}" y1="{y1}" x2="{x2}" y2="{y2}" '
            f'stroke="{color}" stroke-width="{width}"/>')


def rect(x: float, y: float, width: float, height: float, fill: str = "none",
         stroke: str = INK, stroke_width: float = 1.5) -> str:
    return (f'<rect x="{x}" y="{y}" width="{width}" height="{height}" '
            f'fill="{fill}" stroke="{stroke}" stroke-width="{stroke_width}"/>')


def text(x: float, y: float, value: object, size: float = 24, *, anchor: str = "middle",
         fill: str = INK, family: str = SERIF, weight: str = "normal",
         spacing: float = 0, italic: bool = False, max_width: float | None = None) -> str:
    value_text = str(value)
    if max_width:
        estimated = text_width_units(value_text) * size + max(0, len(value_text) - 1) * spacing
        if estimated > max_width:
            scale = max_width / estimated
            size *= scale
            spacing *= scale
    style = f'font-family="{family}" font-size="{size}" font-weight="{weight}"'
    if spacing:
        style += f' letter-spacing="{spacing}"'
    if italic:
        style += ' font-style="italic"'
    return (f'<text x="{x}" y="{y}" text-anchor="{anchor}" fill="{fill}" '
            f'{style}>{esc(value_text)}</text>')


def wrap_text(value: str, max_em: float) -> list[str]:
    """Wrap mostly CJK text by approximate typographic width, preserving paragraphs."""
    output: list[str] = []
    for paragraph in value.replace("\r", "").split("\n"):
        if not paragraph:
            output.append("")
            continue
        tokens: list[str] = []
        for char in paragraph:
            if char in QUOTE_PUNCTUATION and tokens:
                tokens[-1] += char
            else:
                tokens.append(char)
        current: list[str] = []
        used = 0.0
        for token in tokens:
            advance = sum(1.0 if unicodedata.east_asian_width(char) in ("F", "W") else 0.56
                          for char in token)
            if current and used + advance > max_em:
                output.append("".join(current))
                current, used = [], 0.0
            current.append(token)
            used += advance
        if current:
            output.append("".join(current))
    return output or [""]


def balance_quote_lines(lines: list[str], max_em: float) -> list[str]:
    """Avoid a tiny orphan line when a quote wraps into multiple CJK lines."""
    balanced = lines[:]
    max_passes = sum(len(item) for item in balanced)
    for _ in range(max_passes):
        changed = False
        for index in range(len(balanced) - 1):
            first, second = balanced[index], balanced[index + 1]
            if not first or not second:
                continue
            if text_width_units(first) - text_width_units(second) <= 1.0:
                continue
            move_count = 2 if first[-1] in QUOTE_PUNCTUATION and len(first) > 1 else 1
            moved = first[-move_count:]
            if text_width_units(second) + text_width_units(moved) > max_em:
                continue
            balanced[index] = first[:-move_count]
            balanced[index + 1] = moved + second
            changed = True
        if not changed:
            break
    return balanced


def label_block(value: str, *, x: float, y: float, width: float, font_size: float,
                anchor: str = "middle", weight: str = "normal", max_lines: int = 2,
                family: str = SERIF, color: str = INK) -> str:
    """Fit an attribution into a compact one- or two-line label."""
    if not value:
        return ""
    lines = wrap_text(value, width / (font_size * 1.08))
    while len(lines) > max_lines and font_size > 14:
        font_size -= 1
        lines = wrap_text(value, width / (font_size * 1.08))
    gap = font_size * 1.18
    first_y = y - (len(lines) - 1) * gap / 2
    pieces = [f'<text x="{x}" y="{first_y}" text-anchor="{anchor}" fill="{color}" '
              f'font-family="{family}" font-size="{font_size}" font-weight="{weight}">']
    for index, item in enumerate(lines):
        pieces.append(f'<tspan x="{x}" dy="{0 if index == 0 else gap}">{esc(item)}</tspan>')
    pieces.append("</text>")
    return "\n".join(pieces)


def quote_block(value: str, source: str, *, x: float, y: float, width: float,
                max_height: float, font_size: float, color: str = INK,
                line_gap: float = 1.38, max_lines: int | None = None,
                align: str = "middle", source_color: str = INK,
                rule_color: str = MID) -> str:
    max_em = width / (font_size * 1.08)
    lines = balance_quote_lines(wrap_text(value, max_em), max_em)
    while len(lines) * font_size * line_gap > max_height and font_size > 24:
        font_size -= 2
        max_em = width / (font_size * 1.08)
        lines = balance_quote_lines(wrap_text(value, max_em), max_em)
    while max_lines and len(lines) > max_lines and font_size > 18:
        font_size -= 2
        max_em = width / (font_size * 1.08)
        lines = balance_quote_lines(wrap_text(value, max_em), max_em)
    if max_lines and len(lines) > max_lines:
        raise ValueError(f"语录无法在 {max_lines} 行内完整排版；请缩短正文或调整版式参数。")
    gap = font_size * line_gap
    block_height = len(lines) * gap
    first_y = y - block_height / 2 + font_size * 0.82
    anchor = {"start": "start", "middle": "middle", "end": "end"}.get(align, "middle")
    pieces = [f'<text x="{x}" y="{first_y}" text-anchor="{anchor}" fill="{color}" '
              f'font-family="{SERIF}" font-size="{font_size}">']
    for index, item in enumerate(lines):
        dy = 0 if index == 0 else gap
        pieces.append(f'<tspan x="{x}" dy="{dy}">{esc(item)}</tspan>')
    pieces.append("</text>")
    if source:
        source_y = y + min(max_height * 0.43, block_height / 2 + 62)
        if anchor == "start":
            rule_x1, rule_x2 = x, x + 70
        elif anchor == "end":
            rule_x1, rule_x2 = x - 70, x
        else:
            rule_x1, rule_x2 = x - 35, x + 35
        pieces.append(line(rule_x1, source_y - 35, rule_x2, source_y - 35, 1.2, rule_color))
        pieces.append(label_block(source, x=x, y=source_y, width=width * 0.9,
                                  font_size=max(20, font_size * 0.54), anchor=anchor,
                                  color=source_color))
    return "\n".join(pieces)


def common_defs() -> str:
    rng = random.Random(19)
    flecks: list[str] = []
    for index in range(240):
        x, y = rng.uniform(0, 512), rng.uniform(0, 512)
        opacity = rng.uniform(0.025, 0.07)
        if index % 8 == 0:
            width, height = rng.uniform(1.2, 4.5), rng.uniform(0.3, 0.7)
            flecks.append(f'<ellipse cx="{x:.1f}" cy="{y:.1f}" rx="{width:.1f}" '
                          f'ry="{height:.1f}" fill="#756d5e" opacity="{opacity:.3f}"/>')
        else:
            radius = rng.uniform(0.25, 0.85)
            flecks.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="{radius:.2f}" '
                          f'fill="#756d5e" opacity="{opacity:.3f}"/>')
    return f'''<defs>
      <pattern id="paper-grain" width="512" height="512" patternUnits="userSpaceOnUse">
        {''.join(flecks)}
      </pattern>
    </defs>
    <rect width="{W}" height="{H}" fill="{PAPER}"/>
    <rect width="{W}" height="{H}" fill="url(#paper-grain)"/>'''


def svg_open(title: str) -> list[str]:
    return [f'<svg xmlns="http://www.w3.org/2000/svg" width="{W}" height="{H}" viewBox="0 0 {W} {H}">',
            f'<title>{esc(title)}</title>', common_defs()]


def metadata(d: date, layout: str, quote: str, source: str) -> dict[str, object]:
    iso_date = d.isocalendar()
    return {
        "date": d,
        "weekday": WEEKDAYS[d.weekday()],
        "week": iso_date.week,
        "week_year": iso_date.year,
        "week_label": f'{iso_date.year}-W{iso_date.week:02d}',
        "ordinal": d.timetuple().tm_yday,
        "year_days": 366 if calendar.isleap(d.year) else 365,
        "day": d.day,
        "month": MONTHS[d.month - 1],
        "layout": layout,
        "quote": quote,
        "source": source,
    }
