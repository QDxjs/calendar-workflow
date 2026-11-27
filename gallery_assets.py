"""Self-contained gallery UI embedded in each generated HTML file."""

VIEWER_CSS = r"""
dialog{padding:0;border:1px solid var(--line);border-radius:10px;background:var(--paper);color:var(--ink);
width:min(1120px,calc(100vw - 24px));max-width:calc(100vw - 24px);height:calc(100vh - 32px);max-height:calc(100vh - 32px)}
dialog[open]{display:flex;flex-direction:column}dialog::backdrop{background:#171716c9}
.viewer-controls{display:flex;gap:.6rem;align-items:center;flex-wrap:wrap;padding:.8rem 1rem;border-bottom:1px solid var(--line)}
.viewer-controls h2{margin:0;flex:1;min-width:130px}.viewer-controls button,.viewer-controls a{font:inherit;
padding:.5rem .7rem;border:1px solid var(--line);border-radius:5px;background:#fff;color:var(--ink);cursor:pointer;text-decoration:none}
.viewer-controls button:disabled{opacity:.4;cursor:default}.viewer-stage{flex:1;min-height:0;overflow:auto;background:#dedbd2}
.viewer-stage.fit{display:flex;align-items:center;justify-content:center}.viewer-stage img{display:block;margin:auto;max-width:none}
.viewer-stage.fit img{max-width:100%;max-height:100%;object-fit:contain}.viewer-caption{padding:.6rem 1rem;margin:0;max-height:6rem;overflow:auto;
font-size:.9rem;white-space:pre-wrap;overflow-wrap:anywhere}.viewer-error{padding:1.5rem}
@media(max-width:600px){.viewer-controls{gap:.4rem;padding:.5rem}.viewer-controls h2{flex-basis:100%;font-size:.9rem}
.viewer-controls button,.viewer-controls a{font-size:.85rem;padding:.45rem}.viewer-caption{max-height:4.5rem}}
"""

VIEWER_HTML = """
<dialog id="viewer" aria-labelledby="viewer-title">
<div class="viewer-controls"><h2 id="viewer-title">日历大图</h2>
<button id="viewer-prev" type="button" aria-label="上一页">← 上一页</button>
<button id="viewer-next" type="button" aria-label="下一页">下一页 →</button>
<button id="viewer-zoom" type="button" aria-pressed="false">100% 原图</button>
<a id="viewer-svg" download>下载 SVG</a><a id="viewer-png" download>下载 PNG</a>
<button id="viewer-close" type="button">关闭 Esc</button></div>
<div id="viewer-stage" class="viewer-stage fit"><img id="viewer-image" alt="日历大图">
<p id="viewer-error" class="viewer-error" role="status" hidden>图片无法读取，可能已被移动或删除。可切换其他页面。</p></div>
<p id="viewer-caption" class="viewer-caption"></p></dialog>
"""

GALLERY_SCRIPT = r"""
(()=>{
  const byId=id=>document.getElementById(id);
  const search=byId('search'),layout=byId('layout'),month=byId('month'),count=byId('result-count');
  const normalize=value=>value.normalize('NFKC').toLowerCase();
  const entries=[...document.querySelectorAll('.card')].map(card=>({card,text:normalize(card.dataset.search),
    link:card.querySelector('.preview'),svg:card.querySelector('a[download][href$=".svg"]')}));
  const viewer=byId('viewer'),image=byId('viewer-image'),stage=byId('viewer-stage');
  const previous=byId('viewer-prev'),next=byId('viewer-next'),zoom=byId('viewer-zoom');
  let visible=entries,active=null,trigger=null,fit=true;
  const show=entry=>{
    active=entry;const position=visible.indexOf(entry);
    byId('viewer-title').textContent=`${entry.card.querySelector('h2').textContent} · ${position+1} / ${visible.length}`;
    byId('viewer-caption').textContent=[entry.card.querySelector('.quote').textContent,entry.card.querySelector('.source').textContent].filter(Boolean).join(' · ');
    byId('viewer-png').href=entry.link.getAttribute('href');byId('viewer-svg').href=entry.svg.getAttribute('href');
    image.alt=entry.card.querySelector('img').alt;image.hidden=false;byId('viewer-error').hidden=true;
    image.src=entry.link.getAttribute('href');stage.scrollTop=stage.scrollLeft=0;
    previous.disabled=position<=0;next.disabled=position>=visible.length-1;
  };
  const update=()=>{
    const term=normalize(search.value).trim();visible=[];
    for(const entry of entries){const card=entry.card;
      const match=(!term||entry.text.includes(term))&&(!layout.value||card.dataset.layout===layout.value)&&(!month.value||card.dataset.month===month.value);
      card.hidden=!match;if(match)visible.push(entry);
    }
    count.textContent=visible.length?`显示 ${visible.length} / ${entries.length} 页`:'未找到匹配的日历页';
    if(viewer.open&&active){if(!visible.includes(active))viewer.close();else show(active);}
  };
  search.addEventListener('input',update);layout.addEventListener('change',update);month.addEventListener('change',update);
  update();byId('filters').hidden=false;
  if(typeof viewer.showModal!=='function')return;
  for(const entry of entries)entry.link.addEventListener('click',event=>{
    if(event.button!==0||event.ctrlKey||event.metaKey||event.shiftKey||event.altKey)return;
    try{trigger=entry.link;show(entry);viewer.showModal();event.preventDefault();}catch(_error){active=null;}
  });
  const move=offset=>{const index=visible.indexOf(active)+offset;if(index>=0&&index<visible.length)show(visible[index]);};
  previous.addEventListener('click',()=>move(-1));next.addEventListener('click',()=>move(1));
  byId('viewer-close').addEventListener('click',()=>viewer.close());
  viewer.addEventListener('keydown',event=>{
    if(event.key==='Escape'){event.preventDefault();viewer.close();}
    if(event.key==='ArrowLeft'){event.preventDefault();move(-1);}
    if(event.key==='ArrowRight'){event.preventDefault();move(1);}
  });
  zoom.addEventListener('click',()=>{fit=!fit;stage.classList.toggle('fit',fit);
    zoom.textContent=fit?'100% 原图':'适应窗口';zoom.setAttribute('aria-pressed',String(!fit));});
  image.addEventListener('error',()=>{if(viewer.open){image.hidden=true;byId('viewer-error').hidden=false;}});
  viewer.addEventListener('close',()=>{active=null;image.removeAttribute('src');
    if(trigger&&trigger.isConnected&&!trigger.closest('.card').hidden)trigger.focus();});
})();
"""
