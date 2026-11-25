"""SVG renderer for the C calendar layout."""

from __future__ import annotations

from datetime import date

from svg_primitives import BRAND, CLAY, LATIN, line, quote_block, svg_open, text


def render_c(m: dict[str, object]) -> str:
    """Render quiet typography with a broad field of paper."""
    d = m["date"]
    assert isinstance(d, date)
    p = svg_open(f'{d.isoformat()} literary calendar — C air')
    p += [line(76, 95, 76, 548, 1.2), line(1046, 95, 1046, 548, 1.2),
          text(561, 98, m["weekday"], 28, spacing=5),
          text(561, 143, f'{d.year} 年 {d.month} 月 {d.day} 日', 22, spacing=3),
          text(561, 181, f'CAL. {d.year} / ISO {m["week_label"]}', 14,
               spacing=0.8, max_width=500),
          text(561, 337, f'({m["month"]})', 76, family=LATIN, spacing=3),
          text(561, 804, f'{m["day"]:02d}', 444, family=LATIN),
          text(62, 627, "MARGIN", 12, anchor="start", spacing=2.0, max_width=130),
          text(62, 655, "NOTE", 12, anchor="start", spacing=2.0, max_width=130),
          text(62, 683, "NO. 001", 12, anchor="start", spacing=1.6, max_width=130),
          text(1060, 627, "YEAR DAY", 12, anchor="end", spacing=1.5, max_width=150),
          text(1060, 655, f'{m["ordinal"]} / {m["year_days"]}', 15,
               anchor="end", spacing=1.2, max_width=150),
          line(76, 711, 76, 1232, 1.2), line(1046, 711, 1046, 1232, 1.2)]
    p.append(quote_block(str(m["quote"]), str(m["source"]), x=561, y=1054,
                         width=850, max_height=216, font_size=39, max_lines=4,
                         rule_color=CLAY))
    p += [line(76, 1272, 1046, 1272),
          text(561, 1323, BRAND, 17, family=LATIN, italic=True, spacing=1.4,
               max_width=800), "</svg>"]
    return "\n".join(p)
