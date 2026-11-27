"""SVG renderer for the B calendar layout."""

from __future__ import annotations

from datetime import date

from svg_primitives import (
    BRAND, CLAY, INK, LATIN, PALE, PAPER, SANS, label_block, line,
    quote_block, rect, svg_open, text,
)


def render_b(m: dict[str, object]) -> str:
    """Render asymmetric geometry with a bold typographic date."""
    d = m["date"]
    assert isinstance(d, date)
    p = svg_open(f'{d.isoformat()} literary calendar — B geometry')
    p += [text(42, 44, "TYPE / FIELD", 12, anchor="start", family=SANS,
               spacing=1.8, max_width=180),
          text(42, 68, "EDITION 001", 12, anchor="start", family=SANS,  # Series edition, not a day index.
               spacing=1.4, max_width=180),
          text(42, 92, "READING FILE", 12, anchor="start", family=SANS,
               spacing=1.2, max_width=180),
          line(42, 118, 84, 118, 1.5, CLAY),
          line(633, 26, 633, 170, 1.2), line(660, 46, 732, 46),
          text(660, 72, "WORDS / DATE", 12, anchor="start", family=SANS,
               spacing=1.5, max_width=220),
          text(660, 98, "A DAILY INDEX", 12, anchor="start", family=SANS,
               spacing=1.5, max_width=220),
          text(660, 124, "SERIES 01", 12, anchor="start", family=SANS,
               spacing=1.5, max_width=220),
          text(660, 150, f'VOLUME {d.year}', 12, anchor="start", family=SANS,
               spacing=1.3, max_width=220),
          f'<path d="M798 20 H1098 V349 Z" fill="{INK}"/>',
          text(1048, 54, "SOURCE", 11.5, fill=PAPER, family=SANS, spacing=1.2, max_width=120),
          text(1048, 80, "DATE", 11.5, fill=PAPER, family=SANS, spacing=1.2, max_width=120),
          text(1048, 106, "ENTRY", 11.5, fill=PAPER, family=SANS, spacing=1.2, max_width=120),
          text(1048, 132, f'NO. {m["ordinal"]:03d}', 11.5, fill=PAPER, family=SANS, spacing=1.0, max_width=120),
          rect(42, 185, 594, 154, INK, INK, 0),
          text(339, 287, m["month"], 82, fill=PAPER, family=SANS, weight="bold", max_width=560),
          text(339, 722, f'{m["day"]:02d}', 410, anchor="middle", family=SANS, weight="bold"),
          line(660, 188, 660, 772, 1.5),
          f'<path d="M918 180 L1094 354 L918 354 Z" fill="{PALE}"/>',
          rect(918, 369, 176, 406, "#343331", "#343331", 0),
          f'<path d="M918 369 L1094 369 L918 548 Z" fill="#4a4946"/>',
          f'<path d="M918 548 L1094 369 L1094 775 L918 775 Z" fill="#292827"/>',
          text(690, 244, m["weekday"], 31, anchor="start", weight="bold", family=SANS),
          line(690, 278, 888, 278),
          text(690, 330, f'{d.year} 年 {d.month} 月 {d.day} 日', 18,
               anchor="start", weight="bold", family=SANS, max_width=198),
          line(690, 374, 888, 374),
          text(690, 405, f'CAL. {d.year}', 12, anchor="start", family=SANS,
               spacing=0.8, max_width=198),
          text(690, 448, f'ISO {m["week_label"]}', 28, anchor="start",
               weight="bold", family=SANS, max_width=198),
          line(690, 470, 888, 470),
          text(690, 526, f'{m["ordinal"]} / {m["year_days"]}', 25,
               anchor="start", weight="bold", family=SANS, max_width=198),
          line(690, 563, 888, 563),
          text(690, 650, "SOURCE / BOOK", 11.5, anchor="start", family=SANS,
               spacing=1.2, max_width=198),
          text(690, 676, "PAGE / LINE", 11.5, anchor="start", family=SANS,
               spacing=1.2, max_width=198),
          text(690, 702, f'ARCHIVE {m["ordinal"]:03d}', 11.5, anchor="start", family=SANS,
               spacing=1.2, max_width=198),
          line(690, 752, 720, 752, 1.1, CLAY)]
    p += [rect(42, 796, 860, 268, "none", INK, 1.5),
          rect(42, 796, 150, 268, INK, INK, 0),
          *([text(117, 954, "“", 92, fill=PAPER, family=LATIN)] if str(m["quote"]).strip() else []),
          rect(918, 796, 176, 268, INK, INK, 0)]
    p.append(quote_block(str(m["quote"]), "", x=547, y=930, width=700,
                         max_height=190, font_size=42, max_lines=4))
    p += [rect(42, 1078, 150, 159, INK, INK, 0),
          f'<path d="M42 1078 L192 1078 L42 1237 Z" fill="{PAPER}"/>',
          *([label_block(str(m["source"]), x=242, y=1141, width=658,
                         font_size=30, anchor="start", weight="bold", family=SANS),
             line(242, 1170, 900, 1170, 1.2),
             text(242, 1210, "SOURCE / CITATION", 11.5, anchor="start", family=SANS,
                  spacing=1.0, max_width=650)] if m["source"] else []),
          rect(42, 1242, 1052, 123, "none", INK, 1.3),
          rect(883, 1242, 211, 123, INK, INK, 0),
          text(462, 1318, BRAND, 16, family=LATIN, italic=True, max_width=760),
          text(988, 1304, "FILED UNDER", 10.5, fill=PAPER, family=SANS,
               spacing=0.6, max_width=180),
          text(988, 1327, f'READING / {m["ordinal"]:03d}', 10.5, fill=PAPER, family=SANS,
               spacing=0.4, max_width=180), "</svg>"]
    return "\n".join(p)
