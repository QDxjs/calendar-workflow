from __future__ import annotations

import html
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from calendar_models import CalendarPage

def escape(value: object) -> str:
    return html.escape(str(value), quote=True)


def render_gallery(pages: list[CalendarPage], seed: int | None) -> str:
    cards: list[str] = []
    layouts = sorted({page.layout for page in pages})
    for page in pages:
        basename = f"{page.target_date.isoformat()}_layout-{page.layout}"
        cards.append(
            f'<article class="card" data-layout="{escape(page.layout)}" '
            f'data-search="{escape(" ".join((page.target_date.isoformat(), page.quote, page.source)))}">'
            f'<a class="preview" href="png/{basename}.png">'
            f'<img loading="lazy" src="png/{basename}.png" alt="{escape(page.target_date.isoformat())} 日历版式 {page.layout}"></a>'
            f'<div class="details"><h2>{escape(page.target_date.isoformat())} · {page.weekday}</h2>'
            f'<p class="quote">{escape(page.quote)}</p><p class="source">{escape(page.source)}</p>'
            f'<p class="links"><a href="svg/{basename}.svg" download>下载 SVG</a>'
            f'<a href="png/{basename}.png" download>下载 PNG</a></p></div></article>'
        )
    seed_label = "未固定" if seed is None else str(seed)
    layout_options = ''.join(
        f'<option value="{escape(layout)}">版式 {escape(layout)}</option>' for layout in layouts
    )
    return (
        '<!doctype html><html lang="zh-CN"><head><meta charset="utf-8">'
        '<meta name="viewport" content="width=device-width, initial-scale=1">'
        '<title>每日文学日历 · 批次预览</title><style>'
        ':root{color-scheme:light;--paper:#f3f0e8;--ink:#171716;--muted:#6b6963;--line:#d8d4ca}'
        '*{box-sizing:border-box}body{margin:0;background:var(--paper);color:var(--ink);'
        'font-family:"Microsoft YaHei","Noto Sans SC",sans-serif}header{padding:2rem clamp(1rem,5vw,4rem);'
        'border-bottom:1px solid var(--line)}h1{margin:0 0 .4rem;font-family:"SimSun",serif;font-weight:400}'
        '.summary{color:var(--muted);margin:0}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(min(100%,270px),1fr));'
        'gap:1.25rem;padding:clamp(1rem,4vw,3rem)}.card{overflow:hidden;background:#fff;border:1px solid var(--line);'
        'border-radius:8px;box-shadow:0 4px 16px #17171612}.preview{display:block;background:#e7e3d9}'
        '.toolbar{display:flex;flex-wrap:wrap;gap:.75rem;padding:1rem clamp(1rem,4vw,3rem) 0;align-items:end}'
        '.toolbar label{display:grid;min-width:0;max-width:100%;gap:.3rem;font-size:.85rem;color:var(--muted)}.toolbar input,.toolbar select{'
        'min-width:0;max-width:100%;min-height:2.6rem;padding:.4rem .65rem;border:1px solid var(--line);border-radius:5px;background:#fff;color:var(--ink)}'
        '.result-count{margin:0 0 .55rem;color:var(--muted);font-size:.9rem}[hidden]{display:none!important}'
        '.preview img{display:block;width:100%;height:auto}.details{padding:1rem 1.1rem 1.2rem}h2{font-size:.95rem;'
        'margin:0 0 .7rem}.quote{font-family:"SimSun",serif;line-height:1.8;margin:.5rem 0}.source{color:var(--muted);'
        'font-size:.85rem;margin:.4rem 0}.details{overflow-wrap:anywhere}.links{display:flex;flex-wrap:wrap;gap:1rem;margin:.9rem 0 0;font-size:.85rem}'
        'a{color:#67503f}:focus-visible{outline:2px solid #67503f;outline-offset:3px}'
        '.preview:focus-visible{outline-offset:-4px;position:relative}</style></head><body>'
        f'<header><h1>每日文学日历</h1><p class="summary">共 {len(pages)} 页 · 随机种子：{escape(seed_label)} · '
        '<a href="manifest.csv">查看生成清单</a></p></header>'
        '<section id="filters" class="toolbar" aria-label="筛选日历" hidden><label for="search">搜索日期、语录或出处'
        '<input id="search" type="search" autocomplete="off" placeholder="例如：2027-01 或 春风"></label>'
        f'<label for="layout">按版式筛选<select id="layout"><option value="">全部版式</option>{layout_options}</select></label>'
        f'<p id="result-count" class="result-count" role="status" aria-live="polite">显示 {len(pages)} / {len(pages)} 页</p></section>'
        f'<main class="gallery">{"".join(cards)}</main>'
        '<script>(()=>{const search=document.getElementById("search");const layout=document.getElementById("layout");'
        'const count=document.getElementById("result-count");const cards=[...document.querySelectorAll(".card")];'
        'const normalize=value=>value.normalize("NFKC").toLowerCase();'
        'const entries=cards.map(card=>({card,text:normalize(card.dataset.search)}));'
        'const update=()=>{const term=normalize(search.value).trim();const selected=layout.value;let visible=0;'
        'for(const {card,text} of entries){const match=(!term||text.includes(term))&&(!selected||card.dataset.layout===selected);'
        'card.hidden=!match;if(match)visible+=1}count.textContent=visible?`显示 ${visible} / ${cards.length} 页`:"未找到匹配的日历页"};'
        'search.addEventListener("input",update);layout.addEventListener("change",update);'
        'update();document.getElementById("filters").hidden=false})();</script></body></html>'
    )
