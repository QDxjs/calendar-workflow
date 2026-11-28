"""SVG renderer for the F calendar layout."""

from __future__ import annotations

from datetime import date

from svg_primitives import INK, LATIN, MID, SANS, footer_brand, line, quote_block, rect, svg_open, text


def render_f(m: dict[str, object]) -> str:
    """Render a balanced grid for date, weekday, ISO week, and year day."""
    d = m["date"]
    assert isinstance(d, date)
    p = svg_open(f'{d.isoformat()} — F / Balanced Grid')
    p += [rect(42, 42, 1038, 1318, "none", INK, 1.1),
          rect(58, 58, 1006, 150, "none", INK, 0.9),
          line(258, 58, 258, 208, 0.8), line(864, 58, 864, 208, 0.8),
          text(158, 100, "DAILY EDITION", 10, family=SANS, spacing=1.2),
          text(158, 160, f'{m["ordinal"]:03d}', 34, family=LATIN),
          text(561, 110, m["weekday"], 32, family=SANS, weight="bold"),
          line(350, 128, 772, 128, 0.8, MID),
          text(561, 170, f'{d.year} 年 {d.month} 月 {d.day} 日', 18, spacing=1.0),
          text(964, 100, "DAY OF YEAR", 9.5, family=SANS, spacing=0.9),
          text(964, 158, f'{m["ordinal"]:03d} / {m["year_days"]}', 19, family=LATIN),
          rect(58, 230, 1006, 468, "none", INK, 0.9),
          line(258, 230, 258, 698, 0.8), line(864, 230, 864, 698, 0.8),
          text(158, 280, "ISO WEEK", 10, family=SANS, spacing=1.0),
          text(158, 376, f'{m["week"]:02d}', 52, family=LATIN),
          line(92, 400, 224, 400, 0.8),
          text(158, 440, m["week_label"], 13, family=LATIN),
          text(158, 498, "WEEK / YEAR", 9, family=SANS, spacing=0.8),
          text(158, 555, "CALENDAR", 9, family=SANS, spacing=0.8),
          text(158, 592, f'{d.year}', 17, family=LATIN),
          text(561, 500, f'{m["day"]:02d}', 258, family=LATIN),
          line(290, 532, 832, 532, 0.8, MID),
          text(561, 602, m["month"], 42, family=LATIN, spacing=1.8),
          line(320, 626, 802, 626, 0.8, MID),
          text(561, 670, "MONTH  /  DAY", 10, family=SANS, spacing=1.0),
          text(964, 280, "YEAR DAY", 10, family=SANS, spacing=1.0),
          text(964, 376, f'{m["ordinal"]:03d}', 36, family=LATIN),
          text(964, 412, f'OF {m["year_days"]}', 11, family=SANS),
          line(898, 440, 1030, 440, 0.8),
          text(964, 488, "DATE", 9, family=SANS, spacing=0.8),
          text(964, 535, f'{d.month:02d} / {d.day:02d}', 17, family=LATIN),
          text(964, 595, m["weekday"], 12, family=SANS),
          rect(58, 732, 1006, 518, "none", INK, 0.9),
          line(58, 786, 1064, 786, 0.8),
          text(86, 770, "TODAY'S QUOTE", 10, anchor="start", family=SANS, spacing=1.1),
          text(1038, 770, "A LINE TO KEEP", 9, anchor="end", family=SANS,
               spacing=0.7)]
    p.append(quote_block(str(m["quote"]), str(m["source"]), x=561, y=925,
                         width=850, max_height=380, font_size=45, max_lines=4,
                         rule_color=MID, top=810, bottom=1224))
    p += [line(76, 1284, 1046, 1284, 0.8, MID),
          footer_brand(561, 1314 if m.get("creator") else 1322, str(m.get("creator", "")),
                       brand_size=13, brand_spacing=0, max_width=780,
                       creator_y=1338, creator_size=11.5, creator_max_width=780),
          "</svg>"]
    return "\n".join(p)
