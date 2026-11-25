"""SVG renderer for the A calendar layout."""

from __future__ import annotations

from datetime import date

from svg_primitives import (
    BRAND, CLAY, INK, LATIN, SANS, line, quote_block,
    rect, svg_open, text,
)


def render_a(m: dict[str, object]) -> str:
    """Render the modular calendar grid with a framed reading field."""
    d = m["date"]
    assert isinstance(d, date)
    p = svg_open(f'{d.isoformat()} literary calendar — A grid')
    p += [rect(34, 34, 1054, 1334, "none", INK, 2),
          rect(45, 45, 1032, 1312, "none", INK, 0.9)]
    for x, y in ((34, 34), (1076, 34), (34, 1356), (1076, 1356)):
        p.append(f'<rect x="{x}" y="{y}" width="12" height="12" fill="{INK}"/>')
    p += [rect(48, 48, 218, 171), rect(274, 48, 574, 171), rect(856, 48, 218, 171),
          text(157, 94, "READING", 14, spacing=2.0),
          text(157, 121, "INDEX", 14, spacing=2.0),
          text(157, 158, "ENTRY 001", 12, spacing=1.4),
          line(132, 188, 182, 188, 1.4, CLAY),
          text(561, 108, m["weekday"], 42, family=SANS, weight="bold"),
          line(274, 135, 848, 135),
          text(561, 184, f'{d.year} 年 {d.month} 月 {d.day} 日', 23, spacing=1.2),
          text(965, 103, "DATE", 13, spacing=1.8),
          text(965, 132, f'{m["ordinal"]:03d} / {m["year_days"]}', 14, spacing=0.8),
          text(965, 165, f'ISO {m["week_label"]}', 11.5, spacing=0.2),
          rect(48, 237, 1026, 457), rect(48, 237, 203, 457), rect(869, 237, 205, 457),
          line(48, 286, 251, 286), line(869, 286, 1074, 286),
          text(149, 270, "ISO WEEK", 12, spacing=1.2),
          text(971, 270, "YEAR DAY", 12, spacing=1.4),
          text(149, 422, m["week"], 48),
          text(971, 422, f'{m["ordinal"]} / {m["year_days"]}', 29),
          line(76, 505, 223, 505), line(897, 505, 1047, 505),
          text(149, 590, "BOOK", 13, spacing=1.7),
          text(149, 620, "AND PAGE", 13, spacing=1.3),
          text(971, 590, "SOURCE", 13, spacing=1.7),
          text(971, 620, "ON FILE", 13, spacing=1.3),
          text(560, 450, f'{m["day"]:02d}', 248, family=LATIN),
          line(253, 518, 869, 518),
          text(561, 594, m["month"], 58, family=LATIN, spacing=3),
          line(253, 628, 869, 628),
          line(278, 660, 342, 660, 1.2, CLAY),
          text(561, 668, "ENTRY / 001", 13, spacing=1.7, max_width=580),
          line(780, 660, 844, 660, 1.2, CLAY),
          rect(48, 716, 1026, 520), rect(48, 716, 72, 520), rect(1002, 716, 72, 520),
          line(120, 766, 1002, 766),
          text(561, 750, "SELECTED TEXT", 12, spacing=1.2, max_width=800),
          text(84, 944, "READ", 11, family=SANS, spacing=0.6),
          text(84, 974, "MARK", 11, family=SANS, spacing=0.6),
          text(84, 1004, "KEEP", 11, family=SANS, spacing=0.6),
          text(1038, 944, "BOOK", 11, family=SANS, spacing=0.6),
          text(1038, 974, "PAGE", 11, family=SANS, spacing=0.6),
          text(1038, 1004, "LINE", 11, family=SANS, spacing=0.6)]
    p.append(quote_block(str(m["quote"]), str(m["source"]), x=561, y=1004,
                         width=790, max_height=300, font_size=42, max_lines=5,
                         rule_color=CLAY))
    p += [rect(48, 1257, 1026, 96), rect(48, 1257, 160, 96), rect(934, 1257, 140, 96),
          text(128, 1294, "DAY / 001", 11.5, spacing=0.6, max_width=140),
          text(128, 1321, "READING FILE", 11.5, spacing=0.5, max_width=140),
          line(242, 1305, 330, 1305), text(591, 1314, BRAND, 16, family=LATIN,
          italic=True, spacing=0.5, max_width=500),
          line(852, 1305, 914, 1305), text(1004, 1297, "NO. 001", 11.5, spacing=0.3,
          max_width=126), text(1004, 1321, "DAILY INDEX", 11.5, spacing=0.3,
          max_width=126), "</svg>"]
    return "\n".join(p)
