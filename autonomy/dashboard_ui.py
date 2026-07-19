"""Wave-51: the redesigned operator dashboard (single-page, vanilla, offline).

A dark, data-dense board in the house tote-green identity. Left nav = Overview
plus a Crypto and a Sports section that list their coins / leagues; the main
stage shows the overview (paper account, balance curve, promotion ladder) or a
per-scope breakdown (graded accuracy, progression, current picks).

No build step, no CDN: the FastAPI app serves this string as-is, so everything
is inline -- system fonts (Bahnschrift/Cascadia for tabular numerics), hand-
drawn SVG charts, CSS-only motion. It consumes /api/overview, /api/scopes and
/api/status, all served from the persisted snapshot (never the live ledger).

Design intelligence: ui-ux-pro-max "Data-Dense Dashboard" (dark), density 8,
standard motion, WCAG-AA contrast, SVG icons (no emoji), reduced-motion honored.
"""
from __future__ import annotations

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>DUMMY — the board</title>
<style>
:root{
  --bg:#060d0a; --bg-1:#0a1712; --panel:#0b1a14; --panel-2:#0e2119;
  --line:#153029; --line-2:#1f4a3a; --glow:rgba(55,245,160,.14);
  --green:#37f5a0; --green-dim:#1f9e6a; --phos:#5cff9e;
  --amber:#ffb84d; --red:#ff6b78; --blue:#67d0ff; --violet:#b79cff;
  --txt:#e2f1ea; --muted:#82a596; --faint:#517063;
  --mono:"Cascadia Mono","Consolas",ui-monospace,monospace;
  --disp:"Bahnschrift","DIN Alternate Bold","Segoe UI Semibold","Segoe UI",sans-serif;
  --body:"Segoe UI",system-ui,-apple-system,sans-serif;
  --s1:6px; --s2:10px; --s3:16px; --s4:24px; --r:13px;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:
    radial-gradient(1200px 700px at 78% -12%, rgba(31,158,106,.10), transparent 60%),
    radial-gradient(900px 600px at 0% 108%, rgba(103,208,255,.05), transparent 55%),
    var(--bg);
  color:var(--txt);font-family:var(--body);font-size:14px;line-height:1.5;
  -webkit-font-smoothing:antialiased;overflow:hidden}
a{color:inherit;text-decoration:none}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:var(--line-2);border-radius:8px}
::-webkit-scrollbar-track{background:transparent}

#app{display:grid;grid-template-columns:246px 1fr;height:100vh}

/* ---- sidebar ---- */
.side{background:linear-gradient(180deg,var(--bg-1),var(--bg));border-right:1px solid var(--line);
  display:flex;flex-direction:column;min-height:0}
.brand{padding:var(--s4) var(--s3) var(--s3);display:flex;align-items:center;gap:10px}
.brand .mark{width:34px;height:34px;border-radius:9px;display:grid;place-items:center;
  background:radial-gradient(circle at 30% 25%,var(--phos),var(--green-dim));
  box-shadow:0 0 18px var(--glow);color:#04140d;font-family:var(--disp);font-weight:700}
.brand h1{margin:0;font-family:var(--disp);font-size:19px;letter-spacing:.14em;font-weight:700}
.brand .sub{font-size:10px;letter-spacing:.34em;color:var(--green-dim);text-transform:uppercase}
.nav{flex:1;overflow-y:auto;padding:var(--s2) var(--s2) var(--s4)}
.nav .grp{margin-top:var(--s3);padding:0 var(--s2) var(--s1);font-size:10px;letter-spacing:.24em;
  text-transform:uppercase;color:var(--faint);display:flex;justify-content:space-between;align-items:center}
.item{display:flex;align-items:center;gap:10px;padding:9px 11px;border-radius:10px;cursor:pointer;
  color:var(--muted);border:1px solid transparent;transition:background .16s,color .16s,border-color .16s}
.item svg{width:17px;height:17px;flex:none;stroke:currentColor;fill:none;stroke-width:1.7}
.item:hover{background:var(--panel);color:var(--txt)}
.item:focus-visible{outline:2px solid var(--green);outline-offset:2px}
.item.active{background:linear-gradient(90deg,rgba(55,245,160,.12),rgba(55,245,160,.02));
  color:var(--phos);border-color:var(--line-2)}
.item.child{padding-left:14px;margin-left:12px;font-family:var(--mono);font-size:12.5px}
.item .tag{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--faint)}
.item.active .tag{color:var(--green-dim)}
.side .foot{border-top:1px solid var(--line);padding:var(--s2) var(--s3);display:flex;
  align-items:center;gap:8px;font-size:11px;color:var(--muted)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--faint);flex:none}
.dot.live{background:var(--green);box-shadow:0 0 9px var(--green);animation:pulse 2.4s infinite}
@keyframes pulse{50%{opacity:.4}}

/* ---- stage ---- */
.stage{overflow-y:auto;padding:var(--s4);min-height:0}
.topbar{display:flex;align-items:baseline;gap:14px;margin-bottom:var(--s4)}
.topbar h2{margin:0;font-family:var(--disp);font-size:26px;letter-spacing:.02em}
.topbar .crumb{font-size:11px;letter-spacing:.24em;text-transform:uppercase;color:var(--faint)}
.topbar .spacer{flex:1}
.stamp{font-family:var(--mono);font-size:11px;color:var(--muted)}

.grid{display:grid;gap:var(--s3)}
.kpis{grid-template-columns:repeat(auto-fit,minmax(168px,1fr))}
.cols2{grid-template-columns:1fr 1fr}
@media(max-width:900px){.cols2{grid-template-columns:1fr}}

.card{background:linear-gradient(180deg,var(--panel),var(--bg-1));border:1px solid var(--line);
  border-radius:var(--r);padding:var(--s3);position:relative;overflow:hidden}
.card.pad0{padding:0}
.card h3{margin:0 0 var(--s2);font-size:11px;letter-spacing:.2em;text-transform:uppercase;
  color:var(--muted);display:flex;align-items:center;gap:8px}
.card h3 .r{margin-left:auto;font-family:var(--mono);letter-spacing:0;text-transform:none;color:var(--faint)}
.reveal{animation:rise .5s cubic-bezier(.2,.7,.2,1) backwards}
@keyframes rise{from{opacity:0;transform:translateY(12px) scale(.98)}}

.kpi .lab{font-size:10px;letter-spacing:.2em;text-transform:uppercase;color:var(--faint)}
.kpi .val{font-family:var(--mono);font-size:27px;font-weight:600;margin-top:4px;letter-spacing:-.5px}
.kpi .val.sm{font-size:21px}
.kpi .sub{font-family:var(--mono);font-size:12px;color:var(--muted);margin-top:2px}
.pos{color:var(--green)} .neg{color:var(--red)} .amb{color:var(--amber)}
.badge{display:inline-flex;align-items:center;gap:5px;font-size:9.5px;letter-spacing:.18em;
  text-transform:uppercase;padding:3px 8px;border-radius:20px;border:1px solid var(--line-2);color:var(--amber)}
.badge .d{width:5px;height:5px;border-radius:50%;background:var(--amber)}
.flip{animation:flip .5s ease}
@keyframes flip{0%{color:var(--phos);text-shadow:0 0 10px var(--glow)}100%{}}

table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12.5px}
th{font-family:var(--body);text-align:right;font-size:10px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--faint);font-weight:600;padding:6px 10px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
td{padding:8px 10px;border-bottom:1px solid rgba(21,48,41,.5);white-space:nowrap}
tbody tr{transition:background .14s}
tbody tr:hover{background:var(--panel-2)}
.pill{font-size:10px;padding:2px 7px;border-radius:6px;font-family:var(--body);letter-spacing:.06em}
.pill.yes{background:rgba(55,245,160,.12);color:var(--green)}
.pill.no{background:rgba(255,107,120,.12);color:var(--red)}

.rank{display:flex;flex-direction:column;gap:9px}
.rowbar{display:grid;grid-template-columns:130px 1fr auto;align-items:center;gap:12px}
.rowbar .nm{font-family:var(--mono);font-size:12.5px;color:var(--txt);overflow:hidden;text-overflow:ellipsis}
.track{height:8px;border-radius:6px;background:var(--panel-2);overflow:hidden;position:relative;border:1px solid var(--line)}
.fill{height:100%;border-radius:6px;background:linear-gradient(90deg,var(--green-dim),var(--phos));
  box-shadow:0 0 10px var(--glow);transition:width .7s cubic-bezier(.2,.7,.2,1)}
.fill.amb{background:linear-gradient(90deg,#8a5a12,var(--amber));box-shadow:none}
.rowbar .mv{font-family:var(--mono);font-size:12px;color:var(--muted);min-width:64px;text-align:right}

.empty{padding:22px;text-align:center;color:var(--faint);font-size:12.5px;font-family:var(--mono)}
.legend{display:flex;gap:14px;font-size:11px;color:var(--muted);margin-top:8px}
.legend i{width:10px;height:3px;border-radius:2px;display:inline-block;margin-right:5px;vertical-align:middle}
.chart{width:100%;display:block}
.tick{fill:var(--faint);font-family:var(--mono);font-size:9px}
.chip{display:inline-flex;align-items:center;gap:6px;font-family:var(--mono);font-size:11.5px;
  padding:4px 9px;border-radius:8px;background:var(--panel-2);border:1px solid var(--line);margin:3px}
.chip b{color:var(--phos);font-weight:600}
.hero{display:flex;gap:var(--s4);flex-wrap:wrap;align-items:flex-end}
@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}}
</style>
</head><body>
<div id="app">
  <aside class="side">
    <div class="brand">
      <div class="mark">D</div>
      <div><h1>DUMMY</h1><div class="sub">totalizator</div></div>
    </div>
    <nav class="nav" id="nav"></nav>
    <div class="foot"><span class="dot" id="live"></span><span id="footstat">connecting…</span></div>
  </aside>
  <main class="stage"><div id="view"></div></main>
</div>
<script>
const ICON={
 overview:'<path d="M3 3h7v7H3zM14 3h7v4h-7zM14 10h7v11h-7zM3 14h7v7H3z"/>',
 crypto:'<circle cx="12" cy="12" r="9"/><path d="M9.5 8h4a2.5 2.5 0 0 1 0 5h-4zM9.5 13h4.5a2.5 2.5 0 0 1 0 5H9.5zM9.5 8v10M11 6.5v1.5M11 18v1.5"/>',
 sports:'<path d="M7 4h10v3a5 5 0 0 1-10 0zM7 5H4v2a3 3 0 0 0 3 3M17 5h3v2a3 3 0 0 1-3 3M9 14h6M8 20h8M12 12v8"/>',
 coin:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v9M9.5 9.5h4a1.8 1.8 0 0 1 0 3.6h-4"/>',
 ball:'<circle cx="12" cy="12" r="8.5"/><path d="M4 12h16M12 4v16"/>'
};
const $=(h)=>{const t=document.createElement('template');t.innerHTML=h.trim();return t.content.firstChild;};
const fmtUSD=(c)=> (c==null?'—':(c<0?'-':'')+'$'+Math.abs(c/100).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2}));
const pct=(x,d=1)=> x==null?'—':(x*100).toFixed(d)+'%';
const signed=(x,d=1)=> x==null?'—':(x>0?'+':'')+(x*100).toFixed(d)+'%';
const sgn=(x)=> x==null?'':(x>=0?'pos':'neg');
const num=(x,d=3)=> x==null?'—':(+x).toFixed(d);
const ago=(iso)=>{if(!iso)return'—';const s=(Date.now()-Date.parse(iso))/1000;if(s<90)return Math.round(s)+'s ago';if(s<5400)return Math.round(s/60)+'m ago';return Math.round(s/3600)+'h ago';};

let STATE={overview:null,scopes:null,status:null};
let ROUTE=location.hash||'#/overview';

function svgIcon(k){return '<svg viewBox="0 0 24 24">'+(ICON[k]||ICON.overview)+'</svg>';}

// ---- SVG charts ----
function areaChart(pts,{h=150,pad=6,color='var(--green)',fill='rgba(55,245,160,.12)'}={}){
  if(!pts||pts.length<2)return '<div class="empty">no history yet</div>';
  const xs=pts.map((p,i)=>i), ys=pts.map(p=>p.v);
  const mn=Math.min(...ys), mx=Math.max(...ys), rng=(mx-mn)||1;
  const W=1000,H=h;
  const X=i=>pad+ i*(W-2*pad)/(xs.length-1);
  const Y=v=>pad+ (1-(v-mn)/rng)*(H-2*pad);
  let d='M'+X(0)+' '+Y(ys[0]); ys.forEach((v,i)=>{if(i)d+=' L'+X(i).toFixed(1)+' '+Y(v).toFixed(1);});
  const area=d+' L'+X(xs.length-1)+' '+(H-pad)+' L'+X(0)+' '+(H-pad)+' Z';
  const last=pts[pts.length-1];
  return '<svg class="chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="height:'+h+'px">'
    +'<defs><linearGradient id="ag" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="'+fill+'"/><stop offset="1" stop-color="transparent"/></linearGradient></defs>'
    +'<path d="'+area+'" fill="url(#ag)"/><path d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2.2" vector-effect="non-scaling-stroke"/>'
    +'<circle cx="'+X(xs.length-1)+'" cy="'+Y(last.v)+'" r="3.4" fill="'+color+'"/></svg>';
}
function lineChart(series,{h=150,pad=8}={}){
  // series: [{name,color,pts:[{v}], dash}] sharing an index axis, each normalized to its own range
  const any=series.find(s=>s.pts&&s.pts.length>1);
  if(!any)return '<div class="empty">not enough graded history</div>';
  const n=any.pts.length,W=1000,H=h;
  const X=i=>pad+i*(W-2*pad)/(n-1);
  let out='<svg class="chart" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" style="height:'+h+'px">';
  out+='<line x1="'+pad+'" y1="'+(H/2)+'" x2="'+(W-pad)+'" y2="'+(H/2)+'" stroke="var(--line)" stroke-width="1" vector-effect="non-scaling-stroke"/>';
  series.forEach(s=>{
    if(!s.pts||s.pts.length<2)return;
    const ys=s.pts.map(p=>p.v),mn=Math.min(...ys),mx=Math.max(...ys),rng=(mx-mn)||1;
    const Y=v=>pad+(1-(v-mn)/rng)*(H-2*pad);
    let d='M'+X(0)+' '+Y(ys[0]);ys.forEach((v,i)=>{if(i)d+=' L'+X(i).toFixed(1)+' '+Y(v).toFixed(1);});
    out+='<path d="'+d+'" fill="none" stroke="'+s.color+'" stroke-width="2.1" '+(s.dash?'stroke-dasharray="4 4" ':'')+'vector-effect="non-scaling-stroke"/>';
  });
  out+='</svg>';return out;
}

// ---- sidebar ----
function buildNav(){
  const nav=document.getElementById('nav');nav.innerHTML='';
  nav.appendChild(navItem('overview','Overview','#/overview',null));
  const v=(STATE.scopes&&STATE.scopes.verticals)||{};
  [['CRYPTO','crypto','coin'],['SPORTS','sports','ball']].forEach(([key,gicon,cicon])=>{
    const block=v[key];
    const grp=$('<div class="grp"><span>'+key+'</span><span>'+(block?pct(block.summary.hit_rate,0):'')+'</span></div>');
    nav.appendChild(grp);
    if(!block){nav.appendChild($('<div class="item child" style="color:var(--faint)">no data</div>'));return;}
    Object.keys(block.scopes).sort((a,b)=>(block.scopes[b].summary.n||0)-(block.scopes[a].summary.n||0)).forEach(lab=>{
      const sc=block.scopes[lab];
      const it=navItem(cicon,lab,'#/scope/'+key+'/'+lab,pct(sc.summary.hit_rate,0));
      it.classList.add('child');nav.appendChild(it);
    });
  });
}
function navItem(icon,label,href,tag){
  const a=$('<a class="item" href="'+href+'" tabindex="0">'+svgIcon(icon)+'<span>'+label+'</span>'+(tag?'<span class="tag">'+tag+'</span>':'')+'</a>');
  if(href===ROUTE)a.classList.add('active');
  return a;
}

// ---- views ----
function render(){
  const view=document.getElementById('view');
  const parts=ROUTE.replace('#/','').split('/');
  if(parts[0]==='scope'&&parts[1]&&parts[2])view.innerHTML=scopeView(parts[1],parts[2]);
  else view.innerHTML=overviewView();
  // stagger reveal
  [...view.querySelectorAll('.reveal')].forEach((el,i)=>el.style.animationDelay=(i*45)+'ms');
  buildNav();
}

function kpi(lab,val,cls,sub){
  return '<div class="card kpi reveal"><div class="lab">'+lab+'</div><div class="val '+(cls||'')+'">'+val+'</div>'+(sub?'<div class="sub">'+sub+'</div>':'')+'</div>';
}
function overviewView(){
  const o=STATE.overview;
  if(!o||o.error||o.bankroll_cents==null)return topbar('Overview','account & promotion ladder')+'<div class="card"><div class="empty">'+((o&&o.error)||'snapshot warming up — the overview refreshes every 20 min')+'</div></div>';
  const rts=o.realized_trade_statistics||{};
  const roiCls=o.account_roi>=0?'pos':'neg';
  let h=topbar('Overview','account & promotion ladder');
  h+='<div class="grid kpis" style="margin-bottom:var(--s3)">';
  h+='<div class="card kpi reveal"><div class="lab">Account <span class="badge"><span class="d"></span>paper</span></div><div class="val" data-flip>'+fmtUSD(o.bankroll_cents)+'</div><div class="sub">base '+fmtUSD(o.base_bankroll_cents)+'</div></div>';
  h+=kpi('Account ROI',signed(o.account_roi),roiCls,'since inception');
  h+=kpi('Open exposure',fmtUSD(o.exposure_cents),'amb','stage '+o.stage);
  h+=kpi('Realized P&amp;L',fmtUSD(o.realized_pnl_cents),sgn(o.realized_pnl_cents),(rts.trades||0)+' settled trades');
  h+='</div>';
  // balance chart
  const curve=(o.balance_curve||[]).map(p=>({v:p.bankroll_cents}));
  h+='<div class="card reveal" style="margin-bottom:var(--s3)"><h3>Balance curve <span class="r">'+(o.balance_curve||[]).length+' pts · paper $</span></h3>'
    +areaChart(curve,{h:168,color:o.account_roi>=0?'var(--green)':'var(--red)'})
    +'<div class="legend"><span><i style="background:var(--green)"></i>paper bankroll</span></div></div>';
  // realized stats strip
  h+='<div class="grid kpis" style="margin-bottom:var(--s3)">';
  h+=kpi('Win rate',pct(rts.win_rate),'','settled trades');
  h+=kpi('ROI on cost',signed(rts.roi_on_entry_cost),sgn(rts.roi_on_entry_cost));
  h+=kpi('Profit factor',num(rts.profit_factor,2),rts.profit_factor>=1?'pos':'neg');
  h+=kpi('Max drawdown',fmtUSD(rts.max_drawdown_cents),'amb');
  h+='</div>';
  // promotion ladder
  h+='<div class="grid cols2">';
  h+='<div class="card reveal"><h3>'+svgTrophy()+'Actively promoted</h3>'+promotedList(o.promoted)+'</div>';
  h+='<div class="card reveal"><h3>Close to promotion <span class="r">contested Brier edge</span></h3>'+closeList(o.close_to_promotion)+'</div>';
  h+='</div>';
  // active model
  h+='<div class="card reveal" style="margin-top:var(--s3)"><h3>Active model — fused sources <span class="r">weight</span></h3><div>'
    +((o.active_sources||[]).map(s=>'<span class="chip">'+s.source+' <b>'+num(s.weight,2)+'</b></span>').join('')||'<div class="empty">no weights</div>')+'</div></div>';
  return h;
}
function svgTrophy(){return '<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--amber)" stroke-width="1.7" style="vertical-align:-2px"><path d="M7 4h10v3a5 5 0 0 1-10 0zM7 5H4v2a3 3 0 0 0 3 3M17 5h3v2a3 3 0 0 1-3 3M9 20h6M12 12v8"/></svg>';}
function promotedList(arr){
  if(!arr||!arr.length)return '<div class="empty">0 promoted — every challenger still in evaluation<br><span style="color:var(--green-dim)">promotion to capital is operator-gated</span></div>';
  return '<div class="rank">'+arr.map(e=>'<div class="rowbar"><span class="nm">'+e.name+'</span><span class="pill yes">'+(e.execution_authority?'execution':e.auto_promote?'auto':'ready')+'</span><span class="mv">'+(e.contested_markets||0)+' mkts</span></div>').join('')+'</div>';
}
function closeList(arr){
  if(!arr||!arr.length)return '<div class="empty">no challengers near the line</div>';
  // gap: lower95 in [-0.05,0] -> fill toward 0. width = how close to promotion.
  return '<div class="rank">'+arr.map(e=>{
    const low=e.lower95==null?-0.05:e.lower95;
    const w=Math.max(4,Math.min(100,(1-(Math.min(0,low)/-0.05))*100));
    return '<div class="rowbar"><span class="nm" title="'+(e.blocker||'')+'">'+e.name+'</span>'
      +'<span class="track"><span class="fill amb" style="width:'+w.toFixed(0)+'%"></span></span>'
      +'<span class="mv '+(low>=0?'pos':'')+'">'+num(low,3)+'</span></div>';
  }).join('')+'</div>';
}

function scopeView(vert,label){
  const block=STATE.scopes&&STATE.scopes.verticals&&STATE.scopes.verticals[vert];
  const sc=block&&block.scopes&&block.scopes[label];
  if(!sc)return topbar(label,vert.toLowerCase())+'<div class="card"><div class="empty">no data for '+label+' yet</div></div>';
  const s=sc.summary;
  let h=topbar(label,vert.toLowerCase()+' · graded forecast quality');
  h+='<div class="grid kpis" style="margin-bottom:var(--s3)">';
  h+=kpi('Graded picks',(s.n||0).toLocaleString(),'', 'settled markets');
  h+=kpi('Hit rate',pct(s.hit_rate),s.hit_rate>=.5?'pos':'neg','directional');
  h+=kpi('Brier',num(s.brier),'', 'lower = sharper');
  h+=kpi('Edge vs market',signed(s.brier_edge,2),sgn(s.brier_edge),(s.contested_n||0)+' contested');
  h+=kpi('Open picks',(sc.picks?sc.picks.length:0),'amb','live now');
  h+='</div>';
  // progression
  const prog=sc.progression||[];
  const hitPts=prog.filter(p=>p.hit_rate!=null).map(p=>({v:p.hit_rate}));
  const brPts=prog.filter(p=>p.brier!=null).map(p=>({v:p.brier}));
  h+='<div class="card reveal" style="margin-bottom:var(--s3)"><h3>Progression <span class="r">'+prog.length+' windows, oldest→newest</span></h3>'
    +lineChart([{name:'hit',color:'var(--green)',pts:hitPts},{name:'brier',color:'var(--amber)',pts:brPts,dash:true}],{h:150})
    +'<div class="legend"><span><i style="background:var(--green)"></i>hit rate</span><span><i style="background:var(--amber)"></i>Brier (inverted feel)</span></div></div>';
  // accuracy vs market + picks
  h+='<div class="grid cols2">';
  h+='<div class="card reveal"><h3>Model vs market <span class="r">Brier, lower better</span></h3>'+accuracyBars(s)+'</div>';
  h+='<div class="card pad0 reveal"><h3 style="padding:var(--s3) var(--s3) var(--s2)">Current picks <span class="r">by edge</span></h3>'+picksTable(sc.picks)+'</div>';
  h+='</div>';
  return h;
}
function accuracyBars(s){
  if(s.market_brier==null)return '<div class="empty">no contested (market-priced) markets in window</div>';
  const mx=Math.max(s.brier,s.market_brier,0.25);
  const bar=(lab,v,cls)=>'<div class="rowbar" style="grid-template-columns:96px 1fr auto"><span class="nm">'+lab+'</span>'
    +'<span class="track" style="height:12px"><span class="fill '+cls+'" style="width:'+(v/mx*100).toFixed(0)+'%"></span></span>'
    +'<span class="mv">'+num(v)+'</span></div>';
  const better=s.brier<s.market_brier;
  return '<div class="rank">'+bar('model',s.brier,better?'':'amb')+bar('market',s.market_brier,'amb')
    +'</div><div class="sub" style="margin-top:10px;font-family:var(--mono);font-size:12px;color:'+(better?'var(--green)':'var(--red)')+'">'
    +(better?'▲ model beats the line by '+num(s.brier_edge,3)+' Brier':'▼ model trails the line by '+num(-s.brier_edge,3))+'</div>';
}
function picksTable(picks){
  if(!picks||!picks.length)return '<div class="empty">no open picks in this scope right now</div>';
  let h='<div style="max-height:320px;overflow:auto"><table><thead><tr><th>Market</th><th>Side</th><th>Model</th><th>Mkt</th><th>Edge¢</th></tr></thead><tbody>';
  picks.forEach(p=>{
    h+='<tr><td title="'+p.ticker+'">'+p.ticker+'</td>'
      +'<td><span class="pill '+(p.side&&p.side.toUpperCase().includes('NO')?'no':'yes')+'">'+(p.side||'')+'</span></td>'
      +'<td>'+num(p.prob,2)+'</td><td>'+(p.market==null?'—':num(p.market,2))+'</td>'
      +'<td class="'+(p.edge_cents>=0?'pos':'neg')+'">'+(p.edge_cents>0?'+':'')+num(p.edge_cents,1)+'</td></tr>';
  });
  return h+'</tbody></table></div>';
}
function topbar(title,crumb){
  const stamp=STATE.overview&&STATE.overview.generated_at;
  return '<div class="topbar"><h2>'+title+'</h2><span class="crumb">'+crumb+'</span><span class="spacer"></span>'
    +'<span class="stamp">updated '+ago(stamp)+'</span></div>';
}

// ---- data ----
async function poll(){
  try{
    const [ov,sc,st]=await Promise.all([
      fetch('/api/overview').then(r=>r.json()).catch(()=>null),
      fetch('/api/scopes').then(r=>r.json()).catch(()=>null),
      fetch('/api/status').then(r=>r.json()).catch(()=>null),
    ]);
    if(ov)STATE.overview=ov; if(sc)STATE.scopes=sc; if(st)STATE.status=st;
    const live=document.getElementById('live'),fs=document.getElementById('footstat');
    const fresh=ov&&ov.generated_at&&(Date.now()-Date.parse(ov.generated_at))<30*60*1000;
    live.className='dot'+(fresh?' live':'');
    fs.textContent=fresh?'live · '+ago(ov.generated_at):'stale snapshot';
    render();
  }catch(e){}
}
window.addEventListener('hashchange',()=>{ROUTE=location.hash||'#/overview';render();});
render();poll();setInterval(poll,20000);
</script>
</body></html>"""
