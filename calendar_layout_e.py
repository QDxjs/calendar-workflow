"""SVG renderer for the E calendar layout."""

from __future__ import annotations

from datetime import date

from svg_primitives import (
    CLAY, INK, LATIN, PAPER, SANS, footer_brand, line, quote_block, rect, svg_open, text,
)


def render_e(m: dict[str, object]) -> str:
    """Render a bordered quotation page with readable side labels."""
    d = m["date"]
    assert isinstance(d, date)
    p = svg_open(f'{d.isoformat()} literary calendar — E quote frame')
    p += [
        rect(54, 44, 1014, 102, "none", INK, 1.2),
        line(294, 44, 294, 146, 1.0), line(824, 44, 824, 146, 1.0),
        text(174, 106, m["weekday"], 27, family=SANS, weight="bold", max_width=220),
        text(559, 104, f'{d.year} 年 {d.month} 月 {d.day} 日', 20,
             spacing=1.2, max_width=500),
        text(946, 101, f'ISO {m["week_label"]}', 13, family=SANS,
             spacing=0.5, max_width=220),
        line(166, 177, 166, 474, 1.0), line(956, 177, 956, 474, 1.0),
        text(105, 250, "READING", 11, family=SANS, spacing=1.2, max_width=112),
        text(105, 280, "FILE", 11, family=SANS, spacing=1.2, max_width=112),
        text(105, 310, f'NO. {m["ordinal"]:03d}', 11, family=SANS, spacing=0.8, max_width=112),
        text(1017, 250, "SOURCE", 11, family=SANS, spacing=1.0, max_width=112),
        text(1017, 280, "BOOK", 11, family=SANS, spacing=1.2, max_width=112),
        text(1017, 310, "PAGE", 11, family=SANS, spacing=1.2, max_width=112),
        text(561, 239, m["month"], 58, family=LATIN, spacing=3, max_width=730),
        text(561, 455, f'{m["day"]:02d}', 275, family=LATIN),
        line(54, 492, 1068, 492, 1.2),
        rect(54, 518, 1014, 652, "none", INK, 1.2),
        text(561, 558, "SELECTED PASSAGE", 12, family=SANS,
             spacing=1.5, max_width=700),
        line(164, 579, 958, 579, 0.9, CLAY),
        line(158, 596, 158, 1148, 0.9), line(964, 596, 964, 1148, 0.9),
        text(106, 816, "READ", 11, family=SANS, spacing=0.5),
        text(106, 858, "MARK", 11, family=SANS, spacing=0.5),
        text(106, 900, "KEEP", 11, family=SANS, spacing=0.5),
        text(1016, 816, "BOOK", 11, family=SANS, spacing=0.5),
        text(1016, 858, "PAGE", 11, family=SANS, spacing=0.5),
        text(1016, 900, "LINE", 11, family=SANS, spacing=0.5),
        f'<rect x="54" y="518" width="12" height="12" fill="{INK}"/>',
        f'<rect x="1056" y="518" width="12" height="12" fill="{INK}"/>',
        f'<rect x="54" y="1158" width="12" height="12" fill="{INK}"/>',
        f'<rect x="1056" y="1158" width="12" height="12" fill="{INK}"/>',
    ]
    p.append(quote_block(str(m["quote"]), str(m["source"]), x=561, y=860,
                         width=770, max_height=330, font_size=46, max_lines=5,
                         rule_color=CLAY, top=610, bottom=1142))
    p += [rect(42, 1200, 1038, 160, "none", INK, 1.2),
          rect(42, 1200, 146, 160, INK, INK, 0),
          rect(934, 1200, 146, 160, INK, INK, 0),
          text(115, 1264, "ISSUE", 11, fill=PAPER, family=SANS, spacing=1.2),
          text(115, 1290, f'{m["ordinal"]:03d}', 12, fill=PAPER,
               family=SANS, spacing=0.6),
          text(115, 1316, "OF THE YEAR", 9.5, fill=PAPER, family=SANS, spacing=0.4),
          line(235, 1280, 320, 1280),
          footer_brand(577, 1272 if m.get("creator") else 1288, str(m.get("creator", "")),
                       brand_size=15, brand_spacing=0.2, brand_italic=False, max_width=500,
                       creator_y=1304, creator_size=12, creator_max_width=500),
          line(835, 1280, 900, 1280),
          text(1007, 1264, "FILED", 11, fill=PAPER, family=SANS, spacing=1.0),
          text(1007, 1290, "BY DATE", 11, fill=PAPER, family=SANS, spacing=0.8),
          text(1007, 1316, str(d.year), 10, fill=PAPER, family=SANS, spacing=0.8),
          "</svg>"]
    return "\n".join(p)
