"""SVG renderer for the I calendar layout."""

from __future__ import annotations

from datetime import date

from svg_primitives import (
    INK, LATIN, MID, PALE, PAPER, SANS, footer_brand, line, quote_block, rect, svg_open, text,
)


def render_i(m: dict[str, object]) -> str:
    """Render the two-tone circle layout with counts in a side rail."""
    d = m["date"]
    assert isinstance(d, date)
    p = svg_open(f'{d.isoformat()} — I / Two Tone Calendar')
    p += [rect(42, 42, 1038, 1318, "none", INK, 1.0),
          text(98, 100, m["weekday"], 28, anchor="start", family=SANS, weight="bold"),
          text(98, 145, f'{d.year} 年 {d.month} 月 {d.day} 日', 17,
               anchor="start", spacing=0.7),
          text(1024, 100, "DAILY CALENDAR", 10, anchor="end", family=SANS, spacing=1.0),
          line(64, 178, 1058, 178, 0.8),
          text(116, 278, "ISO WEEK", 10, anchor="start", family=SANS, spacing=1.0),
          text(116, 348, f'{m["week"]:02d}', 46, anchor="start", family=LATIN),
          text(116, 382, m["week_label"], 12, anchor="start", family=LATIN),
          line(116, 410, 322, 410, 0.8, MID),
          text(116, 466, "DAY OF YEAR", 10, anchor="start", family=SANS, spacing=0.9),
          text(116, 520, f'{m["ordinal"]:03d} / {m["year_days"]}', 20,
               anchor="start", family=LATIN),
          text(116, 558, f'CALENDAR / {d.year}', 9, anchor="start", family=SANS,
               spacing=0.5),
          f'<circle cx="758" cy="438" r="278" fill="{PALE}" stroke="{INK}" stroke-width="0.9"/>',
          f'<path d="M758 160 A278 278 0 0 1 758 716 Z" fill="{INK}"/>',
          f'<circle cx="758" cy="438" r="248" fill="none" stroke="{MID}" stroke-width="0.8"/>',
          text(850, 430, f'{m["day"]:02d}', 146, family=LATIN, fill=PAPER),
          text(850, 482, m["month"], 15, family=LATIN, fill=PAPER, spacing=1.3),
          text(850, 520, f'{d.year}', 12, family=SANS, fill=PAPER, spacing=0.8),
          line(64, 756, 1058, 756, 1.0),
          rect(64, 790, 994, 402, PALE, "none", 0),
          text(98, 838, "TODAY'S QUOTE", 10, anchor="start", family=SANS, spacing=1.0)]
    p.append(quote_block(str(m["quote"]), str(m["source"]), x=561, y=978,
                         width=850, max_height=360, font_size=44, max_lines=4,
                         rule_color=MID, top=868, bottom=1166))
    p += [line(84, 1222, 1038, 1222, 0.8, MID),
          footer_brand(561, 1298 if m.get("creator") else 1310, str(m.get("creator", "")),
                       brand_size=13, brand_spacing=0, max_width=780,
                       creator_y=1326, creator_size=11.5, creator_max_width=780),
          "</svg>"]
    return "\n".join(p)
