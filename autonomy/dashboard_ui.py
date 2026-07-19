"""Wave-51/53: the operator dashboard (single-page, vanilla, offline).

A dark, data-dense board in the house tote-green "totalizator" identity, pushed
to a premium finish: split-flap flip counters that roll only when new data
actually lands (like a physical pari-mutuel board), phosphor glow on live
figures, a faint CRT scanline, SVG charts that draw themselves in and answer a
hover crosshair, spring-staggered card reveals, and a sliding nav indicator.

Left nav = Overview plus a Crypto and a Sports section listing their coins /
leagues; the stage shows the overview (paper account, balance curve, promotion
ladder) or a per-scope breakdown (graded accuracy, progression, model-vs-market,
current picks) with the legacy surfaces folded into each scope's "Other data".

No build step, no CDN: served as one string, system fonts (Bahnschrift/Cascadia
for tabular numerics), hand-drawn SVG, CSS-only motion. Consumes /api/overview,
/api/scopes, /api/status -- all from the persisted snapshot (never the ledger).
prefers-reduced-motion freezes every animation; contrast holds WCAG-AA.

Design intelligence: ui-ux-pro-max Data-Dense Dashboard x a restrained slice of
terminal/phosphor treatment; motion tiers + chart specs from its motion/chart DB.
"""
from __future__ import annotations

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>DUMMY — the board</title>
<style>
:root{
  --bg:#04100a; --bg-1:#071811; --panel:#081c13; --panel-2:#0b2418; --panel-3:#0e2c1d;
  --line:#123528; --line-2:#1c5038; --line-3:#2a6b4c; --glow:rgba(77,255,160,.20);
  --green:#2fe38f; --phos:#5cffab; --green-deep:#0f7a52;
  --amber:#ffc24d; --amber-deep:#8a5a12; --red:#ff6b7a; --cyan:#6fe0ff; --violet:#b79cff;
  --txt:#e8f6ef; --muted:#83a898; --faint:#537163;
  --mono:"Cascadia Mono","Consolas",ui-monospace,monospace;
  --disp:"Bahnschrift","DIN Alternate Bold","Segoe UI Semibold","Segoe UI",sans-serif;
  --body:"Segoe UI",system-ui,-apple-system,sans-serif;
  --s1:6px; --s2:10px; --s3:16px; --s4:24px; --r:14px;
  --ease:cubic-bezier(.2,.8,.2,1); --spring:cubic-bezier(.16,1.1,.3,1);
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:
    radial-gradient(1300px 760px at 82% -14%, rgba(47,227,143,.11), transparent 60%),
    radial-gradient(1000px 640px at -6% 112%, rgba(111,224,255,.05), transparent 55%),
    var(--bg);
  color:var(--txt);font-family:var(--body);font-size:14px;line-height:1.5;
  -webkit-font-smoothing:antialiased;overflow:hidden}
/* faint CRT scanline — static (no motion), very low contrast */
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:9;
  background:repeating-linear-gradient(0deg,rgba(0,0,0,.16) 0 1px,transparent 1px 3px);
  opacity:.30;mix-blend-mode:overlay}
a{color:inherit;text-decoration:none}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:var(--line-2);border-radius:8px;border:2px solid transparent;background-clip:padding-box}
::-webkit-scrollbar-thumb:hover{background:var(--line-3);background-clip:padding-box}
::-webkit-scrollbar-track{background:transparent}
:focus-visible{outline:2px solid var(--phos);outline-offset:2px;border-radius:6px}

#app{display:grid;grid-template-columns:250px 1fr;height:100vh}

/* ---------- sidebar ---------- */
.side{position:relative;background:linear-gradient(180deg,var(--bg-1),var(--bg));
  border-right:1px solid var(--line);display:flex;flex-direction:column;min-height:0}
.side::after{content:"";position:absolute;top:0;right:0;width:1px;height:100%;
  background:linear-gradient(180deg,transparent,var(--line-2) 30%,var(--line-2) 70%,transparent)}
.brand{padding:var(--s4) var(--s3) var(--s3);display:flex;align-items:center;gap:11px}
.brand .mark{width:36px;height:36px;border-radius:10px;display:grid;place-items:center;
  background:radial-gradient(circle at 32% 26%,var(--phos),var(--green-deep));
  box-shadow:0 0 22px var(--glow),inset 0 1px 1px rgba(255,255,255,.35);
  color:#04140d;font-family:var(--disp);font-weight:700;font-size:19px}
.brand h1{margin:0;font-family:var(--disp);font-size:20px;letter-spacing:.16em;font-weight:700;
  text-shadow:0 0 18px var(--glow)}
.brand .sub{font-size:9.5px;letter-spacing:.36em;color:var(--green);text-transform:uppercase;opacity:.8}
.nav{position:relative;flex:1;overflow-y:auto;padding:var(--s2) var(--s2) var(--s4)}
.nav .glide{position:absolute;left:8px;width:calc(100% - 16px);height:38px;border-radius:10px;
  background:linear-gradient(90deg,rgba(47,227,143,.15),rgba(47,227,143,.03));
  border:1px solid var(--line-2);box-shadow:0 0 16px rgba(47,227,143,.08);
  transition:transform .34s var(--spring),height .2s,opacity .2s;opacity:0;pointer-events:none;z-index:0}
.nav .glide::before{content:"";position:absolute;left:0;top:8px;bottom:8px;width:3px;border-radius:3px;
  background:var(--phos);box-shadow:0 0 10px var(--phos)}
.grp{position:relative;margin-top:var(--s3);padding:0 var(--s2) var(--s1);font-size:9.5px;
  letter-spacing:.26em;text-transform:uppercase;color:var(--faint);display:flex;
  justify-content:space-between;align-items:center;z-index:1}
.item{position:relative;z-index:1;display:flex;align-items:center;gap:10px;padding:9px 11px;
  border-radius:10px;cursor:pointer;color:var(--muted);border:1px solid transparent;
  transition:color .16s,transform .16s}
.item svg{width:17px;height:17px;flex:none;stroke:currentColor;fill:none;stroke-width:1.7}
.item:hover{color:var(--txt);transform:translateX(2px)}
.item.active{color:var(--phos)}
.item.child{padding-left:16px;margin-left:12px;font-family:var(--mono);font-size:12.5px}
.item .tag{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--faint)}
.item.active .tag{color:var(--green)}
.side .foot{position:relative;z-index:1;border-top:1px solid var(--line);padding:var(--s2) var(--s3);
  display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--faint);flex:none;transition:.3s}
.dot.live{background:var(--green);box-shadow:0 0 10px var(--green);animation:pulse 2.4s infinite}
@keyframes pulse{50%{opacity:.35}}

/* ---------- stage ---------- */
.stage{overflow-y:auto;min-height:0;padding:var(--s4);scroll-behavior:smooth}
#view{animation:swap .42s var(--ease)}
@keyframes swap{from{opacity:0;transform:translateY(8px)}}
.topbar{display:flex;align-items:baseline;gap:14px;margin-bottom:var(--s4)}
.topbar h2{margin:0;font-family:var(--disp);font-size:27px;letter-spacing:.02em;text-shadow:0 0 22px var(--glow)}
.topbar .crumb{font-size:10.5px;letter-spacing:.24em;text-transform:uppercase;color:var(--faint)}
.topbar .spacer{flex:1}
.stamp{font-family:var(--mono);font-size:11px;color:var(--muted);display:flex;align-items:center;gap:7px}
.stamp .beat{width:6px;height:6px;border-radius:50%;background:var(--green);box-shadow:0 0 8px var(--green);animation:pulse 2.4s infinite}

.grid{display:grid;gap:var(--s3)}
.kpis{grid-template-columns:repeat(auto-fit,minmax(172px,1fr))}
.cols2{grid-template-columns:1fr 1fr}
@media(max-width:920px){.cols2{grid-template-columns:1fr}#app{grid-template-columns:64px 1fr}
  .brand h1,.brand .sub,.item span:not(.tag),.grp span:last-child{display:none}}

.card{position:relative;background:linear-gradient(180deg,var(--panel),var(--bg-1));
  border:1px solid var(--line);border-radius:var(--r);padding:var(--s3);overflow:hidden;
  transition:transform .2s var(--ease),border-color .2s,box-shadow .2s}
.card::before{content:"";position:absolute;inset:0 0 auto 0;height:1px;
  background:linear-gradient(90deg,transparent,var(--line-2),transparent);opacity:.7}
.card:hover{transform:translateY(-2px);border-color:var(--line-2);box-shadow:0 10px 30px -18px rgba(0,0,0,.7)}
.card.pad0{padding:0}
.card h3{margin:0 0 var(--s2);font-size:10.5px;letter-spacing:.2em;text-transform:uppercase;
  color:var(--muted);display:flex;align-items:center;gap:8px}
.card h3 .r{margin-left:auto;font-family:var(--mono);letter-spacing:0;text-transform:none;color:var(--faint)}
.reveal{animation:rise .55s var(--spring) backwards}
@keyframes rise{from{opacity:0;transform:translateY(14px) scale(.985)}}

.kpi .lab{font-size:9.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--faint);
  display:flex;align-items:center;gap:7px}
.kpi .val{font-family:var(--mono);font-size:28px;font-weight:600;margin-top:5px;letter-spacing:-.5px;
  line-height:1.1;min-height:31px}
.kpi .sub{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:3px}
.pos{color:var(--green)} .neg{color:var(--red)} .amb{color:var(--amber)} .cy{color:var(--cyan)}
.val.pos,.val.phos{text-shadow:0 0 16px var(--glow)}
.badge{display:inline-flex;align-items:center;gap:5px;font-size:9px;letter-spacing:.18em;
  text-transform:uppercase;padding:3px 8px;border-radius:20px;border:1px solid var(--amber-deep);color:var(--amber)}
.badge .d{width:5px;height:5px;border-radius:50%;background:var(--amber);box-shadow:0 0 6px var(--amber)}

/* split-flap flip counter — each char flips in when the value changes */
.flip{display:inline-flex}
.flip .flap{display:inline-block;transform-origin:50% 50%;animation:flap .52s var(--ease) both;
  backface-visibility:hidden}
@keyframes flap{
  0%{transform:rotateX(-88deg) translateY(-2px);opacity:0;color:var(--phos)}
  55%{opacity:1;color:var(--phos);text-shadow:0 0 14px var(--glow)}
  100%{transform:rotateX(0);opacity:1}}

table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12.5px}
thead th{position:sticky;top:0;background:var(--panel);z-index:1}
th{text-align:right;font-family:var(--body);font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--faint);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
td{padding:8px 10px;border-bottom:1px solid rgba(18,53,40,.55);white-space:nowrap}
tbody tr{transition:background .14s,box-shadow .14s}
tbody tr:hover{background:var(--panel-2);box-shadow:inset 2px 0 0 var(--green)}
.pill{font-size:10px;padding:2px 8px;border-radius:6px;font-family:var(--body);letter-spacing:.05em}
.pill.yes{background:rgba(47,227,143,.13);color:var(--green)}
.pill.no{background:rgba(255,107,122,.13);color:var(--red)}

.rank{display:flex;flex-direction:column;gap:9px}
.rowbar{display:grid;grid-template-columns:132px 1fr auto;align-items:center;gap:12px}
.rowbar .nm{font-family:var(--mono);font-size:12.5px;color:var(--txt);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.track{height:8px;border-radius:6px;background:var(--panel-2);overflow:hidden;border:1px solid var(--line)}
.fill{height:100%;border-radius:6px;background:linear-gradient(90deg,var(--green-deep),var(--phos));
  box-shadow:0 0 12px var(--glow);width:0;animation:grow 1s var(--ease) forwards}
.fill.amb{background:linear-gradient(90deg,var(--amber-deep),var(--amber));box-shadow:0 0 10px rgba(255,194,77,.3)}
@keyframes grow{from{width:0}}
.rowbar .mv{font-family:var(--mono);font-size:12px;color:var(--muted);min-width:64px;text-align:right}

.empty{padding:24px;text-align:center;color:var(--faint);font-size:12.5px;font-family:var(--mono);line-height:1.7}
.legend{display:flex;gap:15px;font-size:11px;color:var(--muted);margin-top:9px;flex-wrap:wrap}
.legend i{width:11px;height:3px;border-radius:2px;display:inline-block;margin-right:6px;vertical-align:middle}
.chip{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11.5px;
  padding:4px 9px;border-radius:8px;background:var(--panel-2);border:1px solid var(--line);margin:3px;transition:.15s}
.chip:hover{border-color:var(--line-2);color:var(--txt)}
.chip b{color:var(--phos);font-weight:600}

/* charts */
.cwrap{position:relative}
.chart{width:100%;display:block}
.chart .draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.25s var(--ease) forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.chart .dot{animation:pop .3s var(--ease) 1.1s both}
@keyframes pop{from{r:0;opacity:0}}
.grid-l{stroke:var(--line);stroke-width:1;opacity:.5}
.tick{fill:var(--faint);font-family:var(--mono);font-size:9px}
.cross{position:absolute;top:0;bottom:0;width:1px;background:var(--phos);opacity:0;
  box-shadow:0 0 8px var(--phos);pointer-events:none;transition:opacity .12s}
.ctip{position:absolute;transform:translate(-50%,-140%);background:var(--panel-3);border:1px solid var(--line-2);
  border-radius:8px;padding:5px 9px;font-family:var(--mono);font-size:11px;white-space:nowrap;opacity:0;
  pointer-events:none;transition:opacity .12s;box-shadow:0 8px 20px -10px #000;z-index:3}
.ctip b{color:var(--phos)}

@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}
  .chart .draw{stroke-dashoffset:0}.fill{width:var(--w,60%)!important}}
</style>
</head><body>
<div id="app">
  <aside class="side">
    <div class="brand">
      <div class="mark">D</div>
      <div><h1>DUMMY</h1><div class="sub">totalizator</div></div>
    </div>
    <nav class="nav" id="nav"><div class="glide" id="glide"></div></nav>
    <div class="foot"><span class="dot" id="live"></span><span id="footstat">connecting…</span></div>
  </aside>
  <main class="stage"><div id="view"></div></main>
</div>
<script>
const ICON={
 overview:'<path d="M3 3h7v7H3zM14 3h7v4h-7zM14 10h7v11h-7zM3 14h7v7H3z"/>',
 coin:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v9M9.5 9.5h4a1.8 1.8 0 0 1 0 3.6h-4"/>',
 ball:'<circle cx="12" cy="12" r="8.5"/><path d="M4 12h16M12 4v16"/>'
};
const $=(h)=>{const t=document.createElement('template');t.innerHTML=h.trim();return t.content.firstChild;};
const fmtUSD=(c)=> (c==null?'—':(c<0?'-':'')+'$'+Math.abs(c/100).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}));
const pct=(x,d=1)=> x==null?'—':(x*100).toFixed(d)+'%';
const signed=(x,d=1)=> x==null?'—':(x>0?'+':'')+(x*100).toFixed(d)+'%';
const sgn=(x)=> x==null?'':(x>=0?'pos':'neg');
const num=(x,d=3)=> x==null?'—':(+x).toFixed(d);
const commaN=(x)=> x==null?'—':(+x).toLocaleString();
const ago=(iso)=>{if(!iso)return'—';const s=(Date.now()-Date.parse(iso))/1000;if(s<90)return Math.round(s)+'s ago';if(s<5400)return Math.round(s/60)+'m ago';return Math.round(s/3600)+'h ago';};
const esc=(s)=>String(s==null?'':s).replace(/[&<>"]/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;'}[c]));
const flip=(text)=>'<span class="flip">'+String(text).split('').map((c,i)=>'<span class="flap" style="animation-delay:'+(i*32)+'ms">'+(c===' '?'&nbsp;':esc(c))+'</span>').join('')+'</span>';

let STATE={overview:null,scopes:null,status:null};
let ROUTE=location.hash||'#/overview';
let lastSig='';

function svgIcon(k){return '<svg viewBox="0 0 24 24">'+(ICON[k]||ICON.overview)+'</svg>';}

// ---------- charts ----------
function areaChart(pts,{h=170,color='var(--green)'}={}){
  if(!pts||pts.length<2)return '<div class="empty">no history yet</div>';
  const ys=pts.map(p=>p.v),mn=Math.min(...ys),mx=Math.max(...ys),rng=(mx-mn)||1;
  const W=1000,H=h,pad=8,n=pts.length;
  const X=i=>pad+i*(W-2*pad)/(n-1), Y=v=>pad+(1-(v-mn)/rng)*(H-2*pad);
  let d='M'+X(0).toFixed(1)+' '+Y(ys[0]).toFixed(1);ys.forEach((v,i)=>{if(i)d+=' L'+X(i).toFixed(1)+' '+Y(v).toFixed(1);});
  const area=d+' L'+X(n-1).toFixed(1)+' '+(H-pad)+' L'+X(0).toFixed(1)+' '+(H-pad)+' Z';
  let grid='';for(let g=1;g<4;g++){const yy=pad+g*(H-2*pad)/4;grid+='<line class="grid-l" x1="'+pad+'" y1="'+yy.toFixed(1)+'" x2="'+(W-pad)+'" y2="'+yy.toFixed(1)+'"/>';}
  const series=pts.map(p=>({l:p.t,v:p.disp!=null?p.disp:p.v}));
  return '<div class="cwrap" data-series=\''+esc(JSON.stringify(series))+'\'>'
    +'<svg class="chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="height:'+h+'px">'
    +'<defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="'+color+'" stop-opacity=".26"/><stop offset="1" stop-color="'+color+'" stop-opacity="0"/></linearGradient></defs>'
    +grid+'<path d="'+area+'" fill="url(#ag)"/>'
    +'<path class="draw" pathLength="1" d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2.4" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round"/>'
    +'<circle class="dot" cx="'+X(n-1).toFixed(1)+'" cy="'+Y(ys[n-1]).toFixed(1)+'" r="3.6" fill="'+color+'"><animate attributeName="opacity" values="1;.35;1" dur="2.2s" repeatCount="indefinite"/></circle>'
    +'</svg><div class="cross"></div><div class="ctip"></div></div>';
}
function lineChart(series,{h=150}={}){
  const any=series.find(s=>s.pts&&s.pts.length>1);
  if(!any)return '<div class="empty">not enough graded history</div>';
  const n=any.pts.length,W=1000,H=h,pad=8;
  const X=i=>pad+i*(W-2*pad)/(n-1);
  let out='<div class="cwrap" data-series=\''+esc(JSON.stringify(any.pts.map((p,i)=>({l:'#'+(i+1),v:p.v}))))+'\'>'
    +'<svg class="chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="height:'+h+'px">';
  out+='<line class="grid-l" x1="'+pad+'" y1="'+(H/2)+'" x2="'+(W-pad)+'" y2="'+(H/2)+'"/>';
  series.forEach((s,si)=>{
    if(!s.pts||s.pts.length<2)return;
    const ys=s.pts.map(p=>p.v),mn=Math.min(...ys),mx=Math.max(...ys),rng=(mx-mn)||1;
    const Y=v=>pad+(1-(v-mn)/rng)*(H-2*pad);
    let d='M'+X(0).toFixed(1)+' '+Y(ys[0]).toFixed(1);ys.forEach((v,i)=>{if(i)d+=' L'+X(i).toFixed(1)+' '+Y(v).toFixed(1);});
    out+='<path class="draw" pathLength="1" style="animation-delay:'+(si*.15)+'s" d="'+d+'" fill="none" stroke="'+s.color+'" stroke-width="2.1" '+(s.dash?'stroke-dasharray="5 5" ':'')+'vector-effect="non-scaling-stroke" stroke-linecap="round"/>';
  });
  out+='</svg><div class="cross"></div><div class="ctip"></div></div>';return out;
}
// delegated crosshair — survives re-renders
document.addEventListener('mousemove',e=>{
  const w=e.target.closest&&e.target.closest('.cwrap');if(!w)return;
  let series;try{series=JSON.parse(w.getAttribute('data-series'));}catch(_){return;}
  if(!series||!series.length)return;
  const r=w.getBoundingClientRect(),ratio=Math.min(1,Math.max(0,(e.clientX-r.left)/r.width));
  const i=Math.round(ratio*(series.length-1)),pt=series[i];
  const cross=w.querySelector('.cross'),tip=w.querySelector('.ctip'),x=(i/(series.length-1))*r.width;
  cross.style.left=x+'px';cross.style.opacity='.7';
  tip.style.left=Math.min(r.width-8,Math.max(8,x))+'px';tip.style.top='6px';tip.style.opacity='1';
  tip.innerHTML='<b>'+esc(typeof pt.v==='number'?(+pt.v).toLocaleString(undefined,{maximumFractionDigits:3}):pt.v)+'</b> · '+esc(pt.l||'');
});
document.addEventListener('mouseout',e=>{const w=e.target.closest&&e.target.closest('.cwrap');if(!w)return;
  const c=w.querySelector('.cross'),t=w.querySelector('.ctip');if(c)c.style.opacity='0';if(t)t.style.opacity='0';});

// ---------- sidebar ----------
function buildNav(){
  const nav=document.getElementById('nav');
  [...nav.querySelectorAll('.item,.grp')].forEach(n=>n.remove());
  nav.appendChild(navItem('overview','Overview','#/overview',null));
  const v=(STATE.scopes&&STATE.scopes.verticals)||{};
  [['CRYPTO','coin'],['SPORTS','ball']].forEach(([key,cicon])=>{
    const block=v[key];
    nav.appendChild($('<div class="grp"><span>'+key+'</span><span>'+(block?pct(block.summary.hit_rate,0):'')+'</span></div>'));
    if(!block){nav.appendChild($('<div class="item child" style="color:var(--faint)"><span>no data</span></div>'));return;}
    Object.keys(block.scopes).sort((a,b)=>(block.scopes[b].summary.n||0)-(block.scopes[a].summary.n||0)).forEach(lab=>{
      const it=navItem(cicon,lab,'#/scope/'+key+'/'+lab,pct(block.scopes[lab].summary.hit_rate,0));
      it.classList.add('child');nav.appendChild(it);
    });
  });
  requestAnimationFrame(()=>moveGlide());
}
function navItem(icon,label,href,tag){
  const a=$('<a class="item" href="'+href+'" tabindex="0">'+svgIcon(icon)+'<span>'+label+'</span>'+(tag?'<span class="tag">'+tag+'</span>':'')+'</a>');
  if(href===ROUTE)a.classList.add('active');
  a.addEventListener('mouseenter',()=>moveGlide(a));
  a.addEventListener('mouseleave',()=>moveGlide());
  return a;
}
function moveGlide(el){
  const nav=document.getElementById('nav'),glide=document.getElementById('glide');
  const t=el||nav.querySelector('.item.active');if(!t){glide.style.opacity='0';return;}
  glide.style.opacity='1';glide.style.transform='translateY('+t.offsetTop+'px)';glide.style.height=t.offsetHeight+'px';
}

// ---------- views ----------
function render(){
  const view=document.getElementById('view');
  const parts=ROUTE.replace('#/','').split('/');
  view.style.animation='none';void view.offsetWidth;view.style.animation='';
  if(parts[0]==='scope'&&parts[1]&&parts[2])view.innerHTML=scopeView(parts[1],parts[2]);
  else view.innerHTML=overviewView();
  [...view.querySelectorAll('.reveal')].forEach((el,i)=>el.style.animationDelay=(i*45)+'ms');
  buildNav();
}
function kpi(lab,val,cls,sub,doFlip){
  return '<div class="card kpi reveal"><div class="lab">'+lab+'</div><div class="val '+(cls||'')+'">'+(doFlip?flip(val):val)+'</div>'+(sub?'<div class="sub">'+sub+'</div>':'')+'</div>';
}
function overviewView(){
  const o=STATE.overview;
  if(!o||o.error||o.bankroll_cents==null)return topbar('Overview','account & promotion ladder')+skeleton();
  const rts=o.realized_trade_statistics||{};
  let h=topbar('Overview','account & promotion ladder');
  h+='<div class="grid kpis" style="margin-bottom:var(--s3)">';
  h+='<div class="card kpi reveal"><div class="lab">Account <span class="badge"><span class="d"></span>paper</span></div><div class="val phos">'+flip(fmtUSD(o.bankroll_cents))+'</div><div class="sub">base '+fmtUSD(o.base_bankroll_cents)+'</div></div>';
  h+=kpi('Account ROI',signed(o.account_roi),sgn(o.account_roi),'since inception',true);
  h+=kpi('Open exposure',fmtUSD(o.exposure_cents),'amb','stage '+o.stage,true);
  h+=kpi('Realized P&amp;L',fmtUSD(o.realized_pnl_cents),sgn(o.realized_pnl_cents),(rts.trades||0)+' settled trades',true);
  h+='</div>';
  const curve=(o.balance_curve||[]).map(p=>({v:p.bankroll_cents,disp:(p.bankroll_cents/100),t:(p.t||'').slice(0,10)}));
  h+='<div class="card reveal" style="margin-bottom:var(--s3)"><h3>Balance curve <span class="r">'+(o.balance_curve||[]).length+' pts · paper $</span></h3>'
    +areaChart(curve,{h:176,color:o.account_roi>=0?'var(--green)':'var(--red)'})
    +'<div class="legend"><span><i style="background:var(--green)"></i>paper bankroll</span><span style="color:var(--faint)">hover for value · date</span></div></div>';
  h+='<div class="grid kpis" style="margin-bottom:var(--s3)">';
  h+=kpi('Win rate',pct(rts.win_rate),'','settled trades',true);
  h+=kpi('ROI on cost',signed(rts.roi_on_entry_cost),sgn(rts.roi_on_entry_cost),'',true);
  h+=kpi('Profit factor',num(rts.profit_factor,2),rts.profit_factor>=1?'pos':'neg','',true);
  h+=kpi('Max drawdown',fmtUSD(rts.max_drawdown_cents),'amb','',true);
  h+='</div>';
  h+='<div class="grid cols2">';
  h+='<div class="card reveal"><h3>'+svgTrophy()+'Actively promoted</h3>'+promotedList(o.promoted)+'</div>';
  h+='<div class="card reveal"><h3>Close to promotion <span class="r">contested Brier edge</span></h3>'+closeList(o.close_to_promotion)+'</div>';
  h+='</div>';
  h+='<div class="card reveal" style="margin-top:var(--s3)"><h3>Active model — fused sources <span class="r">weight</span></h3><div>'
    +((o.active_sources||[]).map(s=>'<span class="chip">'+esc(s.source)+' <b>'+num(s.weight,2)+'</b></span>').join('')||'<div class="empty">no weights</div>')+'</div></div>';
  return h;
}
function skeleton(){
  return '<div class="grid kpis" style="margin-bottom:var(--s3)">'+Array(4).fill('<div class="card reveal" style="height:92px"><div class="empty">warming up…</div></div>').join('')
    +'</div><div class="card reveal" style="height:200px"><div class="empty">the snapshot refreshes every 20 min</div></div>';
}
function svgTrophy(){return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--amber)" stroke-width="1.7" style="vertical-align:-2px"><path d="M7 4h10v3a5 5 0 0 1-10 0zM7 5H4v2a3 3 0 0 0 3 3M17 5h3v2a3 3 0 0 1-3 3M9 20h6M12 12v8"/></svg>';}
function promotedList(arr){
  if(!arr||!arr.length)return '<div class="empty">0 promoted — every challenger still in evaluation<br><span style="color:var(--green)">promotion to capital is operator-gated</span></div>';
  return '<div class="rank">'+arr.map(e=>'<div class="rowbar"><span class="nm">'+esc(e.name)+'</span><span class="pill yes">'+(e.execution_authority?'execution':e.auto_promote?'auto':'ready')+'</span><span class="mv">'+(e.contested_markets||0)+' mkts</span></div>').join('')+'</div>';
}
function closeList(arr){
  if(!arr||!arr.length)return '<div class="empty">no challengers near the line</div>';
  return '<div class="rank">'+arr.map(e=>{
    const low=e.lower95==null?-0.05:e.lower95,w=Math.max(4,Math.min(100,(1-(Math.min(0,low)/-0.05))*100));
    return '<div class="rowbar"><span class="nm" title="'+esc(e.blocker||'')+'">'+esc(e.name)+'</span>'
      +'<span class="track"><span class="fill amb" style="--w:'+w.toFixed(0)+'%;width:'+w.toFixed(0)+'%"></span></span>'
      +'<span class="mv '+(low>=0?'pos':'')+'">'+num(low,3)+'</span></div>';
  }).join('')+'</div>';
}
function scopeView(vert,label){
  const block=STATE.scopes&&STATE.scopes.verticals&&STATE.scopes.verticals[vert];
  const sc=block&&block.scopes&&block.scopes[label];
  if(!sc)return topbar(label,vert.toLowerCase())+'<div class="card"><div class="empty">no data for '+esc(label)+' yet</div></div>';
  const s=sc.summary;
  let h=topbar(label,vert.toLowerCase()+' · graded forecast quality');
  h+='<div class="grid kpis" style="margin-bottom:var(--s3)">';
  h+=kpi('Graded picks',commaN(s.n||0),'','settled markets',true);
  h+=kpi('Hit rate',pct(s.hit_rate),s.hit_rate>=.5?'pos':'neg','directional',true);
  h+=kpi('Brier',num(s.brier),'','lower = sharper',true);
  h+=kpi('Edge vs market',signed(s.brier_edge,2),sgn(s.brier_edge),(s.contested_n||0)+' contested',true);
  h+=kpi('Open picks',(sc.picks?sc.picks.length:0),'amb','live now',true);
  h+='</div>';
  const prog=sc.progression||[];
  const hitPts=prog.filter(p=>p.hit_rate!=null).map(p=>({v:p.hit_rate}));
  const brPts=prog.filter(p=>p.brier!=null).map(p=>({v:p.brier}));
  h+='<div class="card reveal" style="margin-bottom:var(--s3)"><h3>Progression <span class="r">'+prog.length+' windows · oldest→newest</span></h3>'
    +lineChart([{name:'hit',color:'var(--green)',pts:hitPts},{name:'brier',color:'var(--amber)',pts:brPts,dash:true}],{h:150})
    +'<div class="legend"><span><i style="background:var(--green)"></i>hit rate</span><span><i style="background:var(--amber)"></i>Brier</span></div></div>';
  h+='<div class="grid cols2">';
  h+='<div class="card reveal"><h3>Model vs market <span class="r">Brier, lower better</span></h3>'+accuracyBars(s)+'</div>';
  h+='<div class="card pad0 reveal"><h3 style="padding:var(--s3) var(--s3) var(--s2)">Current picks <span class="r">by edge</span></h3>'+picksTable(sc.picks)+'</div>';
  h+='</div>';
  h+=extrasSection(sc.extras||{},label);
  return h;
}
function accuracyBars(s){
  if(s.market_brier==null)return '<div class="empty">no contested (market-priced) markets in window</div>';
  const mx=Math.max(s.brier,s.market_brier,0.25);
  const bar=(lab,v,cls)=>'<div class="rowbar" style="grid-template-columns:96px 1fr auto"><span class="nm">'+lab+'</span>'
    +'<span class="track" style="height:13px"><span class="fill '+cls+'" style="--w:'+(v/mx*100).toFixed(0)+'%;width:'+(v/mx*100).toFixed(0)+'%"></span></span>'
    +'<span class="mv">'+num(v)+'</span></div>';
  const better=s.brier<s.market_brier;
  return '<div class="rank">'+bar('model',s.brier,better?'':'amb')+bar('market',s.market_brier,'amb')
    +'</div><div class="sub" style="margin-top:11px;font-family:var(--mono);font-size:12px;color:'+(better?'var(--green)':'var(--red)')+'">'
    +(better?'▲ model beats the line by '+num(s.brier_edge,3)+' Brier':'▼ model trails the line by '+num(-s.brier_edge,3))+'</div>';
}
function picksTable(picks){
  if(!picks||!picks.length)return '<div class="empty">no open picks in this scope right now</div>';
  let h='<div style="max-height:326px;overflow:auto"><table><thead><tr><th>Market</th><th>Side</th><th>Model</th><th>Mkt</th><th>Edge¢</th></tr></thead><tbody>';
  picks.forEach(p=>{h+='<tr><td title="'+esc(p.ticker)+'">'+esc(p.ticker)+'</td>'
    +'<td><span class="pill '+((p.side||'').toUpperCase().includes('NO')?'no':'yes')+'">'+esc(p.side||'')+'</span></td>'
    +'<td>'+num(p.prob,2)+'</td><td>'+(p.market==null?'—':num(p.market,2))+'</td>'
    +'<td class="'+(p.edge_cents>=0?'pos':'neg')+'">'+(p.edge_cents>0?'+':'')+num(p.edge_cents,1)+'</td></tr>';});
  return h+'</tbody></table></div>';
}

// ---------- scope "other data" ----------
function extrasSection(x,label){
  const hasCouncil=!!x.council,hasClv=(x.clv||[]).length,hasMisp=(x.mispricing||[]).length,hasEj=(x.ejections||[]).length;
  if(!hasCouncil&&!hasClv&&!hasMisp&&!hasEj)return '';
  let h='<div class="topbar" style="margin:var(--s4) 0 var(--s3)"><h2 style="font-size:18px">Other data</h2><span class="crumb">council · clv · live mispricing</span></div>';
  h+='<div class="grid cols2" style="margin-bottom:var(--s3)">';
  h+='<div class="card reveal"><h3>'+svgIcon2('council')+'Council — '+esc(label)+' specialist</h3>'+councilCard(x.council)+'</div>';
  h+='<div class="card reveal"><h3>Closing-line value <span class="r">bps vs close</span></h3>'+clvCard(x.clv)+'</div>';
  h+='</div>';
  if(hasEj)h+='<div class="card reveal" style="margin-bottom:var(--s3);border-color:var(--amber-deep)"><h3 style="color:var(--amber)">'+svgIcon2('alert')+'Ejection / injury events</h3>'+ejectionList(x.ejections)+'</div>';
  h+='<div class="card pad0 reveal"><h3 style="padding:var(--s3) var(--s3) var(--s2)">Live mispricing tape <span class="r">model vs book vs market</span></h3>'+mispTable(x.mispricing)+'</div>';
  return h;
}
function svgIcon2(k){const p={council:'<path d="M12 3l7 4v5c0 4-3 7-7 8-4-1-7-4-7-8V7z"/><path d="M9 12l2 2 4-4"/>',alert:'<path d="M12 3l9 16H3z"/><path d="M12 9v5M12 17v.5"/>'};
  return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.7" style="vertical-align:-2px;margin-right:2px">'+(p[k]||'')+'</svg>';}
function councilCard(c){
  if(!c)return '<div class="empty">no council row for this scope</div>';
  const row=(k,v,cls)=>'<div class="rowbar" style="grid-template-columns:150px 1fr"><span class="nm" style="color:var(--muted)">'+k+'</span><span class="mv '+(cls||'')+'" style="text-align:left">'+v+'</span></div>';
  let h='<div class="rank">';
  h+=row('Status',esc(c.status||'—')+(c.in_season?' · in season':(c.in_season===false?' · off season':'')),c.in_season?'pos':'');
  h+=row('Contested Brier',c.contested_brier==null?'—':num(c.contested_brier)+' <span style="color:var(--faint)">('+(c.contested_n||0)+')</span>');
  h+=row('CLV',c.clv_bps==null?'—':(c.clv_bps>0?'+':'')+num(c.clv_bps,0)+' bps',c.clv_bps>0?'pos':(c.clv_bps<0?'neg':''));
  h+=row('Open opportunities',(c.open_opportunities||0),(c.open_opportunities>0?'amb':''));
  h+=row('Graded',(c.settled_n||0)+' settled');
  if(c.games_seen!=null)h+=row('Games seen',c.games_seen);
  if(c.where_we_bleed)h+=row('Where we bleed','<span style="color:var(--red)">'+esc(c.where_we_bleed)+'</span>');
  return h+'</div>';
}
function clvCard(clv){
  if(!clv||!clv.length)return '<div class="empty">no CLV entries for this scope yet</div>';
  let h='<div class="rank">';
  clv.forEach(c=>{const m=c.clv_bps_mean;
    h+='<div class="rowbar" style="grid-template-columns:1fr auto auto;gap:10px"><span class="nm">'+esc(c.market_type||'—')+'</span>'
      +'<span class="mv '+(m>0?'pos':(m<0?'neg':''))+'">'+(m==null?'—':(m>0?'+':'')+num(m,0)+' bps')+'</span>'
      +'<span class="mv" style="color:var(--faint);min-width:48px">'+(c.n_entries||0)+'n</span></div>';});
  return h+'</div>';
}
function ejectionList(ev){return '<div>'+ev.map(e=>'<span class="chip" style="border-color:var(--amber-deep)">'+esc(typeof e==='string'?e:(e.player||e.team||e.detail||JSON.stringify(e).slice(0,40)))+'</span>').join('')+'</div>';}
function mispTable(rows){
  if(!rows||!rows.length)return '<div class="empty">no live mispricing on this scope right now</div>';
  let h='<div style="max-height:344px;overflow:auto"><table><thead><tr><th>Market</th><th>Side</th><th>Edge</th><th>Model</th><th>Book</th><th>Mkt</th><th>Conf</th></tr></thead><tbody>';
  rows.forEach(r=>{const e=r.edge==null?null:(r.edge*100);
    h+='<tr><td title="'+esc(r.ticker)+' — '+esc(r.rationale||'')+'">'+esc(r.ticker||'')+'</td>'
      +'<td><span class="pill '+((r.side||'').toUpperCase().includes('NO')?'no':'yes')+'">'+esc(r.side||'')+'</span></td>'
      +'<td class="'+(e>=0?'pos':'neg')+'">'+(e==null?'—':(e>0?'+':'')+e.toFixed(1)+'%')+'</td>'
      +'<td>'+(r.model_prob==null?'—':num(r.model_prob,2))+'</td><td>'+(r.book_prob==null?'—':num(r.book_prob,2))+'</td>'
      +'<td>'+(r.market_prob==null?'—':num(r.market_prob,2))+'</td><td style="color:var(--muted)">'+esc(r.confidence||'—')+'</td></tr>';});
  return h+'</tbody></table></div>';
}
function topbar(title,crumb){
  const stamp=STATE.overview&&STATE.overview.generated_at;
  return '<div class="topbar"><h2>'+esc(title)+'</h2><span class="crumb">'+esc(crumb)+'</span><span class="spacer"></span>'
    +'<span class="stamp"><span class="beat"></span>updated '+ago(stamp)+'</span></div>';
}

// ---------- data ----------
async function poll(){
  try{
    const [ov,sc,st]=await Promise.all([
      fetch('/api/overview').then(r=>r.json()).catch(()=>null),
      fetch('/api/scopes').then(r=>r.json()).catch(()=>null),
      fetch('/api/status').then(r=>r.json()).catch(()=>null),
    ]);
    if(ov)STATE.overview=ov;if(sc)STATE.scopes=sc;if(st)STATE.status=st;
    const live=document.getElementById('live'),fs=document.getElementById('footstat');
    const fresh=ov&&ov.generated_at&&(Date.now()-Date.parse(ov.generated_at))<30*60*1000;
    live.className='dot'+(fresh?' live':'');
    fs.textContent=fresh?'live · '+ago(ov.generated_at):'stale snapshot';
    // re-render (and re-flip the flaps) only when the data actually changed --
    // like a real tote board, the numbers roll when new results land.
    const sig=JSON.stringify([STATE.overview,STATE.scopes]);
    if(sig!==lastSig){lastSig=sig;render();}
  }catch(e){}
}
window.addEventListener('hashchange',()=>{ROUTE=location.hash||'#/overview';render();});
window.addEventListener('resize',()=>moveGlide());
render();poll();setInterval(poll,20000);
</script>
</body></html>"""
