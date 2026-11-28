"""SVG renderer for the H calendar layout."""

from __future__ import annotations

from datetime import date

from svg_primitives import LATIN, MID, PALE, SANS, footer_brand, line, quote_block, rect, svg_open, text


def render_h(m: dict[str, object]) -> str:
    """Render a centered date flanked by week and year-day fields."""
    d = m["date"]
    assert isinstance(d, date)
    p = svg_open(f'{d.isoformat()} — H / Open Calendar')
    p += [line(76, 74, 76, 782, 0.9), line(1046, 74, 1046, 782, 0.9),
          text(561, 112, m["weekday"], 30, family=SANS, weight="bold", spacing=1.4),
          text(561, 156, f'{d.year} 年 {d.month} 月 {d.day} 日', 17, spacing=1.0),
          text(561, 191, f'ISO WEEK  /  {m["week_label"]}', 11,
               family=SANS, spacing=0.8),
          line(455, 218, 667, 218, 0.8, MID),
          text(561, 300, m["month"], 50, family=LATIN, spacing=2.0),
          text(561, 638, f'{m["day"]:02d}', 304, family=LATIN),
          text(128, 475, "ISO WEEK", 9.5, anchor="start", family=SANS, spacing=1.0),
          text(128, 530, f'{m["week"]:02d}', 35, anchor="start", family=LATIN),
          text(128, 560, m["week_label"], 11, anchor="start", family=LATIN),
          line(128, 582, 232, 582, 0.8, MID),
          text(994, 475, "DAY OF YEAR", 9.5, anchor="end", family=SANS, spacing=0.7),
          text(994, 530, f'{m["ordinal"]:03d} / {m["year_days"]}', 18,
               anchor="end", family=LATIN),
          text(994, 561, f'CALENDAR / {d.year}', 9, anchor="end", family=SANS,
               spacing=0.5),
          line(128, 704, 994, 704, 0.9),
          rect(92, 752, 938, 438, PALE, "none", 0),
          text(561, 802, "A THOUGHT FOR TODAY", 10, family=SANS, spacing=1.1)]
    p.append(quote_block(str(m["quote"]), str(m["source"]), x=561, y=980,
                         width=830, max_height=380, font_size=44, max_lines=4,
                         rule_color=MID, top=834, bottom=1164))
    p += [line(92, 1218, 1030, 1218, 0.8, MID),
          footer_brand(561, 1296 if m.get("creator") else 1306, str(m.get("creator", "")),
                       brand_size=13, brand_spacing=0, max_width=780,
                       creator_y=1324, creator_size=11.5, creator_max_width=780),
          "</svg>"]
    return "\n".join(p)
