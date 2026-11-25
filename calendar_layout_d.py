"""SVG renderer for the D calendar layout."""

from __future__ import annotations

from datetime import date

from svg_primitives import (
    BRAND, CLAY, INK, LATIN, PALE, SANS, line, quote_block, rect, svg_open, text,
)


def render_d(m: dict[str, object]) -> str:
    """Render the two-tone circle motif with date-and-quote hierarchy."""
    d = m["date"]
    assert isinstance(d, date)
    p = svg_open(f'{d.isoformat()} literary calendar — D split circle')
    p += [
        text(58, 74, "CIRCLE / DATE STUDY", 12, anchor="start", family=SANS,
             spacing=1.7, max_width=160),
        line(58, 100, 108, 100, 1.5, CLAY), line(226, 34, 226, 343, 1.2),
        f'<circle cx="696" cy="115" r="235" fill="{PALE}"/>',
        f'<path d="M696 -120 A235 235 0 0 1 696 350 Z" fill="{INK}"/>',
        text(970, 74, "CALENDAR", 12, anchor="start", family=SANS,
             spacing=1.6, max_width=140),
        text(970, 101, str(d.year), 12, anchor="start", family=SANS,
             spacing=1.7, max_width=140),
        text(970, 128, "READING / 01", 11, anchor="start", family=SANS,
             spacing=1.1, max_width=140),
        line(970, 151, 1006, 151, 1.1, CLAY),
        text(970, 188, "DATE", 11.5, anchor="start", family=SANS,
             spacing=1.7, max_width=140),
        text(970, 215, f'{d.month:02d} / {d.day:02d}', 13,
             anchor="start", family=SANS, spacing=0.8, max_width=140),
        text(560, 505, m["month"], 108, family=LATIN, spacing=3, max_width=850),
        line(176, 552, 176, 837, 1.2), line(946, 552, 946, 837, 1.2),
        text(61, 614, "DAY OF YEAR", 11, anchor="start", family=SANS,
             spacing=0.6, max_width=100),
        line(61, 650, 96, 650, 1.1, CLAY),
        text(61, 692, f'{m["ordinal"]:03d}', 15, anchor="start", family=LATIN,
             max_width=100),
        text(61, 719, f'OF {m["year_days"]}', 11, anchor="start", family=SANS,
             spacing=0.5, max_width=100),
        text(586, 800, f'{m["day"]:02d}', 350, family=LATIN),
        text(970, 614, m["weekday"], 18, anchor="start", family=SANS,
             weight="bold", max_width=130),
        line(970, 650, 1062, 650, 1.1),
        text(970, 692, f'ISO {m["week_label"]}', 13,
             anchor="start", family=SANS, max_width=130),
        text(970, 728, "SOURCE / BOOK", 11, anchor="start", family=SANS,
             spacing=0.6, max_width=130),
        line(54, 837, 1068, 837, 1.1),
        rect(55, 860, 1012, 350, PALE, PALE, 0),
        text(560, 907, "READING / 001", 11.5, family=SANS,
             spacing=1.7, max_width=500),
    ]
    p.append(quote_block(str(m["quote"]), str(m["source"]), x=560, y=1054,
                         width=870, max_height=230, font_size=42, max_lines=4,
                         rule_color=CLAY))
    p += [line(54, 1275, 1068, 1275, 1.1),
          text(560, 1324, BRAND, 17, family=LATIN, italic=True,
               spacing=1.0, max_width=760), "</svg>"]
    return "\n".join(p)
