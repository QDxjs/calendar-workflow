"""SVG renderer for the G calendar layout."""

from __future__ import annotations

from datetime import date

from svg_primitives import (
    BRAND, INK, LATIN, MID, PALE, PAPER, SANS, line, quote_block, rect, svg_open, text,
)


def render_g(m: dict[str, object]) -> str:
    """Render the geometric split layout with a strong date field."""
    d = m["date"]
    assert isinstance(d, date)
    p = svg_open(f'{d.isoformat()} — G / Geometric Split')
    p += [rect(42, 42, 1038, 1318, "none", INK, 1.0),
          text(78, 84, "DAILY CALENDAR", 10, anchor="start", family=SANS, spacing=1.3),
          text(1044, 84, f'{d.year} / {m["week_label"]}', 11, anchor="end", family=LATIN),
          line(42, 106, 1080, 106, 0.8),
          text(561, 150, m["weekday"], 30, family=SANS, weight="bold"),
          text(561, 190, f'{d.year} 年 {d.month} 月 {d.day} 日', 17, spacing=1.0),
          f'<path d="M42 224 H708 L630 704 H42 Z" fill="{INK}"/>',
          f'<path d="M708 224 H1080 V704 H630 Z" fill="{PALE}"/>',
          f'<path d="M42 224 H90 V272 H42 Z" fill="{MID}"/>',
          text(104, 302, "MONTH", 10, anchor="start", family=SANS, fill=PAPER, spacing=1.1),
          text(104, 378, m["month"], 50, anchor="start", family=LATIN,
               fill=PAPER, spacing=1.1, max_width=540),
          line(104, 407, 592, 407, 0.8, MID),
          text(102, 652, f'{m["day"]:02d}', 260, anchor="start", family=LATIN, fill=PAPER),
          text(758, 290, "ISO WEEK", 10, anchor="start", family=SANS, spacing=1.0),
          text(758, 382, f'{m["week"]:02d}', 52, anchor="start", family=LATIN),
          text(758, 417, m["week_label"], 13, anchor="start", family=LATIN),
          line(758, 442, 1038, 442, 0.8, MID),
          text(758, 492, "DAY OF YEAR", 10, anchor="start", family=SANS, spacing=0.9),
          text(758, 548, f'{m["ordinal"]:03d} / {m["year_days"]}', 23,
               anchor="start", family=LATIN),
          line(758, 570, 1038, 570, 0.8, MID),
          text(758, 620, "CALENDAR YEAR", 9, anchor="start", family=SANS, spacing=0.7),
          text(758, 668, f'{d.year}', 23, anchor="start", family=LATIN),
          rect(62, 744, 998, 444, "none", INK, 0.9),
          rect(62, 744, 122, 444, INK, "none", 0),
          text(123, 820, "“", 74, family=LATIN, fill=PAPER),
          text(123, 898, "QUOTE", 9, family=SANS, fill=PAPER, spacing=0.8),
          text(210, 794, "TODAY'S LINE", 10, anchor="start", family=SANS, spacing=1.0),
          line(210, 812, 1038, 812, 0.8, MID)]
    p.append(quote_block(str(m["quote"]), str(m["source"]), x=624, y=970,
                         width=780, max_height=380, font_size=44, max_lines=4,
                         rule_color=MID))
    p += [line(76, 1262, 1046, 1262, 0.8, MID),
          text(561, 1310, BRAND, 13, family=LATIN, italic=True), "</svg>"]
    return "\n".join(p)
