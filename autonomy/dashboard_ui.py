"""The loopback-only operator dashboard: "The Organism".

A full-bleed neural field renders persisted system evidence as a model cortex,
active-source satellites, and crypto/sports scope clusters. Cluster size,
brightness, staleness, pulses, and the field's health mood are bound to the same
seven read-only payloads used by the DOM. Calm data produces a calm scene; only
ambient dust is decorative. The operational-truth ribbon, all evidence panels,
and all accessibility semantics remain ordinary DOM content.

The scene uses raw WebGL2/WebGL1 with canvas-2D and static-gradient fallbacks.
It pauses while hidden and becomes one composed frame under
prefers-reduced-motion. The application stays vanilla and build-free, uses only
loopback-served assets, and never reads the ledger or contacts a broker from a
page request. Semantic green/red remains theme-invariant in all four themes.
"""
from __future__ import annotations

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en" data-theme="emerald" data-accent="emerald"><head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">
<title>DUMMY — operator board</title>
<link rel="icon" href="data:image/svg+xml,%3Csvg xmlns='http://www.w3.org/2000/svg' viewBox='0 0 64 64'%3E%3Crect width='64' height='64' rx='16' fill='%23081711'/%3E%3Cpath d='M18 14h14c11 0 18 7 18 18S43 50 32 50H18V14zm11 9v18h3c6 0 9-3 9-9s-3-9-9-9h-3z' fill='%232fe38f'/%3E%3C/svg%3E">
<style>
:root{
  --bg:#04100a; --bg-1:#071811; --panel:#081c13; --panel-2:#0b2418; --panel-3:#0e2c1d;
  --line:#123528; --line-2:#1c5038; --line-3:#2a6b4c; --glow:rgba(77,255,160,.20);
  --green:#2fe38f; --phos:#5cffab; --green-deep:#0f7a52;
  --amber:#ffc24d; --amber-deep:#8a5a12; --red:#ff6b7a; --cyan:#6fe0ff; --violet:#b79cff;
  --txt:#e8f6ef; --muted:#83a898; --faint:#537163;
  /* Theme surfaces change together; green/red remain stable win/loss semantics. */
  --acc:#2fe38f; --acc-2:#0f7a52; --acc-glow:rgba(77,255,160,.22); --acc-rgb:77,255,160;
  --line-rgb:18,53,40; --secondary-rgb:111,224,255; --surface-rgb:8,28,19;
  --card-top-rgb:8,28,19; --card-bottom-rgb:7,24,17;
  --side-top-rgb:7,24,17; --side-bottom-rgb:4,16,10;
  --overlay-rgb:2,8,5;
  --mark-ink:#04140d;
  --mono:"Cascadia Mono","Consolas",ui-monospace,monospace;
  --disp:"Bahnschrift","DIN Alternate Bold","Segoe UI Semibold","Segoe UI",sans-serif;
  --body:"Segoe UI",system-ui,-apple-system,sans-serif;
  --s1:6px; --s2:10px; --s3:16px; --s4:24px; --r:14px;
  --ease:cubic-bezier(.2,.8,.2,1); --spring:cubic-bezier(.16,1.1,.3,1);
}
html[data-theme=amber]{
  --bg:#120b03;--bg-1:#1a1106;--panel:#201408;--panel-2:#2b1a0a;--panel-3:#35200d;
  --line:#4a3014;--line-2:#704a1d;--line-3:#956425;--glow:rgba(255,194,77,.20);
  --txt:#fff4d8;--muted:#c0a677;--faint:#786646;--phos:#ffd56f;
  --acc:#ffc24d;--acc-2:#7a4e12;--acc-glow:rgba(255,194,77,.22);--acc-rgb:255,194,77;
  --line-rgb:74,48,20;--secondary-rgb:255,151,77;--surface-rgb:32,20,8;
  --card-top-rgb:32,20,8;--card-bottom-rgb:24,15,5;--side-top-rgb:26,17,6;--side-bottom-rgb:18,11,3;
  --overlay-rgb:12,7,2;--mark-ink:#211304;
}
html[data-theme=cyan]{
  --bg:#020e14;--bg-1:#061922;--panel:#071d27;--panel-2:#0a2733;--panel-3:#0d3342;
  --line:#123949;--line-2:#1a586e;--line-3:#287890;--glow:rgba(111,224,255,.20);
  --txt:#e8f8ff;--muted:#84afbd;--faint:#557581;--phos:#8eeaff;
  --acc:#6fe0ff;--acc-2:#12667a;--acc-glow:rgba(111,224,255,.22);--acc-rgb:111,224,255;
  --line-rgb:18,57,73;--secondary-rgb:47,227,143;--surface-rgb:7,29,39;
  --card-top-rgb:7,29,39;--card-bottom-rgb:5,23,31;--side-top-rgb:6,25,34;--side-bottom-rgb:2,14,20;
  --overlay-rgb:1,8,12;--mark-ink:#03151d;
}
html[data-theme=violet]{
  --bg:#0b0714;--bg-1:#151025;--panel:#18112a;--panel-2:#211638;--panel-3:#2b1c47;
  --line:#352751;--line-2:#544078;--line-3:#735ca0;--glow:rgba(183,156,255,.20);
  --txt:#f4efff;--muted:#ab99c6;--faint:#6f6086;--phos:#c9b5ff;
  --acc:#b79cff;--acc-2:#4a3a8a;--acc-glow:rgba(183,156,255,.24);--acc-rgb:183,156,255;
  --line-rgb:53,39,81;--secondary-rgb:111,224,255;--surface-rgb:24,17,42;
  --card-top-rgb:24,17,42;--card-bottom-rgb:18,12,33;--side-top-rgb:21,16,37;--side-bottom-rgb:11,7,20;
  --overlay-rgb:7,4,13;--mark-ink:#160d27;
}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:
    radial-gradient(1300px 760px at 82% -14%, rgba(var(--acc-rgb),.10), transparent 60%),
    radial-gradient(1000px 640px at -6% 112%, rgba(var(--secondary-rgb),.055), transparent 55%),
    var(--bg);
  color:var(--txt);font-family:var(--body);font-size:14.5px;line-height:1.5;
  -webkit-font-smoothing:antialiased;overflow:hidden}
/* neural organism + progressively simpler visual fallbacks */
#scene{position:fixed;inset:0;z-index:0;pointer-events:none}
#gl,#fx{position:absolute;inset:0;width:100%;height:100%;display:block}
#fx{display:none;opacity:.64}
body.no-gl #gl{display:none}
/* faint CRT scanline — static (no motion), very low contrast */
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:9;
  background:repeating-linear-gradient(0deg,rgba(0,0,0,.16) 0 1px,transparent 1px 3px);
  opacity:.12;mix-blend-mode:overlay}
a{color:inherit;text-decoration:none}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:var(--line-2);border-radius:8px;border:2px solid transparent;background-clip:padding-box}
::-webkit-scrollbar-thumb:hover{background:var(--line-3);background-clip:padding-box}
::-webkit-scrollbar-track{background:transparent}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px;border-radius:6px}

.skip{position:fixed;left:12px;top:10px;z-index:100;transform:translateY(-150%);padding:9px 13px;
  border-radius:8px;background:var(--txt);color:var(--bg);font-weight:700;transition:transform .16s}
.skip:focus{transform:translateY(0)}
#app{position:relative;z-index:1;display:grid;grid-template-columns:264px 1fr;height:100vh}

/* ---------- sidebar ---------- */
.side{position:relative;background:linear-gradient(180deg,rgba(var(--side-top-rgb),.86),rgba(var(--side-bottom-rgb),.92));
  backdrop-filter:blur(8px);border-right:1px solid var(--line);display:flex;flex-direction:column;min-height:0}
.side::after{content:"";position:absolute;top:0;right:0;width:1px;height:100%;
  background:linear-gradient(180deg,transparent,var(--line-2) 30%,var(--line-2) 70%,transparent)}
.brand{padding:var(--s4) var(--s3) var(--s3);display:flex;align-items:center;gap:11px;border-radius:10px}
.brand .mark{position:relative;width:36px;height:36px;border-radius:10px;display:grid;place-items:center;
  background:radial-gradient(circle at 32% 26%,var(--acc),var(--acc-2));
  box-shadow:0 0 22px var(--acc-glow),inset 0 1px 1px rgba(255,255,255,.35);
  color:var(--mark-ink);font-family:var(--disp);font-weight:700;font-size:19px}
.brand .mark::before{content:"";position:absolute;inset:-3px;border-radius:13px;
  border:1px solid rgba(var(--acc-rgb),.34);z-index:-1;opacity:.9}
.brand h1{margin:0;font-family:var(--disp);font-size:20px;letter-spacing:.16em;font-weight:700;
  text-shadow:0 0 18px var(--acc-glow)}
.brand .sub{font-size:9.5px;letter-spacing:.36em;color:var(--acc);text-transform:uppercase;opacity:.85}
.nav{position:relative;flex:1;overflow-y:auto;padding:var(--s2) var(--s2) var(--s4)}
.nav .glide{position:absolute;left:8px;width:calc(100% - 16px);height:38px;border-radius:10px;
  background:linear-gradient(90deg,rgba(var(--acc-rgb),.15),rgba(var(--acc-rgb),.03));
  border:1px solid var(--line-2);box-shadow:0 0 16px rgba(var(--acc-rgb),.10);
  transition:transform .34s var(--spring),height .2s,opacity .2s;opacity:0;pointer-events:none;z-index:0}
.nav .glide::before{content:"";position:absolute;left:0;top:8px;bottom:8px;width:3px;border-radius:3px;
  background:var(--acc);box-shadow:0 0 10px var(--acc)}
.grp{position:relative;margin-top:var(--s3);padding:0 var(--s2) var(--s1);font-size:9.5px;
  letter-spacing:.26em;text-transform:uppercase;color:var(--faint);display:flex;
  justify-content:space-between;align-items:center;z-index:1}
.item{position:relative;z-index:1;display:flex;align-items:center;gap:10px;padding:9px 11px;
  border-radius:10px;cursor:pointer;color:var(--muted);border:1px solid transparent;
  transition:color .16s,transform .16s}
.item svg{width:17px;height:17px;flex:none;stroke:currentColor;fill:none;stroke-width:1.7}
.item:hover{color:var(--txt);transform:translateX(2px)}
.item.active{color:var(--acc)}
.item.child{padding-left:16px;margin-left:12px;font-family:var(--mono);font-size:12.5px}
.item .tag{margin-left:auto;font-family:var(--mono);font-size:11px;color:var(--faint)}
.item.active .tag{color:var(--green)}
.side .foot{position:relative;z-index:1;border-top:1px solid var(--line);padding:var(--s2) var(--s3);
  display:grid;grid-template-columns:auto 1fr auto;align-items:center;gap:5px 8px;font-size:11px;color:var(--muted);min-height:45px}
.side .foot .kbd{display:none}
.side .foot .tubes{grid-column:2/4;justify-self:end}
.theme-label{font:700 8.5px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
.dot{width:8px;height:8px;border-radius:50%;background:var(--faint);flex:none;transition:.3s}
.dot.live{background:var(--acc);box-shadow:0 0 10px var(--acc);animation:pulse 2.4s infinite}
@keyframes pulse{50%{opacity:.35}}
.tubes{margin-left:auto;display:flex;gap:6px}
.tube{width:12px;height:12px;border-radius:50%;cursor:pointer;border:1px solid rgba(255,255,255,.15);
  transition:transform .16s,box-shadow .16s;padding:0;background:var(--c)}
.tube:hover{transform:scale(1.18)}
.tube[aria-pressed=true]{box-shadow:0 0 0 2px var(--bg),0 0 0 3px var(--c),0 0 10px var(--c)}
.kbd{font-family:var(--mono);font-size:9.5px;color:var(--faint);border:1px solid var(--line);
  border-radius:5px;padding:1px 5px;background:var(--panel)}

/* ---------- stage ---------- */
.stage{position:relative;overflow-y:auto;min-height:0;padding:0 var(--s4) var(--s4);scroll-behavior:smooth}
.modechip{font-family:var(--mono);font-size:9px;font-weight:700;letter-spacing:.12em;text-transform:uppercase;
  border:1px solid var(--line-2);border-radius:999px;padding:3px 7px;color:var(--muted);background:var(--panel)}
.modechip.shadow{color:var(--amber);border-color:var(--amber-deep);background:rgba(255,194,77,.06)}
.modechip.live-auth{color:var(--red);border-color:rgba(255,107,122,.55);background:rgba(255,107,122,.08)}

#view{animation:swap .32s var(--ease);padding-top:var(--s3);max-width:1680px;margin:0 auto}
@keyframes swap{from{opacity:0;transform:translateY(8px)}}
.topbar{display:flex;align-items:center;gap:14px;margin-bottom:var(--s3);min-height:38px}
.topbar h2{margin:0;font-family:var(--disp);font-size:27px;letter-spacing:.02em;text-shadow:0 0 22px var(--acc-glow)}
.topbar .crumb{font-size:10.5px;letter-spacing:.24em;text-transform:uppercase;color:var(--faint)}
.topbar .spacer{flex:1}
.stamp{font-family:var(--mono);font-size:11px;color:var(--muted);display:flex;align-items:center;gap:7px}
.stamp .beat{width:6px;height:6px;border-radius:50%;background:var(--acc);box-shadow:0 0 8px var(--acc);animation:pulse 2.4s infinite}
.top-actions{display:flex;align-items:center;gap:7px}
.ghostbtn{appearance:none;border:1px solid var(--line-2);background:rgba(var(--surface-rgb),.78);color:var(--muted);
  min-height:34px;border-radius:8px;padding:6px 10px;font:600 11px var(--body);letter-spacing:.02em;cursor:pointer;
  transition:color .15s,border-color .15s,background .15s,transform .15s}
.ghostbtn:hover{color:var(--txt);border-color:var(--line-3);background:var(--panel-2)}
.ghostbtn:active{transform:translateY(1px)}
.ghostbtn .key{font:9px var(--mono);color:var(--faint);margin-left:6px}

/* operational truth bar: the first answer on every screen */
.opsbar{display:grid;grid-template-columns:auto minmax(260px,1fr) auto auto;align-items:center;gap:14px;
  margin-bottom:var(--s3);padding:13px 14px;border:1px solid var(--line-2);border-radius:12px;
  background:linear-gradient(90deg,rgba(255,194,77,.07),rgba(var(--surface-rgb),.82) 42%,rgba(var(--surface-rgb),.88));
  box-shadow:inset 3px 0 0 var(--amber)}
.opsbar.live-auth{border-color:rgba(255,107,122,.48);box-shadow:inset 3px 0 0 var(--red);
  background:linear-gradient(90deg,rgba(255,107,122,.09),rgba(var(--surface-rgb),.88) 46%)}
.opsbar.wait{box-shadow:inset 3px 0 0 var(--faint);background:rgba(var(--surface-rgb),.78)}
.opsicon{width:36px;height:36px;border-radius:9px;display:grid;place-items:center;color:var(--amber);
  background:rgba(255,194,77,.09);border:1px solid rgba(255,194,77,.24)}
.opsbar.live-auth .opsicon{color:var(--red);background:rgba(255,107,122,.09);border-color:rgba(255,107,122,.28)}
.opsicon svg{width:18px;height:18px;fill:none;stroke:currentColor;stroke-width:1.8}
.opseye{font-size:9px;letter-spacing:.19em;text-transform:uppercase;color:var(--faint);margin-bottom:1px}
.opstitle{font:700 15px var(--disp);letter-spacing:.02em;color:var(--txt)}
.opsdetail{font-size:11.5px;color:var(--muted);margin-top:1px}
.opsfacts{display:flex;align-items:stretch;gap:4px}
.opsfact{min-width:88px;padding:3px 11px;border-left:1px solid var(--line)}
.opsfact span{display:block;font-size:8.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--faint)}
.opsfact b{display:block;margin-top:2px;font:600 11px var(--mono);color:var(--txt);white-space:nowrap}
.opsfact b.ok{color:var(--green)}.opsfact b.warn{color:var(--amber)}.opsfact b.bad{color:var(--red)}

.outcome-brief{display:flex;align-items:center;gap:12px;margin:-2px 0 var(--s3);padding:11px 13px;
  border-radius:10px;border:1px solid rgba(255,107,122,.30);background:rgba(255,107,122,.055)}
.outcome-brief.good{border-color:rgba(47,227,143,.30);background:rgba(47,227,143,.055)}
.outcome-brief .verdict{font:700 13px var(--disp);color:var(--red);white-space:nowrap}
.outcome-brief.good .verdict{color:var(--green)}
.outcome-brief .explain{font-size:12px;color:var(--muted)}
.outcome-brief .explain b{color:var(--txt);font-weight:600}
.section-head{display:flex;align-items:baseline;gap:12px;margin:var(--s4) 0 var(--s2)}
.section-head h2{margin:0;font:700 18px var(--disp);letter-spacing:.02em}
.section-head p{margin:0;color:var(--faint);font-size:11.5px}
.metric-note{margin:-1px 0 15px;padding:9px 11px;border-left:2px solid var(--amber-deep);
  border-radius:0 7px 7px 0;background:rgba(255,194,77,.045);color:var(--muted);font-size:11.5px}

.grid{display:grid;gap:var(--s3)}
.kpis{grid-template-columns:repeat(auto-fit,minmax(172px,1fr))}
.cols2{grid-template-columns:1fr 1fr}
.hero{grid-template-columns:1.25fr .85fr 1fr;margin-bottom:var(--s3)}
.overview-hero{grid-template-areas:"acct gauge summary"}
.overview-hero .acct{grid-area:acct}.overview-hero .gaugecard{grid-area:gauge}.overview-hero .summarycard{grid-area:summary}
@media(max-width:1040px){.hero{grid-template-columns:1fr 1fr}.hero:not(.overview-hero) .gaugecard{grid-column:span 2}
  .overview-hero{grid-template-areas:"acct summary" "gauge gauge"}.overview-hero .gaugecard{max-height:220px}}
@media(max-width:920px){.cols2,.hero{grid-template-columns:1fr}.hero:not(.overview-hero) .gaugecard{grid-column:auto}
  .overview-hero{grid-template-areas:"acct" "summary" "gauge"}.overview-hero .gaugecard{max-height:210px}
  #app{grid-template-columns:72px 1fr}
  .brand{padding-left:18px}.brand h1,.brand .sub,.item span:not(.tag),.grp span:last-child,.foot #footstat,.foot .kbd,.foot .theme-label{display:none}
  .item{justify-content:center}.item.child{padding-left:11px;margin-left:0}.item .tag{display:none}
  .grp{height:9px;margin:11px 8px 3px;padding:0;border-top:1px solid var(--line)}.grp span{display:none}
  .side .foot{grid-template-columns:1fr;padding:8px 4px;justify-items:center}.side .foot .dot{display:none}
  .side .foot .modechip{font-size:7px;padding:2px 4px}.side .foot .tubes{display:grid;grid-template-columns:repeat(2,12px);gap:4px;grid-column:1;justify-self:center;margin:0}
  .opsbar{grid-template-columns:auto 1fr auto}.opsfacts{display:none}}
@media(max-width:680px){.stage{padding:0 12px 18px}.topbar{align-items:flex-start;flex-wrap:wrap}.topbar .crumb{order:3;width:100%}
  .stamp{margin-left:auto}.top-actions .ghostbtn:first-child{display:none}.opsbar{grid-template-columns:auto 1fr;padding:11px}.opsbar>.ghostbtn{display:none}
  .opsdetail{font-size:11px}.card{padding:13px}.kpis{grid-template-columns:1fr 1fr}}
@media(max-width:480px){
  #app{display:block;height:100vh}
  .stage{height:calc(100vh - 64px);padding:0 10px 18px}
  .side{position:fixed;z-index:20;inset:auto 0 0;height:64px;min-height:64px;border:0;border-top:1px solid var(--line)}
  .side::after,.side .brand,.side .grp,.side .foot,.nav .glide{display:none}
  .nav{display:flex;align-items:center;gap:4px;overflow-x:auto;overflow-y:hidden;padding:7px 8px}
  .item,.item.child{flex:0 0 48px;height:48px;margin:0;padding:0;justify-content:center}
  .item span,.item .tag{display:none}
  .item:hover{transform:none}
  .topbar h2{font-size:22px}
  .kpis{grid-template-columns:1fr}
}

.card{position:relative;background:linear-gradient(180deg,rgba(var(--card-top-rgb),.80),rgba(var(--card-bottom-rgb),.90));
  backdrop-filter:blur(6px) saturate(1.08);
  border:1px solid var(--line);border-radius:var(--r);padding:var(--s3);overflow:hidden;
  transition:transform .18s var(--ease),border-color .2s,box-shadow .2s}
.card::before{content:"";position:absolute;inset:0 0 auto 0;height:1px;z-index:2;
  background:linear-gradient(90deg,transparent,var(--line-2),transparent);opacity:.7}
/* cursor specular highlight (tilt) */
.card::after{content:"";position:absolute;inset:0;border-radius:inherit;pointer-events:none;opacity:0;z-index:1;
  background:radial-gradient(220px circle at var(--mx,50%) var(--my,50%),rgba(var(--acc-rgb),.10),transparent 62%);
  transition:opacity .25s}
.card:hover{border-color:var(--line-2);box-shadow:0 10px 30px -18px rgba(0,0,0,.7)}
.card.tilt{transform:perspective(950px) rotateX(var(--rx,0)) rotateY(var(--ry,0));
  transition:transform .08s linear;box-shadow:0 20px 55px -26px rgba(0,0,0,.85)}
.card.tilt::after{opacity:1}
.card.pad0{padding:0}
.card>*{position:relative;z-index:2}
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
.val.phos{color:var(--phos)}
.badge{display:inline-flex;align-items:center;gap:5px;font-size:9px;letter-spacing:.18em;
  text-transform:uppercase;padding:3px 8px;border-radius:20px;border:1px solid var(--amber-deep);color:var(--amber)}
.badge .d{width:5px;height:5px;border-radius:50%;background:var(--amber);box-shadow:0 0 6px var(--amber)}
.badge.off{border-color:var(--red);color:var(--red)}
.badge.off .d{background:var(--red);box-shadow:0 0 6px var(--red)}
.item.off{opacity:.5}
.item.off:hover{opacity:.85}
.item.off .tag{color:var(--faint)}

/* hero band */
.acct{display:flex;flex-direction:column;justify-content:space-between;gap:var(--s2)}
.acct .big{font-family:var(--mono);font-size:38px;font-weight:600;letter-spacing:-1px;line-height:1;color:var(--phos);
  text-shadow:0 0 22px var(--glow)}
.acct .big.neg{color:var(--red);text-shadow:0 0 18px rgba(255,107,122,.18)}
.acct .big.pos{color:var(--green)}
.acct .spark{margin-top:6px}
.mini{display:grid;grid-template-columns:1fr;gap:9px}
.mini .row{display:flex;align-items:baseline;justify-content:space-between;gap:10px;
  padding-bottom:8px;border-bottom:1px solid rgba(var(--line-rgb),.5)}
.mini .row:last-child{border-bottom:0;padding-bottom:0}
.mini .k{font-size:9.5px;letter-spacing:.16em;text-transform:uppercase;color:var(--faint)}
.mini .vv{font-family:var(--mono);font-size:17px}
.gaugecard{display:flex;flex-direction:column;align-items:center;justify-content:center}
.gauge{position:relative;width:100%;max-width:210px}
.gauge .rd{stroke:var(--line-2);fill:none;stroke-width:11;stroke-linecap:round}
.gauge .val-arc{fill:none;stroke-width:11;stroke-linecap:round;filter:drop-shadow(0 0 8px currentColor);
  animation:sweep 1.1s var(--ease) forwards}
@keyframes sweep{from{stroke-dashoffset:var(--len)}}
.gauge .gc{position:absolute;inset:0;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:2px}
.gauge .gc .n{font-family:var(--mono);font-size:26px;font-weight:600;letter-spacing:-.5px}
.gauge .gc .l{font-size:9px;letter-spacing:.22em;text-transform:uppercase;color:var(--faint)}
.gtick{stroke:var(--line-2);stroke-width:2}

/* split-flap flip counter — each char flips when its value changes */
.flip{display:inline-flex}
.flip .flap{position:relative;display:inline-block;transform-origin:50% 50%;animation:flap .52s var(--ease) both;
  backface-visibility:hidden}
.flip .flap::after{content:"";position:absolute;left:0;right:0;top:50%;height:1px;
  background:rgba(0,0,0,.55);box-shadow:0 1px 0 rgba(255,255,255,.05)}
@keyframes flap{
  0%{transform:rotateX(-88deg) translateY(-2px);opacity:0;color:var(--acc)}
  55%{opacity:1;color:var(--acc);text-shadow:0 0 14px var(--acc-glow)}
  100%{transform:rotateX(0);opacity:1}}

table{width:100%;border-collapse:collapse;font-family:var(--mono);font-size:12.5px}
thead th{position:sticky;top:0;background:var(--panel);z-index:1}
th{text-align:right;font-family:var(--body);font-size:9.5px;letter-spacing:.14em;text-transform:uppercase;
  color:var(--faint);font-weight:600;padding:8px 10px;border-bottom:1px solid var(--line)}
th:first-child,td:first-child{text-align:left}
td{padding:8px 10px;border-bottom:1px solid rgba(var(--line-rgb),.55);white-space:nowrap}
tbody tr{transition:background .14s,box-shadow .14s}
tbody tr:hover{background:var(--panel-2);box-shadow:inset 2px 0 0 var(--acc)}
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

/* bounded, persisted system-health and edge-quality evidence */
.ops-intel-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:var(--s3);
  margin-bottom:var(--s3);align-items:start}
.ops-evidence-card{min-width:0}
.evidence-head{display:flex;align-items:flex-start;justify-content:space-between;gap:12px;margin-bottom:11px}
.evidence-head h3{margin:0}.evidence-state{flex:none;padding:4px 8px;border:1px solid var(--line-2);
  border-radius:999px;background:var(--panel-2);color:var(--faint);font:700 9px var(--mono);
  letter-spacing:.08em;text-transform:uppercase}
.evidence-state.ok{color:var(--green);border-color:rgba(47,227,143,.4);background:rgba(47,227,143,.07)}
.evidence-state.warn{color:var(--amber);border-color:rgba(255,194,77,.4);background:rgba(255,194,77,.07)}
.evidence-state.bad{color:var(--red);border-color:rgba(255,107,122,.4);background:rgba(255,107,122,.07)}
.evidence-kpis{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:7px;margin-bottom:12px}
.evidence-kpi{min-width:0;padding:9px;border:1px solid var(--line);border-radius:9px;background:var(--panel-2)}
.evidence-kpi span{display:block;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;
  color:var(--faint);font:8.5px var(--mono);letter-spacing:.1em;text-transform:uppercase}
.evidence-kpi b{display:block;margin-top:4px;overflow-wrap:anywhere;color:var(--txt);font:650 13px var(--mono)}
.evidence-kpi b.ok{color:var(--green)}.evidence-kpi b.warn{color:var(--amber)}.evidence-kpi b.bad{color:var(--red)}
.evidence-section{margin-top:12px;padding-top:11px;border-top:1px solid var(--line)}
.evidence-section-head{display:flex;align-items:baseline;justify-content:space-between;gap:10px;margin-bottom:6px}
.evidence-section-head b{color:var(--muted);font:700 10px var(--disp);letter-spacing:.12em;text-transform:uppercase}
.evidence-section-head span{color:var(--faint);font:9.5px var(--mono)}
.evidence-list{display:flex;flex-direction:column;gap:6px}
.evidence-item{display:grid;grid-template-columns:minmax(0,1fr) auto;gap:3px 10px;padding:8px 9px;
  border:1px solid var(--line);border-radius:8px;background:rgba(var(--surface-rgb),.55)}
.evidence-main{min-width:0;color:var(--txt);font:600 11px var(--mono);overflow-wrap:anywhere}
.evidence-time{color:var(--faint);font:9.5px var(--mono);white-space:nowrap}
.evidence-meta{grid-column:1/-1;color:var(--muted);font-size:10.5px;line-height:1.45;overflow-wrap:anywhere}
.severity{display:inline-block;margin-right:6px;padding:1px 5px;border:1px solid var(--line-2);
  border-radius:5px;color:var(--faint);font:700 8px var(--mono);letter-spacing:.06em;text-transform:uppercase}
.severity.critical{color:var(--red);border-color:rgba(255,107,122,.45)}
.severity.warning{color:var(--amber);border-color:rgba(255,194,77,.45)}
.severity.info{color:var(--cyan);border-color:rgba(111,224,255,.4)}
.severity.bad{color:var(--red);border-color:rgba(255,107,122,.45)}
.severity.warn{color:var(--amber);border-color:rgba(255,194,77,.45)}
.severity.ok{color:var(--green);border-color:rgba(47,227,143,.4)}
.reason-count{color:var(--acc);font:700 11px var(--mono)}
.evidence-empty{padding:12px;border:1px dashed var(--line-2);border-radius:8px;color:var(--faint);
  background:rgba(var(--surface-rgb),.35);font:10.5px var(--mono);line-height:1.55}
.evidence-context{display:flex;flex-wrap:wrap;gap:5px 12px;margin:-3px 0 10px;padding:7px 9px;
  border:1px solid var(--line);border-radius:8px;background:rgba(var(--surface-rgb),.35);
  color:var(--faint);font:9.5px var(--mono);line-height:1.45}
.evidence-context b{color:var(--muted);font-weight:650}
.evidence-context .stale{color:var(--amber)}.evidence-context .current{color:var(--green)}
.evidence-panes{display:grid;grid-template-columns:repeat(3,minmax(0,1fr));gap:7px}
.evidence-pane{min-width:0;padding:9px;border:1px solid var(--line);border-radius:9px;
  background:rgba(var(--surface-rgb),.55)}
.evidence-pane .pane-label{display:block;color:var(--faint);font:8.5px var(--mono);
  letter-spacing:.1em;text-transform:uppercase}
.evidence-pane b{display:block;margin-top:5px;color:var(--txt);font:650 11.5px var(--mono);
  overflow-wrap:anywhere}
.evidence-pane p{margin:5px 0 0;color:var(--muted);font-size:10.5px;line-height:1.45}
.evidence-pane.ok b{color:var(--green)}.evidence-pane.warn b{color:var(--amber)}
.evidence-pane.bad b{color:var(--red)}
.edge-bins{display:grid;grid-template-columns:repeat(auto-fit,minmax(88px,1fr));gap:6px}
.edge-bin{padding:8px;border:1px solid var(--line);border-radius:8px;background:rgba(var(--surface-rgb),.45)}
.edge-bin span{display:block;color:var(--faint);font:9px var(--mono);overflow-wrap:anywhere}
.edge-bin b{display:block;margin-top:4px;color:var(--txt);font:650 12px var(--mono)}
@media(max-width:1180px){.ops-intel-grid{grid-template-columns:1fr}}
@media(max-width:620px){.evidence-kpis{grid-template-columns:repeat(2,minmax(0,1fr))}
  .evidence-item{grid-template-columns:1fr}.evidence-time{white-space:normal}.evidence-meta{grid-column:1}
  .evidence-panes{grid-template-columns:1fr}}

/* accuracy & improvement telemetry */
.acc-hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(140px,1fr));gap:var(--s3);margin-bottom:var(--s3)}
.acc-stat .lab{font-size:9.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--faint)}
.acc-stat .val{font-family:var(--mono);font-size:24px;font-weight:600;margin-top:4px;line-height:1.1;min-height:27px}
.acc-stat .sub{font-family:var(--mono);font-size:11px;color:var(--faint);margin-top:2px}
.trend{font-family:var(--mono);font-size:15px;font-weight:600;display:inline-flex;align-items:baseline;gap:7px}
.trend .dd{font-size:11px;font-weight:400;color:var(--muted)}
.trend.up,.td.up{color:var(--green)} .trend.dn,.td.dn{color:var(--red)}
.trend.flat,.td.flat{color:var(--muted)} .trend.thin,.td.thin{color:var(--faint)}
.heatwrap{overflow-x:auto;margin:0 calc(-1*var(--s3)) calc(-1*var(--s3));padding:0 var(--s3) var(--s3)}
table.heat{border-collapse:separate;border-spacing:4px;font-family:var(--mono);font-size:11.5px;width:100%}
table.heat th{position:static;background:transparent;text-align:center;color:var(--faint);font-family:var(--body);
  font-size:9px;letter-spacing:.12em;text-transform:uppercase;padding:3px 6px;border:0}
table.heat th:first-child,table.heat td.hs{text-align:left}
td.hs{color:var(--txt);white-space:nowrap;font-size:12px;padding-right:10px}
td.hc{border:1px solid var(--line);border-radius:7px;padding:6px 8px;text-align:center;min-width:66px;
  background:var(--panel-2);transition:transform .12s,border-color .12s;cursor:default}
td.hc:hover{transform:translateY(-1px);border-color:var(--line-2)}
td.hc.empty2{background:transparent;border-style:dashed;opacity:.4}
td.hc .he{font-weight:600}
td.hc .td{font-size:11px;margin-left:3px}
/* bet-type rankings tabs */
.bt-tabs{display:flex;gap:6px;flex-wrap:wrap;margin-bottom:var(--s2)}
.bt-tab{font-family:var(--mono);font-size:11.5px;padding:5px 11px;border-radius:8px;cursor:pointer;
  background:var(--panel-2);border:1px solid var(--line);color:var(--muted);transition:.15s;text-transform:capitalize}
.bt-tab:hover{border-color:var(--line-2);color:var(--txt)}
.bt-tab.on{background:rgba(var(--acc-rgb),.14);border-color:var(--line-3);color:var(--acc)}
.bt-tab .c{display:inline-grid;place-items:center;min-width:18px;margin-left:6px;padding:1px 4px;border-radius:999px;
  background:rgba(var(--line-rgb),.5);color:var(--faint);font-size:9.5px;line-height:1.25}
.bt-tab.on .c{background:rgba(var(--acc-rgb),.12);color:var(--acc)}
.bt-panel{display:none} .bt-panel.on{display:block}
.guide-filter-note{display:flex;align-items:flex-start;justify-content:space-between;gap:16px;margin:0 0 9px;
  padding:8px 10px;border:1px solid var(--line);border-radius:8px;background:rgba(var(--acc-rgb),.035);color:var(--muted);font-size:11.5px;line-height:1.45}
.guide-filter-note b{color:var(--txt);font-weight:650}.guide-filter-note .counts{flex:0 0 auto;color:var(--faint);font-family:var(--mono);font-size:10.5px}
.table-more{text-align:center!important;color:var(--faint);font-family:var(--body);white-space:normal!important;padding:11px!important}
.res-ok{color:var(--green)} .res-no{color:var(--red)}
/* versioned, forward-only tier evidence */
.tier-card{overflow:hidden}.tier-card .tier-intro{display:flex;align-items:flex-start;justify-content:space-between;gap:14px;margin:-2px 0 12px}
.tier-card .tier-intro p{margin:0;color:var(--muted);font-size:11.5px;max-width:780px}.tier-state{flex:none;font:700 9.5px var(--mono);letter-spacing:.1em;text-transform:uppercase;border:1px solid var(--line-2);border-radius:999px;padding:4px 8px;color:var(--faint);background:var(--panel-2)}
.tier-state.ready{color:var(--green);border-color:rgba(47,227,143,.42);background:rgba(47,227,143,.07)}
.tier-state.stale{color:var(--amber);border-color:rgba(255,194,77,.42);background:rgba(255,194,77,.07)}
.tier-dist{display:grid;grid-template-columns:repeat(5,minmax(105px,1fr));gap:8px;margin-bottom:12px}
.tier-count{position:relative;overflow:hidden;border:1px solid var(--line);border-radius:10px;padding:9px 10px;background:var(--panel-2)}
.tier-count::after{content:"";position:absolute;left:0;right:0;bottom:0;height:2px;background:var(--tier-color,var(--faint));opacity:.75}
.tier-count .tc-head{display:flex;align-items:center;justify-content:space-between;gap:8px}.tier-count .tc-n{font:650 18px var(--mono);color:var(--txt)}
.tier-count .tc-share{font:10px var(--mono);color:var(--faint)}
.tier-badge{display:inline-grid;place-items:center;min-width:28px;height:20px;padding:0 7px;border:1px solid var(--line-2);border-radius:6px;background:var(--panel-3);font:750 10px var(--mono);letter-spacing:.08em;color:var(--muted)}
.tier-badge.a{color:var(--green);border-color:rgba(47,227,143,.42);background:rgba(47,227,143,.08)}
.tier-badge.b{color:var(--cyan);border-color:rgba(111,224,255,.38);background:rgba(111,224,255,.07)}
.tier-badge.c{color:var(--amber);border-color:rgba(255,194,77,.42);background:rgba(255,194,77,.07)}
.tier-badge.watch{color:var(--faint);border-style:dashed}.tier-badge.unattributed{min-width:88px;color:var(--red);border-color:rgba(255,107,122,.34);border-style:dotted;background:rgba(255,107,122,.055)}.tier-sample{display:block;margin-top:2px;font:9.5px var(--mono);color:var(--faint)}
.tier-table-wrap{overflow-x:auto;margin:0 calc(-1*var(--s3));padding:0 var(--s3)}.tier-table th:first-child,.tier-table td:first-child{position:sticky;left:0;background:var(--panel);z-index:1}.tier-table tbody tr:hover td:first-child{background:var(--panel-2)}
.tier-horizon-head{display:flex;align-items:baseline;justify-content:space-between;gap:12px;margin:14px 0 6px;padding-top:11px;border-top:1px solid var(--line)}
.tier-horizon-head b{font:700 12px var(--disp);color:var(--txt)}.tier-horizon-head span{font:10px var(--mono);color:var(--faint)}
.tier-horizon-table .scope-row td:first-child{font-weight:700;color:var(--txt)}.tier-horizon-table .tier-detail td:first-child{padding-left:24px;color:var(--muted)}
.tier-foot{display:flex;justify-content:space-between;gap:12px;margin-top:10px;color:var(--faint);font:10.5px var(--mono);line-height:1.5}.tier-foot b{color:var(--muted);font-weight:600}
@media(max-width:680px){.tier-dist{grid-template-columns:repeat(2,1fr)}.tier-card .tier-intro,.tier-foot{display:block}.tier-state{display:inline-block;margin-top:7px}}
/* day's games, click to expand */
.games{display:flex;flex-direction:column;gap:8px;max-height:440px;overflow:auto}
.game{flex:0 0 auto;border:1px solid var(--line);border-radius:10px;overflow:hidden;transition:border-color .15s}
.game:hover{border-color:var(--line-2)}
.ghead{appearance:none;width:100%;color:inherit;border:0;display:grid;grid-template-columns:52px minmax(180px,1fr) auto auto;gap:10px;
  align-items:center;padding:10px 12px;cursor:pointer;font-family:var(--mono);font-size:12.5px;background:var(--panel-2);text-align:left}
.ghead:hover{background:var(--panel-3)}
.ghead .gx{color:var(--faint);transition:transform .2s}
.ghead .gx b{color:var(--acc);font-weight:700;margin-right:4px}
.ghead .gm{min-width:0}
.ghead .gm small{display:block;color:var(--faint);font-weight:400;margin-top:3px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.game.open .ghead .gx{transform:rotate(90deg);color:var(--acc)}
.ghead .gc{color:var(--faint);font-size:11px} .ghead .ge{display:flex;align-items:center;justify-content:flex-end;gap:7px;color:var(--acc);font-size:11.5px;min-width:146px;text-align:right}
.ghead .ge .guide-value{white-space:nowrap}.game-tier-summary{display:inline-flex;align-items:center;justify-content:flex-end;flex-wrap:wrap;gap:4px}
.game-tier-chip{display:inline-flex;align-items:center;gap:3px}.game-tier-chip .tier-badge{height:18px;min-width:24px;padding:0 5px;font-size:9px}.game-tier-chip .tier-n{color:var(--muted);font:9.5px var(--mono)}
.gbody{display:none;padding:2px 8px 8px}
.game.open .gbody{display:block}
.game.open .ghead{border-bottom:1px solid var(--line)}
@media(max-width:680px){.ghead{grid-template-columns:46px minmax(120px,1fr) auto}.ghead .gc{display:none}.games{max-height:none}.daily-guide .bt-tabs{flex-wrap:nowrap;overflow-x:auto;padding:1px 1px 6px;scroll-snap-type:x proximity}.daily-guide .bt-tab{flex:0 0 auto;scroll-snap-align:start}.guide-filter-note{display:block}.guide-filter-note .counts{display:block;margin-top:4px}}

/* crypto horizon coverage */
.horizon-grid{display:grid;grid-template-columns:repeat(4,minmax(150px,1fr));gap:10px}
.horizon{padding:12px;border:1px solid var(--line);border-radius:10px;background:var(--panel-2)}
.horizon .hh{display:flex;align-items:center;justify-content:space-between;gap:8px;font:700 12px var(--mono);color:var(--txt)}
.horizon .hs{margin-top:7px;color:var(--muted);font-size:11.5px;line-height:1.45}
.horizon .hm{display:flex;justify-content:space-between;gap:8px;margin-top:9px;padding-top:8px;border-top:1px solid var(--line);font:11px var(--mono);color:var(--faint)}
.horizon .state{font-size:9px;letter-spacing:.08em;text-transform:uppercase;color:var(--acc)}
.horizon .state.wait{color:var(--amber)}
@media(max-width:1080px){.horizon-grid{grid-template-columns:repeat(2,minmax(150px,1fr))}}
@media(max-width:560px){.horizon-grid{grid-template-columns:1fr}}

/* glossary and operating model */
.how-flow{display:grid;grid-template-columns:repeat(6,1fr);gap:8px;margin-top:12px;counter-reset:how}
.how-step{position:relative;padding:14px 12px 12px;border:1px solid var(--line);border-radius:10px;background:var(--panel-2);min-height:110px}
.how-step::before{counter-increment:how;content:counter(how);display:grid;place-items:center;width:22px;height:22px;border-radius:50%;background:rgba(var(--acc-rgb),.14);color:var(--acc);font:700 11px var(--mono);margin-bottom:8px}
.how-step b{display:block;font:700 12px var(--disp);color:var(--txt);margin-bottom:4px}.how-step span{font-size:11px;color:var(--muted)}
.glossary-tools{display:flex;align-items:center;gap:12px;margin:var(--s3) 0}.glossary-tools label{font:700 10px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}
.glossary-search{flex:1;min-width:0;padding:10px 12px;border:1px solid var(--line-2);border-radius:9px;background:var(--panel);color:var(--txt);font:13px var(--mono);outline:0}
.glossary-search::placeholder{color:var(--faint)}.glossary-search:focus{border-color:var(--acc);box-shadow:0 0 0 3px rgba(var(--acc-rgb),.09)}
.glossary-grid{display:grid;grid-template-columns:repeat(3,minmax(220px,1fr));gap:10px}
.gloss{padding:13px 14px;border:1px solid var(--line);border-radius:10px;background:linear-gradient(180deg,var(--panel-2),var(--panel));min-height:112px}
.gloss[hidden]{display:none}.gloss .gt{display:flex;align-items:center;justify-content:space-between;gap:8px;margin-bottom:7px}.gloss h4{margin:0;font:700 13px var(--disp);color:var(--txt)}
.gloss .cat{font:700 8px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--acc)}.gloss p{margin:0;color:var(--muted);font-size:12px;line-height:1.55}
.glossary-empty{display:none;padding:28px;text-align:center;color:var(--faint);font-family:var(--mono)}
.glossary-empty.show{display:block}
@media(max-width:1180px){.how-flow{grid-template-columns:repeat(3,1fr)}.glossary-grid{grid-template-columns:repeat(2,minmax(210px,1fr))}}
@media(max-width:680px){.how-flow,.glossary-grid{grid-template-columns:1fr}.glossary-tools{align-items:stretch;flex-direction:column;gap:6px}}

/* model arsenal — stored, redacted proof and two-key paid-call truth */
.arsenal-hero{display:grid;grid-template-columns:minmax(0,1.45fr) minmax(300px,.75fr);gap:12px;margin-bottom:var(--s3)}
.arsenal-lead{overflow:hidden;background:
  radial-gradient(640px 220px at 0 0,rgba(var(--acc-rgb),.14),transparent 65%),
  linear-gradient(180deg,rgba(var(--card-top-rgb),.92),rgba(var(--card-bottom-rgb),.96))}
.arsenal-kicker{font:700 9px var(--mono);letter-spacing:.2em;text-transform:uppercase;color:var(--acc)}
.arsenal-title{margin:7px 0 5px;font:700 clamp(24px,3vw,36px)/1.05 var(--disp);letter-spacing:-.02em;color:var(--txt)}
.arsenal-copy{max-width:760px;color:var(--muted);font-size:12.5px;line-height:1.65}
.proof-banner{display:flex;align-items:center;gap:11px;margin-top:15px;padding:11px 12px;border:1px solid var(--line-2);border-radius:10px;background:rgba(var(--acc-rgb),.07)}
.proof-orb{width:32px;height:32px;flex:0 0 auto;display:grid;place-items:center;border-radius:50%;background:rgba(var(--acc-rgb),.13);border:1px solid rgba(var(--acc-rgb),.4);color:var(--acc);font:700 12px var(--mono);box-shadow:0 0 22px var(--acc-glow)}
.proof-banner b{display:block;color:var(--txt);font:700 12px var(--disp)}.proof-banner span{display:block;margin-top:2px;color:var(--faint);font:10.5px var(--mono)}
.arsenal-facts{display:grid;grid-template-columns:1fr 1fr;gap:8px}.arsenal-fact{padding:11px;border:1px solid var(--line);border-radius:9px;background:var(--panel-2)}
.arsenal-fact .afl{font:700 8.5px var(--mono);letter-spacing:.13em;text-transform:uppercase;color:var(--faint)}
.arsenal-fact .afv{margin-top:5px;color:var(--txt);font:700 12px var(--mono);overflow-wrap:anywhere}.arsenal-fact .afv.ok{color:var(--green)}.arsenal-fact .afv.lock{color:var(--amber)}
.gate-strip{display:grid;grid-template-columns:repeat(3,1fr);gap:10px;margin-bottom:var(--s3)}
.gate-box{position:relative;padding:13px 14px;border:1px solid var(--line);border-radius:10px;background:var(--panel-2)}
.gate-box::before{content:attr(data-step);position:absolute;right:10px;top:9px;color:var(--faint);font:700 10px var(--mono)}
.gate-box .gl{font:700 9px var(--mono);letter-spacing:.12em;text-transform:uppercase;color:var(--faint)}
.gate-box .gv{margin-top:7px;font:700 17px var(--disp);color:var(--txt)}.gate-box .gv.on{color:var(--green)}.gate-box .gv.off{color:var(--amber)}
.gate-box .gd{margin-top:3px;color:var(--muted);font-size:10.5px}
.arsenal-grid{display:grid;grid-template-columns:repeat(2,minmax(0,1fr));gap:10px;margin-bottom:var(--s3)}
.model-unit{position:relative;padding:15px;border:1px solid var(--line);border-radius:12px;background:linear-gradient(155deg,var(--panel-2),var(--panel));overflow:hidden}
.model-unit::after{content:attr(data-index);position:absolute;right:-5px;top:-15px;color:rgba(var(--acc-rgb),.07);font:700 86px var(--disp);line-height:1;pointer-events:none}
.unit-head{position:relative;z-index:1;display:flex;align-items:flex-start;justify-content:space-between;gap:12px}.unit-name{font:700 16px var(--disp);color:var(--txt)}
.unit-slug{margin-top:3px;color:var(--acc);font:10px var(--mono);overflow-wrap:anywhere}.unit-role{position:relative;z-index:1;margin:12px 0;color:var(--muted);font-size:12px;line-height:1.55;min-height:38px}
.unit-meta{position:relative;z-index:1;display:flex;flex-wrap:wrap;gap:6px;padding-top:10px;border-top:1px solid var(--line)}
.unit-meta span{padding:4px 7px;border-radius:6px;background:rgba(var(--surface-rgb),.8);color:var(--faint);font:9px var(--mono)}.unit-meta b{color:var(--muted);font-weight:600}
.truth-pill{display:inline-flex;align-items:center;gap:5px;padding:4px 7px;border:1px solid var(--line-2);border-radius:999px;color:var(--muted);font:700 8.5px var(--mono);letter-spacing:.06em;text-transform:uppercase;white-space:nowrap}
.truth-pill::before{content:"";width:5px;height:5px;border-radius:50%;background:var(--faint)}.truth-pill.ok{color:var(--green);border-color:var(--green-deep)}.truth-pill.ok::before{background:var(--green);box-shadow:0 0 7px var(--green)}
.truth-pill.warn{color:var(--amber);border-color:var(--amber-deep)}.truth-pill.warn::before{background:var(--amber)}.truth-pill.bad{color:var(--red);border-color:#70303a}.truth-pill.bad::before{background:var(--red)}
.authority-row{display:grid;grid-template-columns:repeat(3,1fr);gap:9px}.authority-lock{padding:12px;border:1px solid var(--green-deep);border-radius:9px;background:rgba(47,227,143,.045)}
.authority-lock b{display:flex;align-items:center;justify-content:space-between;color:var(--txt);font:700 11px var(--disp)}.authority-lock b span{color:var(--green);font:700 9px var(--mono)}.authority-lock p{margin:5px 0 0;color:var(--muted);font-size:10.5px;line-height:1.45}
.authority-lock.danger{border-color:#70303a;background:rgba(255,107,122,.07)}.authority-lock.danger b span{color:var(--red)}.authority-lock.unknown{border-color:var(--amber-deep);background:rgba(255,194,77,.05)}.authority-lock.unknown b span{color:var(--amber)}
.arsenal-link{display:flex;align-items:center;justify-content:space-between;gap:12px;cursor:pointer}.arsenal-link:hover{border-color:var(--line-3)}.arsenal-link .go{color:var(--acc);font:700 11px var(--mono)}
@media(max-width:980px){.arsenal-hero{grid-template-columns:1fr}.arsenal-grid{grid-template-columns:1fr}}
@media(max-width:680px){.gate-strip,.authority-row{grid-template-columns:1fr}.arsenal-facts{grid-template-columns:1fr}}

/* complete public capability catalog — static descriptions routed to read-only surfaces */
.ability-catalog{margin:var(--s4) 0}.ability-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}
.ability-tile{display:block;min-width:0;padding:14px;border:1px solid var(--line);border-radius:9px;background:var(--panel);color:var(--txt);transition:border-color .16s ease,transform .16s ease}
a.ability-tile:hover{border-color:var(--line-3);transform:translateY(-1px);text-decoration:none}
.ability-tile.crypto{border-color:rgba(65,199,208,.28);background:linear-gradient(145deg,rgba(35,68,70,.38),var(--panel))}
.ability-tile .ak{font:700 8.5px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--faint)}
.ability-tile.crypto .ak{color:#67d7de}.ability-tile .an{margin-top:7px;font:700 13px var(--disp);letter-spacing:.01em}
.ability-tile .ad{margin-top:5px;color:var(--muted);font-size:10.5px;line-height:1.5}
.ability-tile .ap{display:block;margin-top:9px;padding-top:7px;border-top:1px solid var(--line);color:var(--green);font:700 9px var(--mono)}
@media(max-width:1180px){.ability-grid{grid-template-columns:repeat(3,minmax(0,1fr))}}
@media(max-width:780px){.ability-grid{grid-template-columns:repeat(2,minmax(0,1fr))}}
@media(max-width:480px){.ability-grid{grid-template-columns:1fr}}

/* charts */
.cwrap{position:relative}
.chart{width:100%;display:block}
.chart .draw{stroke-dasharray:1;stroke-dashoffset:1;animation:draw 1.25s var(--ease) forwards}
@keyframes draw{to{stroke-dashoffset:0}}
.chart .dot{animation:pop .3s var(--ease) 1.1s both}
@keyframes pop{from{r:0;opacity:0}}
.grid-l{stroke:var(--line);stroke-width:1;opacity:.5}
.tick{fill:var(--faint);font-family:var(--mono);font-size:9px}
.cross{position:absolute;top:0;bottom:0;width:1px;background:var(--acc);opacity:0;
  box-shadow:0 0 8px var(--acc);pointer-events:none;transition:opacity .12s}
.ctip{position:absolute;transform:translate(-50%,-140%);background:var(--panel-3);border:1px solid var(--line-2);
  border-radius:8px;padding:5px 9px;font-family:var(--mono);font-size:11px;white-space:nowrap;opacity:0;
  pointer-events:none;transition:opacity .12s;box-shadow:0 8px 20px -10px #000;z-index:3}
.ctip b{color:var(--acc)}

/* command palette */
.cmdk{position:fixed;inset:0;z-index:40;display:none;align-items:flex-start;justify-content:center;
  padding-top:14vh;background:rgba(var(--overlay-rgb),.62);backdrop-filter:blur(3px)}
.cmdk.open{display:flex;animation:fade .18s var(--ease)}
@keyframes fade{from{opacity:0}}
.cmdk .box{width:min(560px,92vw);background:linear-gradient(180deg,var(--panel-2),var(--bg-1));
  border:1px solid var(--line-2);border-radius:var(--r);box-shadow:0 30px 80px -30px #000,0 0 0 1px rgba(var(--acc-rgb),.12);
  overflow:hidden;animation:rise .28s var(--spring)}
.cmdk input{width:100%;border:0;outline:0;background:transparent;color:var(--txt);
  font-family:var(--mono);font-size:15px;padding:15px 17px;border-bottom:1px solid var(--line)}
.cmdk input::placeholder{color:var(--faint)}
.cmdk .list{max-height:46vh;overflow-y:auto;padding:6px}
.cmdk .opt{display:flex;align-items:center;gap:11px;padding:10px 12px;border-radius:9px;cursor:pointer;color:var(--muted)}
.cmdk .opt .oh{margin-left:auto;font-size:10px;letter-spacing:.16em;text-transform:uppercase;color:var(--faint)}
.cmdk .opt svg{width:16px;height:16px;stroke:currentColor;fill:none;stroke-width:1.7}
.cmdk .opt.sel,.cmdk .opt:hover{background:rgba(var(--acc-rgb),.12);color:var(--txt)}
.cmdk .opt.sel{box-shadow:inset 2px 0 0 var(--acc)}
.cmdk .foot2{display:flex;gap:14px;padding:9px 14px;border-top:1px solid var(--line);
  font-size:10px;color:var(--faint);font-family:var(--mono)}

/* immutable market-observer charts */
.chart-controls{display:flex;flex-wrap:wrap;gap:7px;align-items:center;margin-bottom:var(--s3)}
.chart-controls .label{font:10px var(--mono);letter-spacing:.14em;text-transform:uppercase;color:var(--faint);margin-right:2px}
.chart-choice{appearance:none;border:1px solid var(--line-2);background:var(--panel);color:var(--muted);
  border-radius:8px;padding:7px 10px;font:11px var(--mono);cursor:pointer}
.chart-choice:hover,.chart-choice.on{border-color:var(--acc);color:var(--txt);background:rgba(var(--acc-rgb),.10)}
.market-chart-frame{position:relative;min-height:430px;border:1px solid var(--line);
  border-radius:var(--r);overflow:hidden;background:rgba(2,8,14,.72)}
#marketChart{height:430px;width:100%}.market-chart-overlay{position:absolute;top:9px;left:9px;z-index:3;
  display:flex;flex-wrap:wrap;gap:5px;max-width:75%;pointer-events:none}
.indicator-chip{padding:4px 7px;border:1px solid rgba(var(--acc-rgb),.28);border-radius:6px;
  background:rgba(2,8,14,.84);color:var(--muted);font:10px var(--mono);backdrop-filter:blur(8px)}
.indicator-chip b{color:var(--txt);font-weight:650}.observer-meta{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:9px}
.observer-meta .cell{min-width:0;padding:10px 11px;border:1px solid var(--line);border-radius:9px;background:var(--panel)}
.observer-meta .cell span{display:block;font:9px var(--mono);letter-spacing:.13em;text-transform:uppercase;color:var(--faint)}
.observer-meta .cell b{display:block;margin-top:5px;font:11px var(--mono);color:var(--muted);overflow-wrap:anywhere}
.observer-banner{display:flex;align-items:flex-start;gap:10px;padding:11px 13px;border:1px solid var(--amber-deep);
  border-radius:9px;background:rgba(255,184,77,.05);color:var(--muted);font-size:11px;line-height:1.55}
.observer-banner b{color:var(--amber)}.observer-attribution{margin-top:9px;color:var(--faint);font:10px var(--mono)}
.observer-attribution a{color:var(--muted)}.observer-patterns{display:flex;flex-wrap:wrap;gap:6px}
@media(max-width:760px){.observer-meta{grid-template-columns:repeat(2,minmax(0,1fr))}
  .market-chart-frame{display:flex;flex-direction:column;min-height:376px;height:auto}
  #marketChart{order:2;flex:0 0 330px;min-height:330px;height:330px}
  .market-chart-overlay{position:static;order:1;flex-wrap:nowrap;max-width:none;overflow-x:auto;
    padding:8px;pointer-events:auto;scrollbar-width:thin}
  .indicator-chip{flex:0 0 auto}}

/* snapshot shockwave — one-shot phosphor ripple when new data lands */
#shock{position:fixed;inset:0;z-index:7;pointer-events:none;opacity:0}
#shock.go{animation:shock 1.1s var(--ease)}
@keyframes shock{0%{opacity:.9;background:radial-gradient(circle at 50% 42%,rgba(var(--acc-rgb),.16),transparent 8%)}
  100%{opacity:0;background:radial-gradient(circle at 50% 42%,rgba(var(--acc-rgb),0),transparent 120%)}}

/* ---------- organism layout ---------- */
.stage{overflow-x:hidden}
.opsbar{position:sticky;top:12px;z-index:30;border-radius:14px;
  background:linear-gradient(90deg,rgba(255,194,77,.10),rgba(var(--surface-rgb),.72) 42%,rgba(var(--surface-rgb),.80));
  backdrop-filter:blur(16px)}
.opsbar.live-auth{background:linear-gradient(90deg,rgba(255,107,122,.12),rgba(var(--surface-rgb),.80) 46%)}
.card{background:linear-gradient(180deg,rgba(var(--card-top-rgb),.68),rgba(var(--card-bottom-rgb),.76));
  backdrop-filter:none;border:1px solid rgba(var(--line-rgb),.9);
  box-shadow:0 18px 44px rgba(0,0,0,.34),inset 0 1px 0 rgba(255,255,255,.05)}
.topbar{position:relative;z-index:2}
.dockband{margin-top:var(--s4);padding:var(--s3);border:1px solid var(--line);border-radius:18px;
  background:rgba(var(--surface-rgb),.52);backdrop-filter:blur(18px)}
.chart{filter:drop-shadow(0 0 6px rgba(var(--acc-rgb),.25))}
.dock{margin-left:0;max-width:1100px}
.dock .card{background:linear-gradient(180deg,rgba(var(--card-top-rgb),.74),rgba(var(--card-bottom-rgb),.82))}
.gate-box,.authority-lock{background:rgba(var(--surface-rgb),.66);border-color:rgba(var(--line-rgb),.9)}
.arsenal-lead,.gloss{background:linear-gradient(180deg,rgba(var(--card-top-rgb),.70),rgba(var(--card-bottom-rgb),.78))}
@media(min-width:1201px){.dock{margin-left:min(38vw,640px)}}
@media(min-width:921px){
  #app{grid-template-columns:auto 1fr}
  .side{width:78px;overflow-x:hidden;transition:width .28s var(--ease)}
  .side:hover,.side:focus-within{width:264px}
  .nav{overflow-x:hidden}
  .side .item,.side .foot{white-space:nowrap}
  .side:not(:hover):not(:focus-within) .brand>div:last-child,
  .side:not(:hover):not(:focus-within) .item>span,
  .side:not(:hover):not(:focus-within) .grp>span,
  .side:not(:hover):not(:focus-within) .foot>*:not(.dot){display:none}
  .side:not(:hover):not(:focus-within) .item{justify-content:center}
  .side:not(:hover):not(:focus-within) .item.child{margin-left:0;padding-left:11px}
}

@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}
  .chart .draw{stroke-dashoffset:0}.fill{width:var(--w,60%)!important}
  .gauge .val-arc{stroke-dashoffset:var(--off)!important}}
</style>
</head><body>
<a class="skip" href="#main">Skip to dashboard</a>
<div id="scene" role="img" aria-label="Live map of Dummy scopes, signals, and engine health"><canvas id="gl" aria-hidden="true"></canvas><canvas id="fx" aria-hidden="true" style="display:none"></canvas></div>
<div id="shock"></div>
<div id="app">
  <aside class="side" aria-label="Primary navigation">
    <a class="brand" href="#/overview" aria-label="DUMMY overview">
      <div class="mark" aria-hidden="true">D</div>
      <div><h1>DUMMY</h1><div class="sub">operator board</div></div>
    </a>
    <nav class="nav" id="nav" aria-label="Markets"><div class="glide" id="glide"></div></nav>
    <div class="foot" role="status" aria-live="polite">
      <span class="dot" id="live" aria-hidden="true"></span><span id="footstat">connecting…</span>
      <span class="modechip" id="sideMode">wait</span>
      <span class="kbd" title="command palette">⌘K</span>
      <span class="theme-label">Theme</span>
      <span class="tubes" id="tubes" role="group" aria-label="Application theme"></span>
    </div>
  </aside>
  <main class="stage" id="main" tabindex="-1"><div id="view"></div></main>
</div>
<div class="cmdk" id="cmdk" role="dialog" aria-modal="true" aria-label="Jump to a market scope" aria-hidden="true">
  <div class="box">
    <input id="cmdq" type="text" aria-label="Filter market scopes" placeholder="Jump to a scope…  (type to filter)" autocomplete="off" spellcheck="false">
    <div class="list" id="cmdlist" role="listbox" aria-label="Available scopes"></div>
    <div class="foot2"><span>↑↓ navigate</span><span>⏎ open</span><span>esc close</span><span>t · cycle theme</span></div>
  </div>
</div>
<script src="/assets/vendor/lightweight-charts/5.2.0/lightweight-charts.standalone.production.js"
  integrity="sha384-q1KYLSKHgBnW5tWYGGR8+6YV4/iPy31dILoF2I1OD7XiVUvHEp/TaxIQVmB0j3R2"></script>
<script>
const ICON={
 overview:'<path d="M3 3h7v7H3zM14 3h7v4h-7zM14 10h7v11h-7zM3 14h7v7H3z"/>',
 arsenal:'<rect x="3" y="5" width="18" height="14" rx="3"/><path d="M8 9h2v2H8zM14 9h2v2h-2zM8 15h8M12 2v3M12 19v3M1 12h2M21 12h2"/>',
 glossary:'<path d="M4 5.5A3.5 3.5 0 0 1 7.5 2H11v17H7.5A3.5 3.5 0 0 0 4 22zM20 5.5A3.5 3.5 0 0 0 16.5 2H13v17h3.5A3.5 3.5 0 0 1 20 22z"/>',
 chart:'<path d="M4 4v16h16"/><path d="M7 14l3-4 3 2 4-6"/><path d="M7 7v10M17 4v13"/>',
 coin:'<circle cx="12" cy="12" r="8.5"/><path d="M12 7.5v9M9.5 9.5h4a1.8 1.8 0 0 1 0 3.6h-4"/>',
 ball:'<circle cx="12" cy="12" r="8.5"/><path d="M4 12h16M12 4v16"/>',
 market:'<path d="M4 19V9M10 19V5M16 19v-7M22 19H2"/>',
 weather:'<path d="M8 17h9a4 4 0 0 0 0-8 6 6 0 0 0-11.4 1.5A3.5 3.5 0 0 0 8 17z"/>'
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
const flip=(text)=>'<span class="flip" aria-label="'+esc(String(text))+'">'+String(text).split('').map((c,i)=>'<span class="flap" aria-hidden="true" style="animation-delay:'+(i*32)+'ms">'+(c===' '?'&nbsp;':esc(c))+'</span>').join('')+'</span>';
const REDUCE=matchMedia('(prefers-reduced-motion:reduce)').matches;

let STATE={overview:null,scopes:null,status:null,walk:null,board:null,boardMeta:null,boardFetchOk:false,arsenal:null,tierPerformance:null,tierPerformanceFetchOk:false,
  marketChart:{asset:'BTC',timeframe:'1h',data:null,error:null,pending:false,loadedKey:''},
  connection:{pending:true,error:null}};
let ROUTE=location.hash||'#/overview';
let lastSig='';
let POLLING=false;
let ACTIVE_MARKET_CHART=null;
let LAZY_GUIDE={};
let GUIDE_FILTERS={};
// Year-round capability fallback, not a claim that a league has games today.
// The APIs publish the same server-authored roster; this local copy keeps every
// league navigable during the initial load or a degraded artifact refresh.
const SPORTS_ROSTER=['MLB','WNBA','NBA','NFL','NHL','NCAAF','NCAAMB'];
const VERTICAL_META={CRYPTO:['coin','Crypto'],SPORTS:['ball','Sports']};
function sportsRoster(){
  const fromScopes=STATE.scopes&&STATE.scopes.sports_leagues;
  const fromBoard=STATE.boardMeta&&STATE.boardMeta.sports_leagues;
  const published=Array.isArray(fromScopes)?fromScopes:(Array.isArray(fromBoard)?fromBoard:[]);
  return [...new Set([...SPORTS_ROSTER,...published.map(x=>String(x).toUpperCase()).filter(Boolean)])];
}
function verticalIcon(vert){return (VERTICAL_META[vert]||['market'])[0];}

function svgIcon(k){return '<svg viewBox="0 0 24 24">'+(ICON[k]||ICON.overview)+'</svg>';}

// ---------- charts ----------
function spark(pts,{w=180,h=40,color='var(--acc)'}={}){
  if(!pts||pts.length<2)return '';
  const ys=pts.map(p=>+p),mn=Math.min(...ys),mx=Math.max(...ys),rng=(mx-mn)||1,n=ys.length,pad=3;
  const X=i=>pad+i*(w-2*pad)/(n-1),Y=v=>pad+(1-(v-mn)/rng)*(h-2*pad);
  let d='M'+X(0).toFixed(1)+' '+Y(ys[0]).toFixed(1);ys.forEach((v,i)=>{if(i)d+=' L'+X(i).toFixed(1)+' '+Y(v).toFixed(1);});
  const area=d+' L'+X(n-1).toFixed(1)+' '+(h-pad)+' L'+X(0).toFixed(1)+' '+(h-pad)+' Z';
  return '<svg class="chart spark" viewBox="0 0 '+w+' '+h+'" preserveAspectRatio="none" style="height:'+h+'px">'
    +'<defs><linearGradient id="sg" x1="0" y1="0" x2="0" y2="1"><stop offset="0" stop-color="'+color+'" stop-opacity=".22"/><stop offset="1" stop-color="'+color+'" stop-opacity="0"/></linearGradient></defs>'
    +'<path d="'+area+'" fill="url(#sg)"/>'
    +'<path class="draw" pathLength="1" d="'+d+'" fill="none" stroke="'+color+'" stroke-width="2" vector-effect="non-scaling-stroke" stroke-linecap="round" stroke-linejoin="round"/></svg>';
}
// radial gauge: v is a signed fraction (roi/edge), mapped across [-span,span] on a 240deg arc
function gauge(v,{span=0.5,label='ROI',fmt=signed}={}){
  const R=80,CX=100,CY=100,A=240,rad=Math.PI/180;
  const pol=(deg)=>[CX+R*Math.cos(deg*rad),CY+R*Math.sin(deg*rad)];
  const a0=150,a1=390; // 240deg, gap at bottom
  const p0=pol(a0),p1=pol(a1);
  const track='M'+p0[0].toFixed(1)+' '+p0[1].toFixed(1)+' A '+R+' '+R+' 0 1 1 '+p1[0].toFixed(1)+' '+p1[1].toFixed(1);
  const clamp=Math.max(-span,Math.min(span,v==null?0:v));
  const t=(clamp+span)/(2*span);               // 0..1 fill fraction
  const arcLen=Math.PI*R*(A/180);              // px length of 240deg arc
  const col=(v==null||v>=0)?'var(--green)':'var(--red)';
  // minor ticks every 60deg across the sweep
  let ticks='';for(let a=a0;a<=a1+1;a+=60){const o=pol(a),i2=[CX+(R-9)*Math.cos(a*rad),CY+(R-9)*Math.sin(a*rad)];
    ticks+='<line class="gtick" x1="'+o[0].toFixed(1)+'" y1="'+o[1].toFixed(1)+'" x2="'+i2[0].toFixed(1)+'" y2="'+i2[1].toFixed(1)+'"/>';}
  return '<div class="gauge">'
    +'<svg viewBox="0 0 200 200" style="width:100%;display:block">'
    +'<path class="rd" d="'+track+'"/>'+ticks
    +'<path class="val-arc" d="'+track+'" stroke="'+col+'" color="'+col+'" '
    +'style="stroke-dasharray:'+arcLen.toFixed(1)+';stroke-dashoffset:'+((1-t)*arcLen).toFixed(1)+';--len:'+arcLen.toFixed(1)+';--off:'+((1-t)*arcLen).toFixed(1)+'"/>'
    +'</svg>'
    +'<div class="gc"><div class="n '+(v==null?'':(v>=0?'pos':'neg'))+'">'+flip(fmt(v))+'</div><div class="l">'+esc(label)+'</div></div></div>';
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
  nav.appendChild(navItem('chart','Crypto Charts','#/charts',null));
  nav.appendChild(navItem('arsenal','Model Arsenal','#/arsenal',null));
  nav.appendChild(navItem('glossary','Glossary & how it works','#/glossary',null));
  const v=(STATE.scopes&&STATE.scopes.verticals)||{};
  // SPORTS is a stable product surface, not a reflection of the current
  // snapshot's row keys.  Render it immediately and keep it through outages.
  const keys=['CRYPTO','SPORTS'].filter(key=>key==='SPORTS'||v[key]);
  keys.forEach(key=>{
    const cicon=verticalIcon(key);
    const block=v[key]||{scopes:{},summary:{}};
    const summary=block.summary||{};
    nav.appendChild($('<div class="grp"><span>'+key+'</span><span>'+(summary.hit_rate==null?'':pct(summary.hit_rate,0))+'</span></div>'));
    const labels=scopeLabels(key,block);
    if(!labels.length){nav.appendChild($('<div class="item child" style="color:var(--faint)"><span>no data</span></div>'));return;}
    labels.forEach(lab=>{
      const sc=block&&block.scopes&&block.scopes[lab];
      const season=sc&&sc.season_status;
      const off=sc?(sc.in_season===false||season==='off'):false;
      const tag=sc&&sc.summary&&sc.summary.hit_rate!=null?pct(sc.summary.hit_rate,0):(off?'off':(season==='upcoming'?'pre':'·'));
      const display=lab===key?'All '+((VERTICAL_META[key]||['',titleCase(key)])[1]):lab;
      const it=navItem(cicon,display,'#/scope/'+key+'/'+lab,tag);
      it.classList.add('child');if(off)it.classList.add('off');
      nav.appendChild(it);
    });
  });
  requestAnimationFrame(()=>moveGlide());
}
// SPORTS always shows the whole roster (union with whatever the snapshot has);
// crypto lists exactly what settled. Order: graded volume first, then in-season
// before off-season, then alphabetical.
function scopeLabels(key,block){
  if(key==='SPORTS'){
    const have=block&&block.scopes?Object.keys(block.scopes):[];
    return [...new Set([...have,...sportsRoster()])].sort((a,b)=>{
      const sa=block&&block.scopes&&block.scopes[a],sb=block&&block.scopes&&block.scopes[b];
      const ia=sa?sa.in_season!==false:true,ib=sb?sb.in_season!==false:true;
      if(ia!==ib)return ia?-1:1;                 // live leagues lead
      const na=(sa&&sa.summary&&sa.summary.n)||0,nb=(sb&&sb.summary&&sb.summary.n)||0;
      if(nb!==na)return nb-na;                    // then graded volume
      return a<b?-1:1;
    });
  }
  return block&&block.scopes?Object.keys(block.scopes).sort((a,b)=>((block.scopes[b].summary.n)||0)-((block.scopes[a].summary.n)||0)):[];
}
function navItem(icon,label,href,tag){
  const a=$('<a class="item" href="'+href+'" tabindex="0" title="'+esc(label)+'" aria-label="'+esc(label)+'">'+svgIcon(icon)+'<span>'+label+'</span>'+(tag?'<span class="tag">'+tag+'</span>':'')+'</a>');
  if(href===ROUTE){a.classList.add('active');a.setAttribute('aria-current','page');}
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
function statusSummary(){
  const st=STATE.status||{},hb=st.heartbeat||{},wd=st.watchdog||{},session=st.session||{},controls=st.live_controls||(STATE.overview&&STATE.overview.live_controls)||{};
  const mode=String(hb.mode||'').toUpperCase();
  const activeSession=!!(session.present&&!session.expired&&String(session.mode||'').toUpperCase()==='LIVE');
  const contractAuth=controls.execution_authority===true;
  const liveAuth=mode==='LIVE'&&activeSession&&contractAuth;
  const known=!!st.generated_at;
  const ages=st.data_ages||{},accountAge=ages.live_account||{};
  // The old SHADOW heartbeat is retained only as historical observer data. It
  // has no sports-grade or live authority, so its age must not degrade the
  // operational ribbon after paper/shadow retirement.
  const accountFresh=accountAge.stale===false;
  const healthy=known&&wd.healthy===true&&accountFresh;
  const stale=Object.entries(ages).filter(([k,v])=>['live_account','sports_model_seed'].includes(k)&&v&&v.stale);
  const auth=session.expired?'SESSION EXPIRED':(liveAuth?'ACTIVE':(contractAuth?'ARMED / NO SESSION':'LOCKED'));
  if(!known)return {tone:'wait',mode:'WAIT',title:'Connecting to execution state',detail:'Loading the latest engine health, authorization, and evidence freshness.',healthy:false,accountFresh:false,auth:'CHECKING',stale:[],liveAuth:false};
  if(liveAuth)return {tone:'live-auth',mode:'LIVE',title:'Live execution authorized — capital at risk',detail:'The engine reports an active live session. Confirm risk limits before taking action.',healthy,accountFresh,auth,stale,liveAuth:true};
  const title=accountFresh?'Live account observer active — submit locked':'Live submit locked';
  const blocker=controls.blocker||'No active controlled-live authority and session';
  return {tone:'',mode:'LOCKED',title,detail:blocker+'. Paper/shadow results are retired and cannot enable or block LIVE.',healthy,accountFresh,auth,stale,liveAuth:false};
}
function statusRibbon(){
  const s=statusSummary(),failure=STATE.connection&&STATE.connection.error;
  const health=failure?'DEGRADED':(s.healthy?'HEALTHY':'CHECK');
  const healthClass=failure?'bad':(s.healthy?'ok':'warn');
  const staleLabel=s.stale.length?s.stale.length+' STALE':(s.accountFresh?'CURRENT':'UNAVAILABLE');
  const staleClass=s.stale.length||!s.accountFresh?'warn':'ok';
  const staleTitle=s.stale.length?' title="Stale: '+esc(s.stale.map(([k])=>k.replace(/_/g,' ')).join(', '))+'"':'';
  const icon=s.liveAuth?'<path d="M12 3v10M8 7l4-4 4 4M5 11v9h14v-9"/>':'<rect x="5" y="10" width="14" height="10" rx="2"/><path d="M8 10V7a4 4 0 0 1 8 0v3"/>';
  return '<section class="opsbar '+s.tone+'" role="status" aria-live="polite" aria-label="Execution authority">'
    +'<div class="opsicon" aria-hidden="true"><svg viewBox="0 0 24 24">'+icon+'</svg></div>'
    +'<div><div class="opseye">Execution authority</div><div class="opstitle">'+esc(s.title)+'</div><div class="opsdetail">'+esc(failure?failure:s.detail)+'</div></div>'
    +'<div class="opsfacts"><div class="opsfact"><span>Engine</span><b class="'+healthClass+'">'+health+'</b></div>'
    +'<div class="opsfact"><span>Live auth</span><b class="'+(s.liveAuth?'bad':'warn')+'">'+esc(s.auth)+'</b></div>'
    +'<div class="opsfact"'+staleTitle+'><span>Evidence</span><b class="'+staleClass+'">'+staleLabel+'</b></div></div>'
    +'<button class="ghostbtn" type="button" data-action="readiness" aria-label="Review deployment readiness">Readiness</button></section>';
}
function render(){
  const view=document.getElementById('view');
  const parts=ROUTE.replace('#/','').split('/');
  disposeMarketChart();
  view.style.animation='none';void view.offsetWidth;view.style.animation='';
  const allowedScope=parts[1]==='CRYPTO'||parts[1]==='SPORTS';
  const page=parts[0]==='scope'&&allowedScope&&parts[2]?scopeView(parts[1],parts[2]):(parts[0]==='charts'?cryptoResearchView():(parts[0]==='arsenal'?modelArsenalView():(parts[0]==='glossary'?glossaryView():overviewView())));
  syncCameraToRoute(false);
  view.innerHTML=statusRibbon()+page;
  [...view.querySelectorAll('.reveal')].forEach((el,i)=>el.style.animationDelay=(i*45)+'ms');
  requestAnimationFrame(()=>revealGuideTab(view.querySelector('.daily-guide .bt-tab.on')));
  if(parts[0]==='glossary')wireGlossary();
  if(parts[0]==='charts')requestAnimationFrame(()=>{ensureMarketChartData();mountMarketChart();});
  buildNav();
}
function kpi(lab,val,cls,sub,doFlip){
  return '<div class="card kpi reveal"><div class="lab">'+lab+'</div><div class="val '+(cls||'')+'">'+(doFlip?flip(val):val)+'</div>'+(sub?'<div class="sub">'+sub+'</div>':'')+'</div>';
}
const ISSUED_TIER_ORDER=['A','B','C','WATCH'];
const TIER_ORDER=[...ISSUED_TIER_ORDER,'UNATTRIBUTED'];
const TIER_EVIDENCE_MAX_AGE_MS=48*60*60*1000;
function tierBadge(tier){const t=TIER_ORDER.includes(String(tier).toUpperCase())?String(tier).toUpperCase():'UNATTRIBUTED';return '<span class="tier-badge '+t.toLowerCase()+'">'+t+'</span>';}
function boardTier(row){
  const t=String(row&&row.tier_display_bucket||'UNATTRIBUTED').toUpperCase();
  return TIER_ORDER.includes(t)?t:'UNATTRIBUTED';
}
function boardTierReason(row){
  const tier=boardTier(row),display=String(row&&row.tier_display_reason||'').toLowerCase();
  const raw=String((tier==='UNATTRIBUTED'||display==='a_scarcity_cap_enforced_at_read')?display:(row&&row.tier_reason||display)).toLowerCase();
  const labels={
    meets_a_edge_and_uncertainty:'At least 4% net edge and at most 12% uncertainty',
    meets_b_edge_and_uncertainty:'At least 2% net edge and at most 18% uncertainty',
    meets_c_edge_and_uncertainty:'At least 1% net edge and at most 25% uncertainty',
    a_scarcity_cap_demoted_to_b:'B after the A-tier event or scope scarcity cap',
    a_scarcity_cap_enforced_at_read:'B after the A-tier event or scope scarcity cap',
    below_c_after_fee_edge:'WATCH — below 1% executable net edge',
    uncertainty_above_tier_gate:'WATCH — uncertainty exceeds the tier gate',
    no_executable_depth:'UNATTRIBUTED — no two-sided selected-side quote with positive quote sizes or legacy liquidity',
    cached_model_market_prior_only:'UNATTRIBUTED — exchange price only; no independent predictive source',
    cached_model_missing_lineage:'UNATTRIBUTED — forecast source lineage is missing',
    cached_model_missing_exact_forecast_timestamp:'UNATTRIBUTED — exact forecast time is missing',
    cached_model_missing:'UNATTRIBUTED — no governed forecast exists for this market',
    series_refresh_failed_or_unknown:'UNATTRIBUTED — this market series did not refresh successfully',
    legacy_or_superseded_tier_policy:'UNATTRIBUTED — grade belongs to an older tier policy',
    snapshot_not_bound_to_visible_row:'UNATTRIBUTED — tier snapshot is not bound to this visible row',
    invalid_assessment_clock:'UNATTRIBUTED — assessment time cannot be verified',
    assessment_after_board_generation:'UNATTRIBUTED — assessment is newer than the board snapshot',
    assessment_after_read_time:'UNATTRIBUTED — assessment time is in the future',
    market_expired_for_board:'UNATTRIBUTED — market expired before this board was read',
    legacy_missing_or_invalid_tier_snapshot:'UNATTRIBUTED — no valid current-policy snapshot'
  };
  if(labels[raw])return labels[raw];
  if(raw)return raw.replaceAll('_',' ');
  return tier==='UNATTRIBUTED'?'UNATTRIBUTED — no valid current-policy attribution':tier+' — current executable-value policy';
}
function boardTierCounts(scope){
  const counts=Object.fromEntries(TIER_ORDER.map(t=>[t,0])),board=STATE.board;
  if(!board||typeof board!=='object')return {available:false,counts:counts,rows:0};
  const coverageDate=String((STATE.boardMeta||{}).coverage_date||'');
  const groups=scope?[board[String(scope).toLowerCase()]]:Object.values(board);
  let available=false,rows=0;
  groups.forEach(group=>{if(!group||typeof group!=='object')return;available=true;
    Object.values(group).forEach(items=>(Array.isArray(items)?items:[]).forEach(row=>{
      if(coverageDate&&String((row||{}).event_date||'')!==coverageDate)return;
      counts[boardTier(row)]++;rows++;
    }));
  });
  return {available:available,counts:counts,rows:rows};
}
function gameTierSummary(rows){
  const counts=Object.fromEntries(TIER_ORDER.map(t=>[t,0]));
  rows.forEach(row=>counts[boardTier(row)]++);
  const present=TIER_ORDER.filter(t=>counts[t]>0),label=present.map(t=>t+' '+counts[t]).join(', ');
  return '<span class="game-tier-summary" aria-label="Tier counts: '+esc(label)+'">'+present.map(t=>'<span class="game-tier-chip">'+tierBadge(t)+'<span class="tier-n">'+counts[t]+'</span></span>').join('')+'</span>';
}
function tierScopeCounts(dist,scope){
  if(!scope)return dist.counts||{};
  const by=dist.by_scope||{},wanted=String(scope).toLowerCase();
  const key=Object.keys(by).find(k=>String(k).toLowerCase()===wanted);
  return key?by[key]:{};
}
function tierEvidenceBucket(area,tier,scope){
  if(!area)return {};
  if(!scope)return (area.by_tier||{})[tier]||{};
  const by=area.by_tier_scope||{},wanted=(tier+'|'+scope).toLowerCase();
  const key=Object.keys(by).find(k=>String(k).toLowerCase()===wanted);
  return key?by[key]:{};
}
function tierEvidenceFreshness(tp){
  const stamp=tp&&(tp.tier_performance_generated_at||tp.evidence_generated_at||tp.backtest_generated_at),at=Date.parse(stamp||'');
  if(!Number.isFinite(at))return {known:false,stale:false,stamp:null,ageMs:null};
  const ageMs=Math.max(0,Date.now()-at);
  return {known:true,stale:ageMs>TIER_EVIDENCE_MAX_AGE_MS,stamp:stamp,ageMs:ageMs};
}
function tierSampleLabel(f,freshness){
  const n=Number(f.n||0);
  if(!n)return 'COLLECTING';
  if(freshness&&freshness.stale)return 'STALE SAMPLE';
  if(freshness&&!freshness.known)return 'TIME UNKNOWN';
  if(f.evidence_status==='INSUFFICIENT_SAMPLE')return 'INSUFFICIENT';
  return 'FORWARD SAMPLE';
}
function metricToken(value){
  const token=String(value==null?'':value).trim().toLowerCase().replace(/[\s_-]+/g,'');
  if(['1h','hour','hourly'].includes(token))return 'hourly';
  if(['1d','day','daily'].includes(token))return 'daily';
  if(['1w','week','weekly'].includes(token))return 'weekly';
  return token;
}
function metricBucket(map,parts){
  if(!map||typeof map!=='object')return null;
  const wanted=parts.map(metricToken);
  for(const [key,value] of Object.entries(map)){
    const tokens=String(key).split('|').map(metricToken);
    if(tokens.length===wanted.length&&tokens.every((token,i)=>token===wanted[i]))return value&&typeof value==='object'?value:{};
  }
  let node=map;
  for(const part of wanted){
    if(!node||typeof node!=='object')return null;
    const key=Object.keys(node).find(candidate=>metricToken(candidate)===part);
    if(key==null)return null;node=node[key];
  }
  return node&&typeof node==='object'?node:null;
}
function cryptoTierHorizonTable(scope,forecast,freshness){
  const hasApi=['by_scope_horizon','by_tier_scope_horizon'].some(key=>forecast&&forecast[key]);
  if(!hasApi)return '';
  const horizons=[['hourly','Hourly'],['daily','Daily'],['weekly','Weekly']];let rows='';
  const metricCells=f=>'<td>'+commaN((f||{}).n||0)+' / '+commaN((f||{}).event_clusters||0)+'</td>'
    +'<td>'+((f||{}).value_side_hit_rate==null?'—':pct(f.value_side_hit_rate,1))+'</td><td>'+((f||{}).mean_brier==null?'—':num(f.mean_brier,3))+'</td>';
  horizons.forEach(([horizon,label])=>{
    const f=metricBucket(forecast&&forecast.by_scope_horizon,[scope,horizon]);
    if(f!==null)rows+='<tr class="scope-row"><td>'+label+'<span class="tier-sample">'+tierSampleLabel(f||{},freshness)+'</span></td>'+metricCells(f)+'</tr>';
    ISSUED_TIER_ORDER.forEach(t=>{
      const tf=metricBucket(forecast&&forecast.by_tier_scope_horizon,[t,scope,horizon]);
      if(tf!==null)rows+='<tr class="tier-detail"><td>'+tierBadge(t)+'<span class="tier-sample">'+label+'</span></td>'+metricCells(tf)+'</tr>';
    });
  });
  if(!rows)return '';
  return '<div class="tier-horizon-head"><b>'+esc(scope)+' hourly / daily / weekly forecast evidence</b><span>policy-separated settled forecast slices</span></div>'
    +'<div class="tier-table-wrap"><table class="tier-table tier-horizon-table"><thead><tr><th>Horizon / tier</th><th>Forecast n / clusters</th><th>Value-side hit</th><th>Brier</th></tr></thead><tbody>'+rows+'</tbody></table></div>';
}
function tierPerformanceCard(scope){
  const tp=STATE.tierPerformance||{},dist=tp.current_distribution||{},boardCounts=boardTierCounts(scope),counts=boardCounts.available?boardCounts.counts:tierScopeCounts(dist,scope);
  const total=TIER_ORDER.reduce((n,t)=>n+Number(counts[t]||0),0),forecast=tp.forecast||{},freshness=tierEvidenceFreshness(tp);
  const evidenceN=ISSUED_TIER_ORDER.reduce((n,t)=>n+Number(tierEvidenceBucket(forecast,t,scope).n||0),0);
  const unavailable=!STATE.tierPerformanceFetchOk||tp.status==='UNAVAILABLE'||!!tp.error;
  const state=unavailable?'RESULT EVIDENCE UNAVAILABLE':(freshness.stale?'STALE EVIDENCE':(evidenceN&&!freshness.known?'EVIDENCE TIME UNKNOWN':(evidenceN?(ISSUED_TIER_ORDER.some(t=>tierSampleLabel(tierEvidenceBucket(forecast,t,scope),freshness)==='INSUFFICIENT')?'INSUFFICIENT SAMPLE':'FORWARD EVIDENCE'):'COLLECTING FORWARD EVIDENCE')));
  const policy=tp.policy_version||(dist.policy_versions||[]).join(', ')||'executable value v5';
  let h='<section class="card reveal tier-card" style="margin-bottom:var(--s3)" aria-label="'+esc((scope?scope+' ':'')+'tier forecast diagnostics')+'"><h3>Tier forecast diagnostics <span class="r">'+esc(scope||'all scopes')+' · '+esc(policy)+'</span></h3>';
  h+='<div class="tier-intro"><p>Current grades come from the visible board snapshot'+(boardCounts.available?' ('+commaN(boardCounts.rows)+' rows)':'')+'. Forward forecast evidence is shown separately and never inferred from current grades. Paper/shadow realized economics are retired and are not displayed or used for live authority.</p><span class="tier-state '+(state==='FORWARD EVIDENCE'?'ready':(state==='STALE EVIDENCE'||state==='EVIDENCE TIME UNKNOWN'||state==='RESULT EVIDENCE UNAVAILABLE'?'stale':''))+'">'+esc(state)+'</span></div>';
  h+='<div class="tier-dist" aria-label="Current tier distribution">'+TIER_ORDER.map(t=>{const n=Number(counts[t]||0),share=total?n/total:0,color=t==='A'?'var(--green)':(t==='B'?'var(--cyan)':(t==='C'?'var(--amber)':(t==='UNATTRIBUTED'?'var(--red)':'var(--faint)')));return '<div class="tier-count" style="--tier-color:'+color+'"><div class="tc-head">'+tierBadge(t)+'<span class="tc-n">'+commaN(n)+'</span></div><div class="tc-share">'+pct(share,1)+' of '+commaN(total)+' current</div></div>';}).join('')+'</div>';
  h+='<div class="tier-table-wrap"><table class="tier-table"><thead><tr><th>Tier / evidence</th><th>Current</th><th>Forecast n / clusters</th><th>Value-side hit</th><th>Brier</th></tr></thead><tbody>';
  TIER_ORDER.forEach(t=>{const f=tierEvidenceBucket(forecast,t,scope),sample=t==='UNATTRIBUTED'?'NOT SCORED':tierSampleLabel(f,freshness);
    if(t==='UNATTRIBUTED'){h+='<tr><td>'+tierBadge(t)+'<span class="tier-sample">'+sample+'</span></td><td>'+commaN(counts[t]||0)+'</td><td>—</td><td>—</td><td>—</td></tr>';return;}
    h+='<tr><td>'+tierBadge(t)+'<span class="tier-sample">'+sample+'</span></td><td>'+commaN(counts[t]||0)+'</td>'
      +'<td>'+commaN(f.n||0)+' / '+commaN(f.event_clusters||0)+'</td><td>'+(f.value_side_hit_rate==null?'—':pct(f.value_side_hit_rate,1))+'</td><td>'+(f.mean_brier==null?'—':num(f.mean_brier,3))+'</td></tr>';});
  h+='</tbody></table></div>'+cryptoTierHorizonTable(scope,forecast,freshness)+'<div class="tier-foot"><span><b>Policy:</b> A ≥4% net edge / ≤12% uncertainty · B ≥2% / ≤18% · C ≥1% / ≤25%.</span><span>Letters also require an independent governed model source, a two-sided selected-side quote, and positive depth from both Kalshi quote sizes (or positive legacy liquidity). A is capped at one per event and five per scope. Research only; no execution authority.</span></div>';
  if(unavailable)h+='<div class="sub" style="margin-top:8px;color:var(--amber)">Forward tier-performance evidence is temporarily unavailable. Current A/B/C/WATCH/UNATTRIBUTED counts above still come directly from the visible board snapshot; no legacy rows are relabelled.</div>';
  else if(freshness.stale)h+='<div class="sub" style="margin-top:8px;color:var(--amber)">Evidence snapshot '+esc(ago(freshness.stamp))+' exceeds the 48-hour freshness window. Metrics remain visible for audit only and are not presented as forward-ready.</div>';
  else if(evidenceN&&!freshness.known)h+='<div class="sub" style="margin-top:8px;color:var(--amber)">Evidence timestamp is unavailable. Metrics remain visible for audit only until freshness can be verified.</div>';
  return h+'</section>';
}
function safeEvidenceRows(value){
  return Array.isArray(value)?value.filter(row=>row&&typeof row==='object'&&!Array.isArray(row)):[];
}
function evidenceCount(value){
  return typeof value==='number'&&Number.isInteger(value)&&value>=0&&Number.isFinite(value)?value:null;
}
function evidenceMetric(value){
  return typeof value==='number'&&Number.isFinite(value)?value:null;
}
function evidenceTime(value){
  const at=Date.parse(String(value||''));
  if(!Number.isFinite(at))return 'time unavailable';
  if(at>Date.now())return 'future timestamp';
  return ago(value);
}
function evidenceKpi(label,value,cls){
  const tone=['ok','warn','bad'].includes(cls)?cls:'';
  return '<div class="evidence-kpi"><span>'+esc(label)+'</span><b class="'+tone+'">'+esc(value)+'</b></div>';
}
function evidenceObject(value){
  return value&&typeof value==='object'&&!Array.isArray(value)?value:{};
}
function evidenceContractState(value,requireSchema){
  const item=evidenceObject(value);
  if(requireSchema&&item.schema_version!==1)return {label:'UNAVAILABLE',tone:'warn',raw:'SCHEMA_UNAVAILABLE'};
  const raw=String(item.status||'').trim().toUpperCase();
  let label='UNAVAILABLE';
  if(['AVAILABLE','OK','FRESH'].includes(raw))label='AVAILABLE';
  else if(['PARTIAL','STALE','DEGRADED','AUDIT_ONLY','INSUFFICIENT_EVIDENCE','EVIDENCE_ONLY','EXACT_TAXONOMY'].includes(raw))label='PARTIAL';
  if(item.stale===true&&label==='AVAILABLE')label='PARTIAL';
  return {label:label,tone:label==='AVAILABLE'?'ok':'warn',raw:raw||'UNAVAILABLE'};
}
function evidenceSource(value,fallback){
  const source=evidenceObject(value).source;
  return typeof source==='string'&&source.trim()?source.trim():(fallback||'unavailable');
}
function evidenceMoment(value){
  const at=Date.parse(String(value||''));
  if(!Number.isFinite(at))return 'time unavailable';
  const delta=(at-Date.now())/1000,abs=Math.abs(delta);
  const amount=abs<90?Math.round(abs)+'s':(abs<5400?Math.round(abs/60)+'m':Math.round(abs/3600)+'h');
  return delta>=0?'in '+amount:amount+' ago';
}
function evidenceBytes(value){
  if(typeof value!=='number'||!Number.isFinite(value))return 'UNAVAILABLE';
  const sign=value<0?'-':'',absolute=Math.abs(value),units=['B','KiB','MiB','GiB','TiB'];
  let scaled=absolute,index=0;
  while(scaled>=1024&&index<units.length-1){scaled/=1024;index++;}
  return sign+scaled.toFixed(index?2:0)+' '+units[index];
}
function evidenceBytesRate(value){
  if(typeof value!=='number'||!Number.isFinite(value))return 'UNAVAILABLE';
  return (value>0?'+':'')+evidenceBytes(value)+'/h';
}
function evidenceContextHtml(source,windowLabel,staleness){
  const stale=String(staleness||'UNAVAILABLE').toUpperCase();
  const freshnessClass=stale==='CURRENT'?'current':(stale==='STALE'?'stale':'');
  return '<div class="evidence-context">'
    +'<span><b>Source:</b> '+esc(source||'unavailable')+'</span>'
    +'<span><b>Window:</b> '+esc(windowLabel||'unavailable')+'</span>'
    +'<span class="'+freshnessClass+'"><b>Staleness:</b> '+esc(stale)+'</span>'
    +'</div>';
}
function renderSystemHealth(){
  const st=STATE.status;
  if(!st||!st.generated_at){
    return '<section class="card reveal ops-evidence-card" aria-label="System health evidence"><div class="evidence-head"><h3>System health</h3>'
      +'<span class="evidence-state warn">UNAVAILABLE</span></div>'
      +'<div class="evidence-empty">No validated status snapshot is loaded. Health, alert history, and recent-cycle evidence are unavailable; no healthy state is inferred.</div></section>';
  }
  const sh=evidenceObject(st.system_health),hasContract=Object.keys(sh).length>0;
  const contractState=hasContract?evidenceContractState(sh,true):null;
  const ledger=evidenceObject(sh.ledger),growth=evidenceObject(ledger.growth);
  const retention=evidenceObject(sh.retention),sqlite=evidenceObject(sh.sqlite_contention);
  const deadlines=evidenceObject(sh.cycle_deadlines),promotion=evidenceObject(sh.promotion_run);
  const wd=st.watchdog&&typeof st.watchdog==='object'?st.watchdog:{},hb=st.heartbeat&&typeof st.heartbeat==='object'?st.heartbeat:{};
  const alerts=safeEvidenceRows(st.alerts).slice(-5).reverse(),cycles=safeEvidenceRows(st.recent_cycles).slice(-5).reverse();
  const ageEntries=Object.entries(st.data_ages&&typeof st.data_ages==='object'?st.data_ages:{}).filter(([,v])=>v&&typeof v==='object');
  const stale=ageEntries.filter(([,v])=>v.stale===true),staleTasks=Array.isArray(wd.stale_tasks)?wd.stale_tasks.filter(v=>typeof v==='string'&&v.trim()):[];
  const watchdogKnown=typeof wd.healthy==='boolean',watchdogLabel=watchdogKnown?(wd.healthy?'HEALTHY':'DEGRADED'):'UNAVAILABLE';
  const heartbeatKnown=typeof hb.alive==='boolean',heartbeatLabel=heartbeatKnown?(hb.alive?'ALIVE':'NOT ALIVE'):'UNAVAILABLE';
  const fallbackKnown=watchdogKnown||heartbeatKnown||alerts.length>0||cycles.length>0;
  const stateLabel=contractState?contractState.label:(fallbackKnown?'PARTIAL':'UNAVAILABLE');
  const stateTone=contractState?contractState.tone:(fallbackKnown?'warn':'warn');
  const ledgerState=evidenceContractState(ledger),sizeGib=evidenceMetric(ledger.size_gib);
  const sizeText=ledgerState.label!=='UNAVAILABLE'&&sizeGib!==null?num(sizeGib,3)+' GiB':'UNAVAILABLE';
  const growthState=evidenceContractState(growth),growthSamples=evidenceCount(growth.sample_count);
  const growthRate=evidenceMetric(growth.bytes_per_hour);
  const growthText=growthState.label!=='UNAVAILABLE'&&growthSamples!==null&&growthSamples>=2&&growthRate!==null
    ?evidenceBytesRate(growthRate):'UNAVAILABLE';
  const retryState=evidenceContractState({status:sqlite.retry_events_status});
  const retryEvents=evidenceCount(sqlite.retry_events);
  const retryText=retryState.label!=='UNAVAILABLE'&&retryEvents!==null?commaN(retryEvents):'UNAVAILABLE';
  const deadlineState=evidenceContractState(deadlines),deadlineN=evidenceCount(deadlines.deadline_count);
  const deadlineTotal=evidenceCount(deadlines.records_considered),deadlineRate=evidenceMetric(deadlines.rate);
  const deadlineText=deadlineState.label!=='UNAVAILABLE'&&deadlineTotal!==null&&deadlineTotal>0&&deadlineRate!==null
    ?pct(deadlineRate,1)+' · '+commaN(deadlineN)+' / '+commaN(deadlineTotal):'UNAVAILABLE';
  const sources=[ledger.source,retention.source,deadlines.source,promotion.source]
    .filter(value=>typeof value==='string'&&value.trim());
  const uniqueSources=[...new Set(sources)];
  const windowLabel=deadlineTotal!==null
    ?String(deadlines.window_kind||'bounded records')+' · '+deadlineTotal+' considered / '+String(deadlines.tail_limit||'limit unavailable')
    :'cycle window unavailable';
  const promotionStaleness=promotion.stale===true?'STALE':(promotion.stale===false?'CURRENT':'UNAVAILABLE');
  let h='<section class="card reveal ops-evidence-card" aria-label="System health evidence"><div class="evidence-head"><h3>System health <span class="r">persisted snapshot · GET-only</span></h3>'
    +'<span class="evidence-state '+stateTone+'">'+esc(stateLabel)+'</span></div>'
    +evidenceContextHtml(uniqueSources.join(' + ')||'status snapshot fallback',windowLabel,promotionStaleness);
  h+='<div class="evidence-kpis">'
    +evidenceKpi('Ledger size',sizeText,sizeText==='UNAVAILABLE'?'warn':(ledger.over_threshold===true?'bad':'ok'))
    +evidenceKpi('Ledger growth',growthText,growthText==='UNAVAILABLE'?'warn':(growthRate>0?'warn':'ok'))
    +evidenceKpi('SQLite retry events',retryText,retryText==='UNAVAILABLE'?'warn':(retryEvents>0?'bad':'ok'))
    +evidenceKpi('CycleDeadline rate',deadlineText,deadlineText==='UNAVAILABLE'?'warn':(deadlineN>0?'bad':'ok'))
    +'</div>';
  const ledgerDetails=[];
  if(ledger.sampled_at)ledgerDetails.push('sampled '+evidenceMoment(ledger.sampled_at));
  if(evidenceMetric(ledger.wal_size_bytes)!==null)ledgerDetails.push('WAL '+evidenceBytes(ledger.wal_size_bytes));
  if(evidenceMetric(ledger.threshold_bytes)!==null)ledgerDetails.push('threshold '+evidenceBytes(ledger.threshold_bytes));
  if(growthSamples!==null)ledgerDetails.push('growth samples '+growthSamples);
  if(growth.window_start||growth.window_end)ledgerDetails.push('growth window '+evidenceMoment(growth.window_start)+' to '+evidenceMoment(growth.window_end));
  if(growthText==='UNAVAILABLE'&&growth.reason)ledgerDetails.push('growth unavailable: '+String(growth.reason));
  h+='<div class="evidence-section"><div class="evidence-section-head"><b>Ledger &amp; contention evidence</b><span>observational · no database query from this page</span></div>'
    +'<div class="evidence-item"><div class="evidence-main">'+esc(ledgerState.raw||'UNAVAILABLE')+'</div>'
    +'<div class="evidence-time">'+esc(sqlite.status||'UNAVAILABLE')+'</div>'
    +'<div class="evidence-meta">'+esc(ledgerDetails.length?ledgerDetails.join(' · '):'Ledger evidence unavailable.')
    +(evidenceCount(sqlite.terminal_failure_count)!==null?' · terminal lock failures '+esc(sqlite.terminal_failure_count):'')
    +(typeof sqlite.wal_checkpoint_busy==='boolean'?' · WAL checkpoint busy '+esc(sqlite.wal_checkpoint_busy):'')
    +(sqlite.reason?' · '+esc(sqlite.reason):'')+'</div></div></div>';
  const retentionState=evidenceContractState(retention),promotionState=evidenceContractState(promotion);
  const retentionStatus=String(retention.last_run_status||retention.status||'UNAVAILABLE').toUpperCase();
  const retentionTone=/REFUSED|FAILED|ERROR/.test(retentionStatus)?'bad':(retentionStatus==='APPLIED'?'ok':'warn');
  const retentionMeta=[
    'last run '+evidenceMoment(retention.last_run_at),
    'last success '+evidenceMoment(retention.last_success_at),
    'next due '+evidenceMoment(retention.next_due_at),
    'due status '+String(retention.next_due_status||'UNAVAILABLE'),
  ];
  if(evidenceCount(retention.lock_retries_last_run)!==null)retentionMeta.push('lock retries '+retention.lock_retries_last_run);
  if(retention.failure_reason)retentionMeta.push('failure '+retention.failure_reason);
  const promotionStatus=String(promotion.run_status||promotion.status||'UNAVAILABLE').toUpperCase();
  const promotionTone=/ABORTED|NO_DB|FAILED|ERROR/.test(promotionStatus)?'bad':(promotionStatus==='OK'&&!promotion.stale?'ok':'warn');
  const promotionMeta=[
    'generated '+evidenceMoment(promotion.generated_at),
    'scopes '+(evidenceCount(promotion.scopes_evaluated)===null?'UNAVAILABLE':promotion.scopes_evaluated),
    'eligible '+(evidenceCount(promotion.eligible_scopes)===null?'UNAVAILABLE':promotion.eligible_scopes),
    'promoted '+(evidenceCount(promotion.promoted_count)===null?'UNAVAILABLE':promotion.promoted_count),
    'declined '+(evidenceCount(promotion.declined_count)===null?'UNAVAILABLE':promotion.declined_count),
    'human review '+(evidenceCount(promotion.human_review_candidate_count)===null?'UNAVAILABLE':promotion.human_review_candidate_count),
  ];
  h+='<div class="evidence-section"><div class="evidence-section-head"><b>Retention &amp; promotion runs</b><span>cadence and evidence only · no execution authority</span></div><div class="evidence-list">'
    +'<div class="evidence-item"><div class="evidence-main"><span class="severity '+retentionTone+'">'+esc(retentionState.label)+'</span>Retention '+esc(retentionStatus)+'</div>'
    +'<div class="evidence-time">'+esc(evidenceSource(retention,'source unavailable'))+'</div><div class="evidence-meta">'+esc(retentionMeta.join(' · '))+'</div></div>'
    +'<div class="evidence-item"><div class="evidence-main"><span class="severity '+promotionTone+'">'+esc(promotionState.label)+'</span>Promotion run '+esc(promotionStatus)+'</div>'
    +'<div class="evidence-time">'+esc(promotion.stale===true?'STALE':'audit')+'</div><div class="evidence-meta">'+esc(promotionMeta.join(' · '))+' · live trading authority '+esc(promotion.live_trading_authority||'UNAVAILABLE')+' · execution authority '+esc(promotion.execution_authority===false?'FALSE':'UNAVAILABLE')+'</div></div>'
    +'</div></div>';
  if(stale.length||staleTasks.length){
    const detail=[];
    if(stale.length)detail.push('Stale artifacts: '+stale.map(([name])=>name.replaceAll('_',' ')).join(', '));
    if(staleTasks.length)detail.push('Watchdog stale tasks: '+staleTasks.join(', '));
    h+='<div class="evidence-empty">'+esc(detail.join(' · '))+'</div>';
  }
  h+='<div class="evidence-section"><div class="evidence-section-head"><b>Recent alert records</b><span>historical · de-duplicated · newest first</span></div>';
  if(alerts.length){
    h+='<div class="evidence-list">'+alerts.map(row=>{
      const rawSeverity=String(row.severity||'').toLowerCase(),severity=['critical','warning','info'].includes(rawSeverity)?rawSeverity:'unknown';
      const kind=String(row.kind||'UNKNOWN_KIND').trim()||'UNKNOWN_KIND';
      const message=String(row.message||'message unavailable').trim()||'message unavailable';
      return '<div class="evidence-item"><div class="evidence-main"><span class="severity '+severity+'">'+esc(severity)+'</span>'+esc(kind)+'</div>'
        +'<div class="evidence-time">'+esc(evidenceTime(row.at))+'</div><div class="evidence-meta">'+esc(message)+'</div></div>';
    }).join('')+'</div>';
  }else h+='<div class="evidence-empty">Alert history is empty or unavailable in this bounded status snapshot; those states are not distinguishable here.</div>';
  h+='</div><div class="evidence-section"><div class="evidence-section-head"><b>Recent cycles</b><span>persisted receipts · newest first</span></div>';
  if(cycles.length){
    h+='<div class="evidence-list">'+cycles.map(row=>{
      const status=String(row.status||'STATUS_UNAVAILABLE').trim()||'STATUS_UNAVAILABLE',parts=[];
      [['markets_scanned','markets'],['signals_generated','signals'],['signals_rejected','rejected'],['decisions_made','decisions'],['abstained','abstained']].forEach(([key,label])=>{
        const value=evidenceCount(row[key]);if(value!==null)parts.push(label+' '+value);
      });
      return '<div class="evidence-item"><div class="evidence-main">'+esc(status)+'</div><div class="evidence-time">'+esc(evidenceTime(row.completed_at||row.at))+'</div>'
        +'<div class="evidence-meta">'+esc(parts.length?parts.join(' · '):'Cycle counters unavailable on this receipt.')+'</div></div>';
    }).join('')+'</div>';
  }else h+='<div class="evidence-empty">Recent-cycle evidence is unavailable. No successful or healthy cycle is inferred.</div>';
  return h+'</div></section>';
}
function systemHealthCard(){return renderSystemHealth();}
function currentBoardRows(){
  const board=STATE.board;
  if(!board||typeof board!=='object'||Array.isArray(board))return {available:false,rows:[]};
  const coverageDate=String((STATE.boardMeta||{}).coverage_date||''),rows=[];let available=false;
  Object.values(board).forEach(group=>{
    const lists=Array.isArray(group)?[group]:(group&&typeof group==='object'?Object.values(group):[]);
    if(lists.length)available=true;
    lists.forEach(items=>(Array.isArray(items)?items:[]).forEach(row=>{
      if(!row||typeof row!=='object'||Array.isArray(row))return;
      if(coverageDate&&String(row.event_date||'')!==coverageDate)return;
      rows.push(row);
    }));
  });
  return {available:available,rows:rows};
}
function explicitBoardGateReasons(){
  const meta=evidenceObject(STATE.boardMeta),artifactStatus=String(meta.artifact_status||'').toUpperCase();
  const currentArtifact=STATE.boardFetchOk===true&&artifactStatus==='FRESH'&&meta.stale===false;
  if(!currentArtifact)return {available:false,current:false,rows:0,nonIssued:0,missingReasons:0,reasons:[]};
  const current=currentBoardRows(),counts=new Map();let nonIssued=0,missingReasons=0;
  current.rows.forEach(row=>{
    const tier=boardTier(row);
    if(!['WATCH','UNATTRIBUTED'].includes(tier))return;
    nonIssued++;
    const display=String(row.tier_display_reason||'').trim(),policy=String(row.tier_reason||'').trim(),raw=display||policy;
    if(!raw){missingReasons++;return;}
    const key=tier+'|'+raw,found=counts.get(key);
    if(found)found.count++;
    else counts.set(key,{tier:tier,raw:raw,label:boardTierReason(row),count:1});
  });
  return {available:current.available,current:true,rows:current.rows.length,nonIssued:nonIssued,missingReasons:missingReasons,
    reasons:[...counts.values()].sort((a,b)=>b.count-a.count||a.label.localeCompare(b.label))};
}
function renderAfterFeeDistribution(afterFee){
  const state=evidenceContractState(afterFee),sampleCount=evidenceCount(afterFee.sample_count);
  const bins=safeEvidenceRows(afterFee.bins).filter(row=>
    typeof row.label==='string'&&row.label.trim()&&evidenceCount(row.count)!==null);
  const binTotal=bins.reduce((total,row)=>total+row.count,0);
  const valid=state.label==='AVAILABLE'&&sampleCount!==null&&sampleCount>0&&bins.length>0&&binTotal===sampleCount;
  if(!valid){
    const reason=String(afterFee.reason||(
      sampleCount===0?'zero validated after-fee rows':'validated distribution unavailable'
    ));
    return '<div class="evidence-empty">After-fee edge distribution UNAVAILABLE: '+esc(reason)+'. A raw edge value or zero-row sample is not substituted.</div>';
  }
  const stats=[
    ['min',afterFee.min],['p50',afterFee.p50],['p90',afterFee.p90],
    ['max',afterFee.max],['mean',afterFee.mean],
  ].filter(([,value])=>evidenceMetric(value)!==null)
    .map(([label,value])=>label+' '+signed(value,2)).join(' · ');
  return '<div class="edge-bins">'+bins.map(row=>'<div class="edge-bin"><span>'+esc(row.label)+'</span><b>'+commaN(row.count)+'</b></div>').join('')+'</div>'
    +'<div class="evidence-meta" style="margin-top:6px">'+esc(sampleCount)+' validated rows'
    +(evidenceCount(afterFee.missing_count)!==null?' · '+esc(afterFee.missing_count)+' missing/excluded':'')
    +(stats?' · '+esc(stats):'')+'</div>';
}
function actionableShareEvidence(actionable){
  const state=evidenceContractState(actionable),numerator=evidenceCount(actionable.numerator);
  const denominator=evidenceCount(actionable.denominator),value=evidenceMetric(actionable.value);
  const consistent=numerator!==null&&denominator!==null&&denominator>0&&numerator<=denominator
    &&value!==null&&value>=0&&value<=1&&Math.abs(value-numerator/denominator)<=0.0002;
  return {
    available:state.label==='AVAILABLE'&&consistent,
    text:state.label==='AVAILABLE'&&consistent?pct(value,1):'UNAVAILABLE',
    numerator:numerator,denominator:denominator,value:value,
    reason:String(actionable.reason||'validated numerator/denominator/share unavailable'),
    definition:String(actionable.definition||'letter-tier A/B/C rows divided by all current board rows'),
  };
}
function executionCohortPane(cohort,kind){
  const value=evidenceObject(cohort),maker=kind==='maker';
  const fixedLabel=maker?'Witnessed maker (C0)':'Counterfactual taker (C1)';
  const fills=evidenceCount(value.fills),clusters=evidenceCount(value.fill_event_clusters);
  const fillRate=evidenceMetric(value.fill_rate),edge=evidenceMetric(value.brier_edge_vs_market);
  const lines=[
    'fills '+(fills===null?'UNAVAILABLE':fills),
    'clusters '+(clusters===null?'UNAVAILABLE':clusters),
    'fill rate '+(fillRate===null?'UNAVAILABLE':pct(fillRate,1)),
    'Brier edge '+(edge===null?'UNAVAILABLE':signed(edge,2)),
    'gate '+String(value.gate_status||'UNAVAILABLE'),
  ];
  return '<div class="evidence-pane"><span class="pane-label">'+esc(fixedLabel)+'</span><b>'+esc(value.label||value.cohort||'UNAVAILABLE')+'</b>'
    +'<p>'+esc(lines.join(' · '))+'</p><p>Evidence basis: '+esc(value.evidence_basis||'UNAVAILABLE')+'. '
    +(maker?'Observed resting-maker fills only.':'Replay counterfactual; it is not a second realized book.')+'</p></div>';
}
function renderExecutionComparison(comparison){
  const state=evidenceContractState(comparison),validAudit=comparison.audit_only===true
    &&comparison.policy_switch_authority===false&&state.label!=='UNAVAILABLE';
  if(!validAudit){
    return '<div class="evidence-empty">Maker-versus-taker comparison UNAVAILABLE. No realized or policy-switch claim is inferred.</div>';
  }
  const stale=comparison.stale===true;
  return '<div class="evidence-context"><span><b>Source:</b> '+esc(evidenceSource(comparison,'unavailable'))+'</span>'
    +'<span><b>As of:</b> '+esc(evidenceMoment(comparison.generated_at))+'</span>'
    +'<span class="'+(stale?'stale':'current')+'"><b>Staleness:</b> '+esc(stale?'STALE':'CURRENT')+'</span></div>'
    +'<div class="evidence-panes">'+executionCohortPane(comparison.maker,'maker')+executionCohortPane(comparison.taker,'taker')+'</div>'
    +'<div class="evidence-empty" style="margin-top:7px">AUDIT ONLY'+(stale?' · STALE':'')+': this comparison cannot switch policy, promote a model, or authorize execution.</div>';
}
function renderKxsol15m(kx){
  const mapping=evidenceObject(kx.scope_mapping),stats=evidenceObject(kx.statistical_evidence);
  const caps=evidenceObject(kx.caps_evidence),live=evidenceObject(kx.live_authority);
  const kxState=evidenceContractState(kx),mappingState=evidenceContractState(mapping);
  const statsState=evidenceContractState(stats),capsState=evidenceContractState(caps);
  const statsAvailable=kxState.label!=='UNAVAILABLE'&&mappingState.label!=='UNAVAILABLE'
    &&statsState.label!=='UNAVAILABLE'&&stats.execution_authority===false;
  const classification=statsAvailable?String(stats.classification||'UNAVAILABLE'):'UNAVAILABLE';
  const clusters=evidenceCount(stats.clusters),edgeMean=evidenceMetric(stats.edge_mean);
  const ciLower=evidenceMetric(stats.ci_lower),ciUpper=evidenceMetric(stats.ci_upper);
  const statsMeta=[
    'scope '+String(mappingState.label==='UNAVAILABLE'?'UNAVAILABLE':(mapping.scope||'UNAVAILABLE')),
    'clusters '+(clusters===null?'UNAVAILABLE':clusters),
    'mean '+(edgeMean===null?'UNAVAILABLE':signed(edgeMean,2)),
    'CI95 '+(ciLower===null||ciUpper===null?'UNAVAILABLE':signed(ciLower,2)+' to '+signed(ciUpper,2)),
    stats.stale===true?'STALE':'staleness '+(stats.stale===false?'CURRENT':'UNAVAILABLE'),
  ];
  const capsUsable=kxState.label!=='UNAVAILABLE'&&capsState.label!=='UNAVAILABLE'
    &&caps.execution_authority===false&&typeof caps.exact_series_allowed==='boolean';
  const exactSeries=capsUsable&&caps.exact_series_allowed===true&&caps.matched_series==='KXSOL15M';
  const capsText=!capsUsable?'UNAVAILABLE':(exactSeries?'EXACT SERIES LISTED':'NOT LISTED');
  const liveKnown=typeof live.execution_authority==='boolean';
  const liveText=liveKnown?(live.execution_authority?'LIVE AUTHORITY TRUE':'LOCKED'):'UNAVAILABLE';
  const liveTone=liveKnown?(live.execution_authority?'bad':'ok'):'warn';
  const session=String(live.session_status||'UNAVAILABLE')+(live.session_expired===true?' · EXPIRED':'');
  return '<div class="evidence-panes" aria-label="KXSOL15M evidence separation">'
    +'<div class="evidence-pane '+(statsAvailable?'':'warn')+'"><span class="pane-label">Statistical scope</span><b>'+esc(classification)+'</b>'
    +'<p>'+esc(statsMeta.join(' · '))+'</p><p>Source: '+esc(evidenceSource(stats,evidenceSource(mapping,'unavailable')))+'. Statistical evidence cannot authorize trading.</p></div>'
    +'<div class="evidence-pane '+(exactSeries?'ok':(!capsUsable?'warn':'bad'))+'"><span class="pane-label">Caps exact-series evidence</span><b>'+esc(capsText)+'</b>'
    +'<p>Series '+esc(kx.series||'KXSOL15M')+' · matched '+esc(caps.matched_series||'UNAVAILABLE')+' · source '+esc(evidenceSource(caps,'unavailable'))+'.</p>'
    +'<p>Positive caps candidacy is one predicate only; this pane has no execution authority.</p></div>'
    +'<div class="evidence-pane '+liveTone+'"><span class="pane-label">Live authority &amp; session</span><b>'+esc(liveText)+'</b>'
    +'<p>State '+esc(live.state||'UNAVAILABLE')+' · session '+esc(session)+(live.blocker?' · blocker '+esc(live.blocker):'')+'.</p>'
    +'<p>Independent live gates and an active session are required; statistics do not authorize orders.</p></div>'
    +'</div><div class="evidence-empty" style="margin-top:7px">'+esc(kx.conclusion||'KXSOL15M evidence panes are independent; none is substituted for another.')
    +' · evidence-contract execution authority '+esc(kx.execution_authority===false?'FALSE':'UNAVAILABLE')+'</div>';
}
function renderEdgeQuality(){
  const st=STATE.status||{},cycles=safeEvidenceRows(st.recent_cycles),latest=cycles.length?cycles[cycles.length-1]:null;
  const eq=evidenceObject(st.edge_quality),hasContract=Object.keys(eq).length>0;
  const contractState=hasContract?evidenceContractState(eq,true):null;
  const board=evidenceObject(eq.current_board),afterFee=evidenceObject(board.after_fee_edge);
  const boardState=evidenceContractState(board),hasContractBoard=Object.keys(board).length>0;
  const boardArtifactStatus=String(board.artifact_status||'').toUpperCase();
  const contractBoardCurrent=hasContractBoard&&boardState.label!=='UNAVAILABLE'
    &&board.stale===false&&boardArtifactStatus==='FRESH';
  const actionable=evidenceObject(board.actionable_share),actionableView=actionableShareEvidence(actionable);
  const comparison=evidenceObject(eq.execution_comparison),kx=evidenceObject(eq.kxsol15m);
  const summary=STATE.scopes&&STATE.scopes.telemetry&&STATE.scopes.telemetry.overall&&STATE.scopes.telemetry.overall.summary||{};
  const graded=evidenceCount(summary.n),brier=evidenceMetric(summary.brier),brierEdge=evidenceMetric(summary.brier_edge),contested=evidenceCount(summary.contested_n);
  const forecastKnown=graded!==null&&graded>0&&(brier!==null||brierEdge!==null),cycleFields=['markets_scanned','signals_generated','signals_rejected','decisions_made','abstained'];
  const cycleKnown=!!latest&&cycleFields.some(key=>evidenceCount(latest[key])!==null);
  const gates=hasContractBoard?{available:false,current:false,rows:0,nonIssued:0,missingReasons:0,reasons:[]}:explicitBoardGateReasons();
  const fallbackKnown=forecastKnown||cycleKnown||gates.available;
  const stateLabel=contractState?contractState.label:(fallbackKnown?'PARTIAL':'UNAVAILABLE');
  const stateTone=contractState?contractState.tone:'warn';
  const afterFeeState=evidenceContractState(afterFee),afterFeeN=evidenceCount(afterFee.sample_count);
  const bins=safeEvidenceRows(afterFee.bins).filter(row=>evidenceCount(row.count)!==null);
  const validAfterFee=afterFeeState.label==='AVAILABLE'&&afterFeeN!==null&&afterFeeN>0
    &&bins.length>0&&bins.reduce((total,row)=>total+row.count,0)===afterFeeN;
  const comparisonState=evidenceContractState(comparison);
  const kxState=evidenceContractState(kx);
  const sources=[board.source,comparison.source,evidenceObject(kx.statistical_evidence).source,evidenceObject(kx.caps_evidence).source]
    .filter(value=>typeof value==='string'&&value.trim());
  const uniqueSources=[...new Set(sources)];
  const boardRows=evidenceCount(board.total_rows);
  const windowLabel=(boardRows===null?'board rows unavailable':boardRows+(contractBoardCurrent?' current board rows':' board rows · current validation unavailable'))
    +' · execution artifact '+(comparison.generated_at?evidenceMoment(comparison.generated_at):'time unavailable');
  const anyStale=board.stale===true||comparison.stale===true||evidenceObject(kx.statistical_evidence).stale===true;
  const allCurrent=board.stale===false&&comparison.stale===false&&evidenceObject(kx.statistical_evidence).stale===false;
  const staleness=anyStale?'STALE':(allCurrent?'CURRENT':'UNAVAILABLE');
  let h='<section class="card reveal ops-evidence-card" aria-label="Edge quality and abstention evidence"><div class="evidence-head"><h3>Edge quality &amp; abstention <span class="r">diagnostic only</span></h3>'
    +'<span class="evidence-state '+stateTone+'">'+esc(stateLabel)+'</span></div>'
    +evidenceContextHtml(uniqueSources.join(' + ')||'status/scopes fallback',windowLabel,staleness)
    +'<div class="metric-note">Forecast quality includes markets Dummy did not trade. Cycle counters, board grades, statistical scopes, and execution replays have no live-submit authority and are not profitability evidence.</div>';
  h+='<div class="evidence-kpis">'
    +evidenceKpi('After-fee rows',validAfterFee?commaN(afterFeeN):'UNAVAILABLE',validAfterFee?'ok':'warn')
    +evidenceKpi('Actionable share',actionableView.text,actionableView.available?'ok':'warn')
    +evidenceKpi('Maker / taker',comparisonState.label==='UNAVAILABLE'?'UNAVAILABLE':(comparison.stale===true?'STALE AUDIT':'AUDIT ONLY'),comparisonState.label==='UNAVAILABLE'?'warn':(comparison.stale===true?'warn':''))
    +evidenceKpi('KXSOL15M evidence',kxState.label,kxState.label==='AVAILABLE'?'ok':'warn')
    +'</div>';
  h+='<div class="evidence-section"><div class="evidence-section-head"><b>After-fee edge distribution</b><span>validated current-board rows only</span></div>'
    +renderAfterFeeDistribution(afterFee)+'</div>';
  h+='<div class="evidence-section"><div class="evidence-section-head"><b>Actionable share</b><span>A / B / C research grades · not order authority</span></div>';
  if(actionableView.available){
    h+='<div class="evidence-item"><div class="evidence-main">'+esc(actionableView.text)+'</div><div class="evidence-time">'
      +esc(actionableView.numerator)+' / '+esc(actionableView.denominator)+'</div><div class="evidence-meta">'+esc(actionableView.definition)
      +' · execution authority '+esc(actionable.execution_authority===false?'FALSE':'UNAVAILABLE')+'</div></div>';
  }else h+='<div class="evidence-empty">Actionable share UNAVAILABLE: '+esc(actionableView.reason)+'. No percentage is inferred from raw edge or incomplete counts.</div>';
  h+='</div><div class="evidence-section"><div class="evidence-section-head"><b>Maker versus taker</b><span>witnessed maker vs counterfactual taker · audit only</span></div>'
    +renderExecutionComparison(comparison)+'</div>';
  h+='<div class="evidence-section"><div class="evidence-section-head"><b>KXSOL15M evidence separation</b><span>statistics ≠ caps candidacy ≠ live authority</span></div>'
    +renderKxsol15m(kx)+'</div>';
  if(forecastKnown){
    h+='<div class="evidence-section"><div class="evidence-section-head"><b>Graded forecast context</b><span>all graded forecasts · not only board rows</span></div><div class="evidence-kpis">'
      +evidenceKpi('Graded forecasts',commaN(graded),'')
      +evidenceKpi('Brier',brier===null?'UNAVAILABLE':num(brier,3),brier===null?'warn':'')
      +evidenceKpi('Brier edge vs market',brierEdge===null?'UNAVAILABLE':signed(brierEdge,2),brierEdge===null?'warn':(brierEdge>=0?'ok':'bad'))
      +evidenceKpi('Contested forecasts',contested===null?'UNAVAILABLE':commaN(contested),contested===null?'warn':'')
      +'</div></div>';
  }else h+='<div class="evidence-empty">Forecast edge diagnostics are unavailable; the current payload has no validated graded telemetry sample.</div>';
  h+='<div class="evidence-section"><div class="evidence-section-head"><b>Latest cycle receipt</b><span>aggregate counters only</span></div>';
  if(cycleKnown){
    h+='<div class="evidence-item"><div class="evidence-main">'+esc(String(latest.status||'STATUS_UNAVAILABLE'))+'</div>'
      +'<div class="evidence-time">'+esc(evidenceTime(latest.completed_at||latest.at))+'</div>'
      +'<div class="evidence-meta">'+esc(cycleFields.map(key=>{
        const value=evidenceCount(latest[key]);return value===null?null:key.replaceAll('_',' ')+' '+value;
      }).filter(Boolean).join(' · '))+'</div></div>';
  }else h+='<div class="evidence-empty">Aggregate abstention evidence is unavailable on the latest cycle receipt.</div>';
  h+='<div class="evidence-empty" style="margin-top:6px">Cycle-level reason distribution unavailable: the status contract publishes aggregate abstained and signals-rejected counts, not per-decision reasons.</div></div>';
  h+='<div class="evidence-section"><div class="evidence-section-head"><b>Explicit board gate reasons</b><span>'
    +(contractBoardCurrent||gates.current?'current WATCH / UNATTRIBUTED rows · not cycle causes':'unavailable until a fresh validated board is present')+'</span></div>';
  const contractGateReasons=contractBoardCurrent?safeEvidenceRows(board.gate_reason_counts).filter(reason=>
    typeof reason.tier==='string'&&typeof reason.reason==='string'&&evidenceCount(reason.count)!==null):[];
  if(contractGateReasons.length){
    h+='<div class="evidence-list">'+contractGateReasons.slice(0,5).map(reason=>'<div class="evidence-item"><div class="evidence-main">'
      +tierBadge(reason.tier)+' '+esc(reason.reason)+'</div><div class="reason-count">'+commaN(reason.count)+'</div>'
      +'<div class="evidence-meta">Fresh complete-board reason count; not a cycle cause or execution authority.</div></div>').join('')+'</div>';
  }else if(gates.reasons.length){
    h+='<div class="evidence-list">'+gates.reasons.slice(0,5).map(reason=>'<div class="evidence-item"><div class="evidence-main">'
      +tierBadge(reason.tier)+' '+esc(reason.label)+'</div><div class="reason-count">'+commaN(reason.count)+'</div>'
      +'<div class="evidence-meta">Persisted reason code: '+esc(reason.raw)+'</div></div>').join('')+'</div>';
    if(gates.missingReasons)h+='<div class="evidence-empty" style="margin-top:6px">'+commaN(gates.missingReasons)+' current non-issued row(s) have no explicit reason field and are excluded.</div>';
  }else if(!contractBoardCurrent&&!gates.current)h+='<div class="evidence-empty">Board gate-reason evidence is unavailable because the board is missing, malformed, stale, or not explicitly fresh. Stored reasons are not rendered as current.</div>';
  else if(!gates.available)h+='<div class="evidence-empty">Board gate-reason evidence is unavailable because no validated board snapshot is loaded.</div>';
  else if(!gates.nonIssued)h+='<div class="evidence-empty">No current WATCH or UNATTRIBUTED rows are present in the visible board snapshot. This does not establish a cycle-level reason.</div>';
  else h+='<div class="evidence-empty">Current non-issued board rows have no explicit reason fields; no reason is inferred.</div>';
  return h+'</div></section>';
}
function edgeQualityCard(){return renderEdgeQuality();}
function abilityTile(group,name,description,proof,href,crypto=false){
  const body='<div class="ak">'+esc(group)+'</div><div class="an">'+esc(name)+'</div><div class="ad">'+esc(description)+'</div><span class="ap">'+esc(proof)+'</span>';
  return href?'<a class="ability-tile'+(crypto?' crypto':'')+'" href="'+href+'">'+body+'</a>'
    :'<div class="ability-tile'+(crypto?' crypto':'')+'">'+body+'</div>';
}
function capabilityCatalog(){
  const abilities=[
    ['Observe','Market perception','Allowlisted discovery, public context, identity normalization, provenance, freshness, deduplication, and explicit abstention.','observation ledger · source health','#/glossary',false],
    ['Crypto · loops','Paper twin + horizon evidence','DummyCryptoPaperTwin (5-minute) and DummyCryptoHorizonEvidence (10-minute) preserve asset × timeframe × strategy evidence.','2 named loops · zero capital authority','#/charts',true],
    ['Crypto · visualize','Multi-timeframe research charts','BTC, ETH, and SOL closed candles across 15m, 1h, 4h, 1d, and 1w with deterministic indicators and pattern markers.','immutable Market Observer bundles','#/charts',true],
    ['Sports · model','Seven-league intelligence','History, play-by-play, power ratings, scoring distributions, live state, props, and league-specific specialists.','point-in-time and walk-forward','#/scope/sports/mlb',false],
    ['Forecast','Probability engines','Market anchors, statistical kernels, simulations, and attributed specialist forecasts remain separately scored.','schema-bound forecasts','#/scope/crypto/btc',false],
    ['Council','Model Arsenal + dissent','Four exact model roles and vertical specialists preserve disagreement behind stored redacted proof and paid-call gates.','zero automatic influence','#/arsenal',false],
    ['Calibrate','Trust + uncertainty','Brier, log loss, ECE/MCE, debiasing, contested scoring, scope trust, and uncertainty intervals drive fusion.','settled evidence only','#/scope/crypto/btc',false],
    ['Evaluate','Walk-forward + backtests','Temporal folds, clustered bootstrap, fees, liquidity, CLV, partial fills, and negative controls test claims.','predict before update','#/scope/sports/nba',false],
    ['Allocate','Portfolio construction','Evidence-adjusted edge, settlement velocity, candidate splitting, correlation limits, quarter-Kelly, and stage ladders divide one bounded pot.','grant ≤ ask · Σ grants ≤ pot','#/glossary',false],
    ['Constrain','Risk + execution firewall','Drawdown, cluster, price, liquidity, TTL, session, credential, sealed-cap, proof-lock, and LIMIT-only gates can only shrink intent.','code cannot self-authorize','#/glossary',false],
    ['Memory','Settlement + audit memory','Orders, fills, cancels, outcomes, corrections, account snapshots, and promotion dossiers remain separately attributable.','append-only truth + corrections','#/glossary',false],
    ['Learn','Autoresearch + evolution','Strategy mining, tuning, quality-diversity search, crossover, ablation, chaos, and fragility produce challengers.','observational until promoted','#/glossary',false],
    ['Reflect','Metacognition + self-scout','Film room, recruiting, matchup lens, top-threat analysis, no-edge maps, and development tracking challenge the organism itself.','diagnosis cannot promote itself','#/glossary',false],
    ['Operate','Fleet reliability','Watchdog, healer, readiness, snapshots, retention, prune, vacuum, and allowlisted rotation isolate failures.','45 independent retry boundaries','#/glossary',false],
    ['Expose','Operator experience','Overview, scoped diagnostics, charts, Arsenal, glossary, command palette, themes, and desktop outcome notifications are read-only.','loopback GET · no mutation','#/charts',false],
    ['Integrate','Observer MCP','Candles, snapshots, indicators, patterns, charts, network status, and source health stay provider-neutral and authority-free.','read-only tools · false authority','#/charts',false],
  ];
  return '<section class="ability-catalog" aria-label="Complete capability catalog"><div class="section-head"><h2>All abilities</h2><p>Public-release catalog · research, operations, and authority stay separate</p></div><div class="ability-grid">'
    +abilities.map(a=>abilityTile(...a)).join('')+'</div></section>';
}
function overviewView(){
  const o=STATE.overview;
  if(!o||o.error)return topbar('Overview','live Kalshi account & execution control')
    +capabilityCatalog()
    +'<div class="ops-intel-grid">'+systemHealthCard()+edgeQualityCard()+'</div>'+skeleton();
  const account=o.live_account||{},controls=o.live_controls||(STATE.status&&STATE.status.live_controls)||{};
  const accountAvailable=Number.isInteger(account.balance_cents)&&!account.invalid;
  const accountFresh=accountAvailable&&account.stale===false&&String(account.status||'').toUpperCase()!=='ERROR';
  const controlState=String(controls.state||'invalid_or_blocked').replace(/_/g,' ').toUpperCase();
  const proof=account.http_proof||{},source=account.source||{};
  let h=topbar('Overview','live Kalshi account & execution control');
  // Hero band: cached GET-only live account + explicit live authority.
  h+='<div class="grid hero overview-hero">';
  h+='<div class="card acct reveal"><div><div class="lab" style="font-size:9.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--faint);display:flex;gap:8px;align-items:center">Live Kalshi account <span class="badge"><span class="d"></span>'+esc(accountFresh?'fresh':'read-only')+'</span></div>'
    +'<div class="big '+(accountFresh?'pos':'')+'">'+flip(accountAvailable?fmtUSD(account.balance_cents):'SNAPSHOT PENDING')+'</div>'
    +'<div class="sub" style="font-family:var(--mono);color:var(--muted);margin-top:4px">'+(account.generated_at?'captured '+esc(ago(account.generated_at)):'No validated cached live-account snapshot')+' · page requests never query Kalshi</div></div></div>';
  h+='<div class="card reveal"><h3>Open live state <span class="r">cached broker reads</span></h3><div class="mini">'
    +miniRow('Open positions',accountAvailable?commaN(account.open_positions_count||0):'—',(account.open_positions_count||0)>0?'amb':'')
    +miniRow('Open orders',accountAvailable?commaN(account.open_orders_count||0):'—',(account.open_orders_count||0)>0?'amb':'')
    +miniRow('Orders in retained window',accountAvailable?commaN(account.historical_orders_count||0):'—','')
    +miniRow('Fills in retained window',account.historical_fills_count==null?'—':commaN(account.historical_fills_count),'')
    +'</div><div class="sub" style="margin-top:8px;color:var(--faint)">'+esc(source.history_scope||'live portfolio retention window')+' · not all-time P&amp;L</div></div>';
  h+='<div class="card summarycard reveal"><div class="mini">'
    +miniRow('Live authority',controls.execution_authority===true?'ARMED':'LOCKED',controls.execution_authority===true?'neg':'amb')
    +miniRow('Authority state',esc(controlState),'cy')
    +miniRow('Proof scope','ONE CONTROLLED','')
    +miniRow('Order policy','LIMIT ONLY','pos')
    +'</div></div>';
  h+='</div>';
  h+='<div class="outcome-brief '+(controls.execution_authority===true?'good':'')+' reveal" role="note"><span class="verdict">'
    +(controls.execution_authority===true?'One-proof live authority is armed':'Live submission remains locked')+'</span><span class="explain">'
    +(controls.execution_authority===true?'An order still requires an active LIVE session, fresh market/account/risk state, every central firewall check, and a limit-only submit. This page cannot place orders.'
      :'<b>'+esc(controls.blocker||'DEFAULT_DISABLED')+'</b>. Paper/shadow results cannot unlock or block LIVE; only the explicit live-control contracts can change this state.')+'</span></div>';
  h+='<div class="card reveal" style="margin-bottom:var(--s3)"><h3>Paper history retired <span class="r">RETIRED_NON_AUTHORITATIVE</span></h3>'
    +'<div class="sub" style="color:var(--muted)">Paper bankroll, paper P&amp;L, and paper-result promotion gates were removed from this operator view and from live authority. Raw ledger/history remains preserved for audit; it is not rewritten or deleted.</div></div>';
  h+=capabilityCatalog();
  h+='<div class="ops-intel-grid">'+systemHealthCard()+edgeQualityCard()+'</div>';
  h+=tierPerformanceCard();
  h+='<section id="readiness"><div class="section-head"><h2>Live control contract</h2><p>Local checks only · no broker contact</p></div>';
  h+='<div class="card reveal"><div class="mini">'
    +miniRow('Central firewall',controls.central_firewall_required===true?'REQUIRED':'UNKNOWN',controls.central_firewall_required===true?'pos':'amb')
    +miniRow('Market orders',controls.market_orders_allowed===false?'DISABLED':'UNKNOWN',controls.market_orders_allowed===false?'pos':'neg')
    +miniRow('GET-only account proof',proof.get_only===true?'VERIFIED':(accountAvailable?'UNVERIFIED':'PENDING'),proof.get_only===true?'pos':'amb')
    +miniRow('Account source',source.provider?esc(String(source.provider).toUpperCase()):'PENDING','')
    +'</div></div></section>';
  h+='<div class="dockband"><div class="section-head"><h2>Forecast diagnostics</h2><p>Probability quality across graded markets — not trading profit</p></div>';
  h+=accuracyPanel();
  h+='<div class="card reveal" style="margin-top:var(--s3)"><h3>Active model — fused sources <span class="r">weight</span></h3><div>'
    +((o.active_sources||[]).map(s=>'<span class="chip">'+esc(s.source)+' <b>'+num(s.weight,2)+'</b></span>').join('')||'<div class="empty">no weights</div>')+'</div></div>';
  h+=modelArsenalSummaryCard();
  return h+'</div>';
}
function miniRow(k,v,cls){return '<div class="row"><span class="k">'+k+'</span><span class="vv '+(cls||'')+'">'+flip(v)+'</span></div>';}
// ---------- accuracy & improvement telemetry ----------
function trendMeta(t){return t==='improving'?['up','▲']:t==='declining'?['dn','▼']:t==='flat'?['flat','▬']:['thin','·'];}
function improvBig(imp){
  if(!imp||imp.trend==null||imp.trend==='thin')return '<span class="trend thin">· building sample</span>';
  const[cls,ar]=trendMeta(imp.trend);const db=imp.delta_brier;
  const d=db==null?'':'<span class="dd">Δ '+(db>0?'−':'+')+Math.abs(db).toFixed(3)+' Brier</span>';
  return '<span class="trend '+cls+'">'+ar+' '+esc(imp.trend)+' '+d+'</span>';
}
function improvArrow(imp){
  if(!imp||imp.trend==null||imp.trend==='thin')return '<span class="td thin">·</span>';
  const[cls,ar]=trendMeta(imp.trend);const db=imp.delta_brier;
  return '<span class="td '+cls+'">'+ar+(db==null?'':' '+(db>0?'−':'+')+Math.abs(db).toFixed(3))+'</span>';
}
function improvDot(t){const[cls,ar]=trendMeta(t);return '<span class="td '+cls+'">'+ar+'</span>';}
function heatColor(e){if(e==null)return '';const a=Math.max(-.06,Math.min(.06,e))/.06;
  return a>=0?'background:rgba(47,227,143,'+(0.05+a*0.22).toFixed(3)+')':'background:rgba(255,107,122,'+(0.05+(-a)*0.22).toFixed(3)+')';}
function heatmap(matrix){
  if(!matrix||!matrix.length)return '';
  const scopes=[],cols=[],by={};
  matrix.forEach(c=>{const sk=c.scope;if(!scopes.includes(sk))scopes.push(sk);if(!cols.includes(c.bet_type))cols.push(c.bet_type);by[sk+'|'+c.bet_type]=c;});
  let h='<div class="heatwrap"><table class="heat"><thead><tr><th>scope</th>'+cols.map(c=>'<th>'+esc(prettyBet(c))+'</th>').join('')+'</tr></thead><tbody>';
  scopes.forEach(sk=>{h+='<tr><td class="hs">'+esc(sk)+'</td>'+cols.map(c=>{const cell=by[sk+'|'+c];
    if(!cell)return '<td class="hc empty2"></td>';
    return '<td class="hc" style="'+heatColor(cell.brier_edge)+'" title="'+esc(prettyBet(c))+' · n='+cell.n+' · hit '+pct(cell.hit_rate)+' · Brier '+num(cell.brier)+' · '+esc(cell.trend||'')+'">'
      +'<span class="he">'+(cell.brier_edge==null?'—':signed(cell.brier_edge,2))+'</span>'+improvDot(cell.trend)+'</td>';}).join('')+'</tr>';});
  return h+'</tbody></table></div>';
}
function accuracyPanel(){
  const tel=STATE.scopes&&STATE.scopes.telemetry;
  if(!tel||!tel.overall)return '';
  const s=tel.overall.summary||{},imp=tel.overall.improvement||{};
  if(!s.n)return '';
  let h='<div class="card reveal" style="margin-bottom:var(--s3)"><h3>Forecast quality &amp; improvement <span class="r">'+commaN(s.n)+' graded forecasts · recent vs prior</span></h3>';
  h+='<div class="metric-note">Diagnostic only: this population includes markets the engine did not trade. Forecast quality has no live-submit authority and is not a claim of realized profitability.</div>';
  h+='<div class="acc-hero">'
    +'<div class="acc-stat"><div class="lab">Brier</div><div class="val">'+flip(num(s.brier))+'</div><div class="sub">lower = sharper</div></div>'
    +'<div class="acc-stat"><div class="lab">Directional hit rate</div><div class="val '+(s.hit_rate>=.5?'pos':'')+'">'+flip(pct(s.hit_rate))+'</div><div class="sub">all graded forecasts</div></div>'
    +'<div class="acc-stat"><div class="lab">Brier edge vs market</div><div class="val '+sgn(s.brier_edge)+'">'+flip(signed(s.brier_edge,2))+'</div><div class="sub">'+commaN(s.contested_n||0)+' contested</div></div>'
    +'<div class="acc-stat"><div class="lab">Improvement</div><div class="val">'+improvBig(imp)+'</div><div class="sub">Brier fell = sharper</div></div>'
    +'</div>';
  const series=tel.series||[];
  if(series.length>1){
    const key=series.some(p=>p.brier_edge!=null)?'brier_edge':(series.some(p=>p.hit_rate!=null)?'hit_rate':'brier');
    const pts=series.map(p=>p[key]).filter(x=>x!=null);
    const lab=key==='brier_edge'?'edge vs market over time':(key==='hit_rate'?'hit rate over time':'Brier over time (lower = sharper)');
    if(pts.length>1)h+='<div style="margin:2px 0 12px"><div class="sub" style="font-family:var(--mono);color:var(--faint);margin-bottom:4px">'+lab+' · '+series.length+' snapshots</div>'
      +spark(pts,{w:640,h:46,color:key==='brier'?'var(--amber)':'var(--acc)'})+'</div>';
  }
  h+='<div class="sub" style="font-family:var(--mono);color:var(--faint);margin:2px 0 10px">edge by scope × bet type — green beats the line, arrow = trend</div>';
  h+=heatmap(tel.matrix||[]);
  return h+'</div>';
}
function settledTodayCard(scope){
  const rows=scope.settled_today||[];
  if(!rows.length)return '';
  const correct=rows.filter(r=>r.correct).length;
  const pctc=Math.round(correct/rows.length*100);
  const visible=[...rows].sort((a,b)=>String(b.settled_at||'').localeCompare(String(a.settled_at||''))).slice(0,100);
  let h='<div class="card pad0 reveal" style="margin-top:var(--s3)"><h3 style="padding:var(--s3) var(--s3) var(--s2)">Settled today '
    +'<span class="r"><b class="'+(pctc>=50?'res-ok':'res-no')+'">'+correct+'/'+rows.length+'</b> correct · '+pctc+'%</span></h3>';
  h+='<div style="max-height:300px;overflow:auto"><table><thead><tr><th>Market</th><th>Bet</th><th>Lean</th><th>Model</th><th>Result</th><th>Call</th></tr></thead><tbody>';
  visible.forEach(r=>{h+='<tr><td title="'+esc(r.ticker)+'">'+esc(r.label||r.matchup||(r.ticker||'').slice(0,26))+'</td><td>'+esc(prettyBet(r.bet_type))+'</td>'
    +'<td>'+esc(r.lean)+(r.traded?' <span style="color:var(--amber);font-size:10px">·traded</span>':'')+'</td>'
    +'<td>'+num(r.prob,2)+'</td><td>'+(r.result?'YES':'NO')+'</td>'
    +'<td>'+(r.correct?'<span class="res-ok">✓</span>':'<span class="res-no">✗</span>')+'</td></tr>';});
  if(rows.length>visible.length)h+='<tr><td class="table-more" colspan="6">Showing the 100 most recent of '+commaN(rows.length)+' settlements.</td></tr>';
  return h+'</tbody></table></div></div>';
}
// delegated bet-type tab switch (survives re-renders)
document.addEventListener('click',e=>{
  const action=e.target.closest&&e.target.closest('[data-action]');
  if(action){
    const name=action.getAttribute('data-action');
    if(name==='search'){cmdOpen();return;}
    if(name==='refresh'){poll();return;}
    if(name==='chart-refresh'){STATE.marketChart.loadedKey='';ensureMarketChartData(true);render();return;}
    if(name==='readiness'){
      if(ROUTE!=='#/overview'){location.hash='#/overview';setTimeout(()=>document.getElementById('readiness')?.scrollIntoView({behavior:REDUCE?'auto':'smooth'}),80);}
      else document.getElementById('readiness')?.scrollIntoView({behavior:REDUCE?'auto':'smooth'});
      return;
    }
  }
  const assetChoice=e.target.closest&&e.target.closest('[data-chart-asset]');
  if(assetChoice){STATE.marketChart.asset=assetChoice.getAttribute('data-chart-asset');STATE.marketChart.data=null;STATE.marketChart.error=null;STATE.marketChart.loadedKey='';render();return;}
  const timeframeChoice=e.target.closest&&e.target.closest('[data-chart-timeframe]');
  if(timeframeChoice){STATE.marketChart.timeframe=timeframeChoice.getAttribute('data-chart-timeframe');STATE.marketChart.data=null;STATE.marketChart.error=null;STATE.marketChart.loadedKey='';render();return;}
  const tab=e.target.closest&&e.target.closest('.bt-tab');
  if(tab){const card=tab.closest('.card'),bt=tab.getAttribute('data-bt');
    if(card.classList.contains('daily-guide')&&card.dataset.league){GUIDE_FILTERS[card.dataset.league]=tab.dataset.marketType||'all';card.dataset.filter=tab.dataset.marketType||'all';}
    card.querySelectorAll('.bt-tab').forEach(t=>{const on=t===tab;t.classList.toggle('on',on);t.setAttribute('aria-selected',String(on));t.tabIndex=on?0:-1;});
    revealGuideTab(tab,true);
    card.querySelectorAll('.bt-panel').forEach(p=>{const on=p.getAttribute('data-bt')===bt;p.classList.toggle('on',on);p.hidden=!on;
      if(on&&p.dataset.loaded!=='true'){
        const kind=p.parentElement&&p.parentElement.dataset.kind;
        if(kind==='guide'){
          const lazy=LAZY_GUIDE[bt]||{rows:[],label:'All markets',isAll:true,key:bt};
          p.innerHTML=dayGames(lazy.rows,lazy.key,lazy.label,lazy.isAll);
        }
        p.dataset.loaded='true';
      }});return;}
  const gh=e.target.closest&&e.target.closest('.ghead');
  if(gh){const open=gh.parentElement.classList.toggle('open'),body=gh.parentElement.querySelector('.gbody');gh.setAttribute('aria-expanded',String(open));if(body)body.hidden=!open;}
});
document.addEventListener('keydown',e=>{
  const tab=e.target.closest&&e.target.closest('.bt-tab[role="tab"]');if(!tab)return;
  const tabs=[...tab.closest('[role="tablist"]').querySelectorAll('.bt-tab[role="tab"]')];
  const i=tabs.indexOf(tab);let next=null;
  if(e.key==='ArrowRight'||e.key==='ArrowDown')next=(i+1)%tabs.length;
  if(e.key==='ArrowLeft'||e.key==='ArrowUp')next=(i-1+tabs.length)%tabs.length;
  if(e.key==='Home')next=0;if(e.key==='End')next=tabs.length-1;
  if(next==null)return;e.preventDefault();tabs[next].focus();tabs[next].click();
});
// ---- market-type readability ----
function titleCase(s){return String(s).replace(/_/g,' ').replace(/\b\w/g,c=>c.toUpperCase());}
const _BT_BASE={winner:'Moneyline',spread:'Spread',total:'Total (O/U)',team_total:'Team Total',
  yrfi:'1st-Inning Run',market:'Price',ladder:'Price Ladder','15m_direction':'15-min Up/Down',
  between:'Range',other:'Other'};
const _BT_SEG={f5:'First 5',f3:'First 3',f7:'First 7',h1:'1st Half',h2:'2nd Half',
  q1:'Q1',q2:'Q2',q3:'Q3',q4:'Q4',p1:'P1',p2:'P2',p3:'P3'};
const _BT_MKT={winner:'Moneyline',spread:'Spread',total:'Total',team_total:'Team Total'};
const _BT_PROP={home_runs:'Home Runs',hits:'Hits',strikeouts:'Strikeouts',rbis:'RBIs',outs:'Outs',
  stolen_bases:'Stolen Bases',hits_runs_rbis:'H+R+RBI',total_bases:'Total Bases'};
function prettyBet(bt){
  if(!bt)return '—';
  if(_BT_BASE[bt])return _BT_BASE[bt];
  let m;
  if((m=String(bt).match(/^prop_(.+)$/)))return 'Prop · '+(_BT_PROP[m[1]]||titleCase(m[1]));
  if((m=String(bt).match(/^(f5|f3|f7|h1|h2|q1|q2|q3|q4|p1|p2|p3)_(winner|spread|total|team_total)$/)))
    return _BT_SEG[m[1]]+' · '+_BT_MKT[m[2]];
  return titleCase(bt);
}
const _MON=['Jan','Feb','Mar','Apr','May','Jun','Jul','Aug','Sep','Oct','Nov','Dec'];
function prettyMatchup(m){
  const mm=String(m||'').match(/^(\d{2})([A-Z]{3})(\d{2})(\d{4})?([A-Z0-9]+)$/);
  if(!mm)return m||'?';
  const mon={JAN:'Jan',FEB:'Feb',MAR:'Mar',APR:'Apr',MAY:'May',JUN:'Jun',JUL:'Jul',AUG:'Aug',SEP:'Sep',OCT:'Oct',NOV:'Nov',DEC:'Dec'}[mm[2]]||mm[2];
  return mm[5]+' · '+mon+' '+parseInt(mm[3],10);
}
function dateTag(d){return d?' <span style="color:var(--faint);font-size:11px">· '+esc(d)+'</span>':'';}
function prettyDay(d,today){
  if(d===today)return 'Today';
  const t=Date.parse(today+'T00:00:00Z'),dd=Date.parse(d+'T00:00:00Z');
  if(!isNaN(t)&&!isNaN(dd)){const diff=Math.round((dd-t)/86400000);
    if(diff===1)return 'Tomorrow';if(diff===-1)return 'Yesterday';}
  const p=d.split('-');return (_MON[(+p[1]||1)-1]||'')+' '+(+p[2]||'');
}
// ---- daily sports guide: event date -> market category -> ranked matchups ----
function boardFor(label){return STATE.board&&STATE.board[String(label).toLowerCase()];}
function localISODate(){const d=new Date(),p=n=>String(n).padStart(2,'0');return d.getFullYear()+'-'+p(d.getMonth()+1)+'-'+p(d.getDate());}
function rowEventDate(r){
  if(r.event_date)return r.event_date;
  const m=String(r.ticker||'').match(/-(\d{2})([A-Z]{3})(\d{2})/);
  if(!m)return '';
  const month={JAN:'01',FEB:'02',MAR:'03',APR:'04',MAY:'05',JUN:'06',JUL:'07',AUG:'08',SEP:'09',OCT:'10',NOV:'11',DEC:'12'}[m[2]];
  return month?'20'+m[1]+'-'+month+'-'+m[3]:'';
}
function eventKey(r){return r.event_id||String(r.ticker||'').split('-')[1]||((r.matchup||'?')+'|'+rowEventDate(r));}
function eventCount(rows){return new Set(rows.map(eventKey)).size;}
function countLabel(n,word){return n+' '+word+(n===1?'':'s');}
function opportunity(r){
  if(r.after_fee_edge!=null&&Number.isFinite(Number(r.after_fee_edge)))return Number(r.after_fee_edge);
  return r.edge==null||!Number.isFinite(Number(r.edge))?Number.NEGATIVE_INFINITY:Math.abs(Number(r.edge));
}
function sideFor(r){
  const explicit=String(r.value_side||r.pick||'').toUpperCase();
  if(explicit==='YES'||explicit==='NO')return explicit;
  return r.edge==null||!Number.isFinite(Number(r.edge))?null:(Number(r.edge)>=0?'YES':'NO');
}
function opportunityLabel(r){const edge=opportunity(r);if(!Number.isFinite(edge))return '—';return r.after_fee_edge!=null?signed(edge,1):pct(edge,1);}
function sideProb(r,key){const v=r[key];if(v==null)return null;return sideFor(r)==='NO'?1-v:v;}
function marketName(r){
  if(String(r.bet_type||'').startsWith('prop_')&&r.title){
    const m=String(r.title).match(/^\s*(.+?)\s*:\s*(.+?)\s*\??\s*$/);
    if(m)return m[1].trim()+' · '+m[2].trim().replace(/\?$/,'');
  }
  return r.market||String(r.ticker||'').slice(0,30);
}
function domId(s){return String(s||'guide').toLowerCase().replace(/[^a-z0-9_-]+/g,'-');}
function revealGuideTab(tab,smooth){
  if(!tab)return;const strip=tab.parentElement;if(!strip||strip.scrollWidth<=strip.clientWidth)return;
  const left=Math.max(0,tab.offsetLeft-(strip.clientWidth-tab.offsetWidth)/2);
  strip.scrollTo({left:left,behavior:smooth&&!REDUCE?'smooth':'auto'});
}
function modelCell(r){
  // The independent model view: our own model's both-sides call, present even
  // when the promotion ladder keeps it out of the traded number. Shows the
  // recommended action + model-vs-market edge, or an em dash when no model
  // priced this market (e.g. a prop with no batter model yet).
  if(!r.has_independent_model||r.model_recommendation==null)return '<span class="tier-badge" style="border-style:dashed">no model</span>';
  const e=r.model_edge,cls=(e==null?'':(e>=0?'pos':'neg'));
  return '<span class="pill '+(String(r.model_side||'').toUpperCase()==='NO'?'no':'yes')+'" style="white-space:normal">'+esc(r.model_recommendation)+'</span>'
    +(e==null?'':' <b class="'+cls+'">'+signed(e,3)+'</b>');
}
function gameBreakdown(rows){
  rows=[...rows].sort((a,b)=>opportunity(b)-opportunity(a));
  return '<div style="overflow:auto"><table><thead><tr><th>Category</th><th>Market</th><th>Value side</th><th>Traded P</th><th>Market P</th><th>Net edge</th><th>Independent model</th><th>Tier / reason</th></tr></thead><tbody>'
    +rows.map(r=>{const side=sideFor(r),edge=opportunity(r);
      return '<tr><td>'+esc(prettyBet(r.bet_type))+'</td><td title="'+esc(r.ticker)+'">'+esc(marketName(r))+'</td>'
        +'<td>'+(side?'<span class="pill '+(side==='NO'?'no':'yes')+'">'+side+'</span>':'—')+'</td>'
        +'<td>'+num(sideProb(r,'probability'),2)+'</td><td>'+num(sideProb(r,'market_probability'),2)+'</td>'
        +'<td class="'+(!Number.isFinite(edge)?'':(edge>=0?'pos':'neg'))+'">'+opportunityLabel(r)+'</td>'
        +'<td>'+modelCell(r)+'</td>'
        +'<td title="'+esc(r.tier_reason||r.tier_display_reason||'')+'">'+tierBadge(boardTier(r))+'<span class="tier-sample">'+esc(boardTierReason(r))+'</span></td></tr>';}).join('')
    +'</tbody></table></div>';
}
function dayGames(rows,key,filterLabel,isAll){
  const byGame={};rows.forEach(r=>{const k=eventKey(r);(byGame[k]=byGame[k]||[]).push(r);});
  const games=Object.keys(byGame).sort((a,b)=>{const gap=Math.max(...byGame[b].map(opportunity))-Math.max(...byGame[a].map(opportunity));return gap||String(byGame[a][0].matchup||a).localeCompare(String(byGame[b][0].matchup||b));});
  if(!games.length)return '<div class="empty">No events in this category.</div>';
  const note=isAll?'All-market view. Open a matchup for its complete priced board.':'Filtered to <b>'+esc(filterLabel)+'</b>. Matchup rankings, counts, and expanded rows stay inside this category; choose All markets for the complete board.';
  const counts=games.length+' matchup'+(games.length===1?'':'s')+' · '+rows.length+' market'+(rows.length===1?'':'s');
  return '<div class="guide-filter-note" role="status" aria-live="polite"><span>'+note+'</span><span class="counts">'+counts+'</span></div>'
    +'<div class="games">'+games.map((k,i)=>{const ranked=byGame[k];
    const best=[...ranked].sort((a,b)=>opportunity(b)-opportunity(a))[0],side=sideFor(best),be=opportunity(best);
    const bodyId=domId(key+'-'+k+'-'+i),count=ranked.length+' market'+(ranked.length===1?'':'s'),value=side&&Number.isFinite(be)?side+' · '+opportunityLabel(best):'No executable quote';
    return '<div class="game"><button type="button" class="ghead" aria-expanded="false" aria-controls="'+bodyId+'"><span class="gx"><b>#'+(i+1)+'</b> ▸</span><span class="gm">'+esc(prettyMatchup(best.matchup||'?'))+'<small>'+esc(marketName(best))+'</small></span><span class="gc">'+count+'</span><span class="ge"><span class="guide-value">'+esc(value)+'</span>'+gameTierSummary(ranked)+'</span></button>'
      +'<div class="gbody" id="'+bodyId+'" hidden><div class="sub" style="padding:8px 4px;color:var(--muted)">'+(isAll?'Complete matchup board':'Filtered '+esc(filterLabel)+' breakdown')+' · ranked by quoted ask + taker-fee net edge · forecast guide, not an order</div>'+gameBreakdown(ranked)+'</div></div>';}).join('')+'</div>';
}
function dailyGuideCard(label){
  const grp=boardFor(label)||{},all=[];
  Object.values(grp).forEach(rows=>rows.forEach(r=>{if(rowEventDate(r))all.push(r);}));
  const today=localISODate(),todayRows=all.filter(r=>rowEventDate(r)===today);
  // A daily guide is strictly today's slate.  Future rows can never stand in
  // for an empty/off-season day because that makes the header and rankings lie.
  const active=todayRows;
  const sports=(STATE.scopes&&STATE.scopes.verticals&&STATE.scopes.verticals.SPORTS)||{};
  const scope=(sports.scopes&&sports.scopes[label])||null;
  const season=scope?(scope.season_status||(scope.in_season===false?'off':'unknown')):'unknown';
  const refreshed=STATE.boardMeta&&STATE.boardMeta.generated_at;
  const requested=GUIDE_FILTERS[label]||'all';
  const preferred=requested==='all'||active.some(r=>r.bet_type===requested)?requested:'all';
  if(preferred!==requested)GUIDE_FILTERS[label]='all';
  let h='<div class="card reveal daily-guide" data-league="'+esc(label)+'" data-season="'+esc(season)+'" data-filter="'+esc(preferred)+'" style="margin-bottom:var(--s3)"><h3>Today’s '+esc(label)+' betting guide <span class="r">refreshed '+ago(refreshed)+'</span></h3>';
  h+='<div class="sub" style="margin:-3px 0 12px;color:var(--muted)">'+esc(prettyDay(today,today))+' · '+countLabel(eventCount(todayRows),'event')+' · '+countLabel(todayRows.length,'priced market')+(active.length?' · ranked by executable after-fee value · click any matchup for market breakdown':'')+'</div>';
  if(!todayRows.length){
    const detail=season==='off'
      ? esc(label)+' is currently out of season. It stays available in the league menu year-round; this guide will populate only when a current-day slate is listed.'
      : (season==='upcoming'
        ? esc(label)+' is in preseason or awaiting its next slate. It stays available year-round, with no future event substituted for today.'
        : 'No current-day slate is available. Future-dated markets are intentionally excluded from today’s rankings.');
    h+='<div class="empty" style="margin-bottom:12px"><b>No '+esc(label)+' events are listed for today.</b><br><span style="color:'+(season==='off'?'var(--amber)':'var(--faint)')+'">'+detail+'</span></div>';
  }
  if(!active.length)return h+'</div>';
  const types=[...new Set(active.map(r=>r.bet_type).filter(Boolean))].sort((a,b)=>prettyBet(a).localeCompare(prettyBet(b)));
  const tabs=['all',...types],selected=tabs.includes(preferred)?preferred:'all';LAZY_GUIDE={};
  h+='<div class="bt-tabs" role="tablist" aria-label="'+esc(label)+' market categories">'+tabs.map(t=>{const rows=t==='all'?active:active.filter(r=>r.bet_type===t),key='guide-'+label.toLowerCase()+'-'+t,labelText=t==='all'?'All markets':prettyBet(t),on=t===selected;LAZY_GUIDE[key]={rows:rows,label:labelText,isAll:t==='all',key:key};
    return '<button type="button" id="'+domId(key+'-tab')+'" role="tab" aria-selected="'+String(on)+'" aria-controls="'+domId(key+'-panel')+'" tabindex="'+(on?'0':'-1')+'" class="bt-tab'+(on?' on':'')+'" data-market-type="'+esc(t)+'" data-bt="'+esc(key)+'">'+esc(labelText)+'<span class="c" aria-label="'+countLabel(eventCount(rows),'matchup')+'">'+eventCount(rows)+'</span></button>';}).join('')+'</div>';
  h+='<div class="bt-panels" data-kind="guide">'+tabs.map(t=>{const key='guide-'+label.toLowerCase()+'-'+t,lazy=LAZY_GUIDE[key],on=t===selected;return '<div id="'+domId(key+'-panel')+'" role="tabpanel" aria-labelledby="'+domId(key+'-tab')+'" class="bt-panel'+(on?' on':'')+'" data-bt="'+esc(key)+'" data-loaded="'+String(on)+'" '+(on?'':'hidden')+'>'+(on?dayGames(lazy.rows,lazy.key,lazy.label,lazy.isAll):'')+'</div>';}).join('')+'</div>';
  return h+'</div>';
}
function walkCard(vert,label){
  if(vert!=='SPORTS')return '';
  const w=STATE.walk&&STATE.walk[String(label).toLowerCase()];
  if(!w)return '';
  const LABELS={glicko:'Glicko-2',pythagenpat:'Pythagenpat',mov_elo:'MOV-Elo',four_factors:'Four Factors',epa:'EPA'};
  // generic over whatever models the artifact carries; back-compat with a flat report
  let models=Object.keys(w).filter(k=>w[k]&&typeof w[k]==='object'&&w[k].n).map(k=>[LABELS[k]||k,w[k]]);
  if(!models.length&&w.n)models=[['Glicko-2',w]];
  if(!models.length)return '';
  models.sort((a,b)=>(b[1].edge_vs_baseline||0)-(a[1].edge_vs_baseline||0));
  let h='<div class="card reveal" style="margin-top:var(--s3)"><h3>Model backtest <span class="r">point-in-time lake · walk-forward, no look-ahead</span></h3>';
  h+='<div style="overflow-x:auto"><table><thead><tr><th>Analytic</th><th>Games</th><th>Hit</th><th>Brier</th><th>vs coin</th><th>Edge</th><th>Log-loss</th></tr></thead><tbody>';
  models.forEach(([nm,m])=>{const e=m.edge_vs_baseline;
    h+='<tr><td>'+nm+'</td><td>'+commaN(m.n)+'</td><td class="'+(m.hit_rate>=.5?'pos':'')+'">'+pct(m.hit_rate)+'</td>'
      +'<td>'+num(m.brier)+'</td><td>'+num(m.baseline_brier)+'</td>'
      +'<td class="'+(e>=0?'pos':'neg')+'">'+signed(e,2)+'</td><td>'+num(m.log_loss)+'</td></tr>';});
  return h+'</tbody></table></div><div class="sub" style="font-family:var(--mono);color:var(--faint);margin-top:6px">two independent analytics graded on the lake — the ensemble weights each by its contested-Brier edge</div></div>';
}
function betTypeCard(bt){
  const keys=bt?Object.keys(bt):[];
  if(!keys.length)return '';
  let h='<div class="card pad0 reveal" style="margin-top:var(--s3)"><h3 style="padding:var(--s3) var(--s3) var(--s2)">Accuracy by bet type <span class="r">settled · recent vs prior</span></h3>';
  h+='<div style="max-height:340px;overflow:auto"><table><thead><tr><th>Bet type</th><th>n</th><th>Hit</th><th>Brier</th><th>Mkt</th><th>Edge</th><th>Trend</th></tr></thead><tbody>';
  keys.forEach(k=>{const c=bt[k],s=c.summary||{},imp=c.improvement||{};
    h+='<tr><td>'+esc(prettyBet(k))+'</td><td>'+commaN(s.n)+'</td><td>'+pct(s.hit_rate)+'</td><td>'+num(s.brier)+'</td>'
      +'<td>'+num(s.market_brier)+'</td><td class="'+sgn(s.brier_edge)+'">'+signed(s.brier_edge,2)+'</td><td>'+improvArrow(imp)+'</td></tr>';});
  return h+'</tbody></table></div></div>';
}
function skeleton(){
  return '<div class="grid hero" style="margin-bottom:var(--s3)">'+Array(3).fill('<div class="card reveal" style="height:150px"><div class="empty">warming up…</div></div>').join('')
    +'</div><div class="card reveal" style="height:200px"><div class="empty">the snapshot refreshes every 20 seconds</div></div>';
}
function truthText(v,on='ON',off='OFF'){return v===true?on:(v===false?off:'UNKNOWN');}
function proofPill(label,v,good=true){const known=v===true||v===false,tone=!known?'warn':(v===good?'ok':'bad');return '<span class="truth-pill '+tone+'">'+esc(label)+' · '+esc(truthText(v,'pass','fail'))+'</span>';}
function statePill(label,v,ok){const text=String(v==null?'UNKNOWN':v),tone=text===ok?'ok':(text==='UNKNOWN'?'warn':'bad');return '<span class="truth-pill '+tone+'">'+esc(label)+' · '+esc(text)+'</span>';}
function shortAge(seconds){if(seconds==null||!Number.isFinite(Number(seconds)))return'UNKNOWN';const s=Math.max(0,Number(seconds));if(s<60)return Math.round(s)+'s';if(s<3600)return Math.round(s/60)+'m';if(s<86400)return(s/3600).toFixed(1)+'h';return(s/86400).toFixed(1)+'d';}
function gateBox(step,label,value,detail,result){const on=value===true,known=on||value===false,text=result?(on?'OPEN':'LOCKED'):truthText(value);return '<div class="gate-box" data-step="'+esc(step)+'"><div class="gl">'+esc(label)+'</div><div class="gv '+(on?'on':'off')+'">'+text+'</div><div class="gd">'+esc(detail||'UNKNOWN')+'</div></div>';}
function authorityLock(label,value,detail){const cls=value===false?'':(value===true?' danger':' unknown'),state=value===false?'FALSE · LOCKED':(value===true?'TRUE · DANGER':'UNKNOWN');return '<div class="authority-lock'+cls+'"><b>'+esc(label)+'<span>'+state+'</span></b><p>'+esc(detail)+'</p></div>';}
function modelArsenalSummaryCard(){
  const a=STATE.arsenal||{},sm=a.live_smoke||{},pc=a.panel_configuration||{},n=sm.models_proven;
  const headline=sm.all_models_live_proven===true?String(n==null?4:n)+' / 4 live identities proven':'Model connectivity proof unavailable';
  return '<a class="card arsenal-link reveal" href="#/arsenal" aria-label="Open Model Arsenal" style="margin-top:var(--s3)"><div><h3>'+svgIcon('arsenal')+'Model Arsenal <span class="r">stored OpenRouter witness</span></h3><div style="font:700 15px var(--disp);color:var(--txt)">'+esc(headline)+'</div><div class="sub" style="margin-top:4px;color:var(--muted)">Paid-call gate '+esc(pc.gate_status||'UNKNOWN')+' · evidence, probability, and order authority remain separate.</div></div><span class="go">inspect →</span></a>';
}
const CHART_ASSETS=['BTC','ETH','SOL'];
const CHART_TIMEFRAMES=['15m','1h','4h','1d','1w'];
const INDICATOR_LABELS={
  rsi_wilder_14:'RSI 14',ema_channel_trend:'EMA trend',atr_14:'ATR 14',
  atr_normalized_momentum_10:'ATR momentum',macd_atr:'MACD / ATR',
  bollinger_pct_b_20:'Bollinger %B',stochastic_k_14:'Stochastic K',
  obv_slope_20:'OBV slope',volume_z_20:'Volume z',breakout_state:'Breakout',
  fakeout_state:'Fakeout',close_location_value:'Close location'
};
function chartNumber(v){
  if(typeof v!=='number'||!Number.isFinite(v))return null;
  const a=Math.abs(v);
  return a>=1000?v.toLocaleString(undefined,{maximumFractionDigits:2}):(a>=10?v.toFixed(2):v.toFixed(3));
}
function chartIndicators(bundle){
  const rows=[],values=(bundle&&bundle.indicators)||{};
  Object.entries(INDICATOR_LABELS).forEach(([key,label])=>{
    const shown=chartNumber(values[key]);if(shown!=null)rows.push([label,shown]);
  });
  return rows;
}
function observerStatusBadge(d){
  const s=String((d&&d.artifact_status)||'UNAVAILABLE').toUpperCase();
  const cls=s==='COMPLETE'&&d.time_status==='FRESH'?'':'off';
  return '<span class="badge '+cls+'"><span class="d"></span>'+esc(s)+'</span>';
}
function cryptoResearchView(){
  const c=STATE.marketChart,d=c.data,available=!!(d&&d.available&&d.chart_bundle),bundle=available?d.chart_bundle:null;
  let h=topbar('Crypto Research Charts','stored immutable observations only',
    '<span class="badge off"><span class="d"></span>NO PRODUCTION AUTHORITY</span>');
  h+='<div class="chart-controls reveal"><span class="label">Asset</span>'
    +CHART_ASSETS.map(a=>'<button type="button" class="chart-choice '+(a===c.asset?'on':'')+'" data-chart-asset="'+a+'">'+a+'</button>').join('')
    +'<span class="label" style="margin-left:8px">Timeframe</span>'
    +CHART_TIMEFRAMES.map(t=>'<button type="button" class="chart-choice '+(t===c.timeframe?'on':'')+'" data-chart-timeframe="'+t+'">'+t+'</button>').join('')
    +'<button type="button" class="ghostbtn" data-action="chart-refresh" '+(c.pending?'disabled':'')+'>'+(c.pending?'Reading…':'Re-read artifact')+'</button></div>';
  if(!available){
    const status=d&&d.artifact_status?d.artifact_status:(c.pending?'READING':'UNAVAILABLE');
    const detail=c.error||(d&&d.detail)||'No persisted chart bundle exists for this asset and timeframe. Run the separate market-observer collector; the dashboard will never fetch market data itself.';
    h+='<section class="card reveal"><h3>'+esc(c.asset)+' · '+esc(c.timeframe)+' '+observerStatusBadge({artifact_status:status})+'</h3>'
      +'<div class="empty">'+esc(detail)+'</div></section>';
    return h+observerAuthorityBanner();
  }
  const indicators=chartIndicators(bundle),patterns=Array.isArray(bundle.patterns)?bundle.patterns:[];
  const latestRefresh=d.latest_refresh;
  const syntheticDemo=String((d.source&&d.source.provider)||'').startsWith('dummy-synthetic-release-demo');
  if(syntheticDemo)h+='<div class="observer-banner reveal" style="margin-bottom:var(--s3);border-color:var(--amber)"><div><b>Synthetic release demo — not market data or market evidence.</b> '
    +'These deterministic candles exercise the real artifact-only renderer. They carry no forecast, execution, allocation, promotion, or trading authority.</div></div>';
  h+='<section class="card reveal" style="margin-bottom:var(--s3)"><h3>'+esc(c.asset)+' / USD · '+esc(c.timeframe)
    +' <span class="r">'+observerStatusBadge(d)+(d.serving_last_complete?' last complete':' latest observation')+'</span></h3>';
  if(latestRefresh)h+='<div class="observer-banner" style="margin-bottom:10px"><div><b>Latest refresh '+esc(latestRefresh.status)+'.</b> '
    +'The chart remains on the last validated complete artifact. '+esc((latestRefresh.warnings||[]).join(' · '))+'</div></div>';
  h+='<div class="market-chart-frame"><div id="marketChart" role="img" aria-label="'+esc(c.asset+' '+c.timeframe+' candlestick chart')+'"></div>'
    +'<div class="market-chart-overlay">'+indicators.map(([label,value])=>'<span class="indicator-chip">'+esc(label)+' <b>'+esc(value)+'</b></span>').join('')+'</div></div>';
  h+='<div class="observer-attribution">Rendered locally with <a href="https://github.com/tradingview/lightweight-charts" target="_blank" rel="noopener noreferrer">TradingView Lightweight Charts™ 5.2.0</a> (Apache-2.0). The library supplies rendering only; no TradingView data, account, widget, API, browser automation, or scraping is used.</div></section>';
  const source=d.source||{},last=bundle.candles[bundle.candles.length-1]||{};
  h+='<div class="observer-meta reveal" style="margin-bottom:var(--s3)">'
    +observerMetaCell('Artifact status',String(d.artifact_status)+' / '+String(d.time_status||'UNKNOWN'))
    +observerMetaCell('Closed through',last.close_time_s?new Date(last.close_time_s*1000).toISOString():'UNKNOWN')
    +observerMetaCell('Source',String(source.provider||'UNKNOWN')+' · '+String(source.venue||'UNKNOWN'))
    +observerMetaCell('Adapter',source.adapter_version||'UNKNOWN')
    +observerMetaCell('Endpoint',source.endpoint||'UNKNOWN')
    +observerMetaCell('Observation',d.observation_id||'UNKNOWN')
    +observerMetaCell('Bars',String(bundle.candles.length))
    +observerMetaCell('Age',d.data_age_seconds==null?'UNKNOWN':Math.max(0,Number(d.data_age_seconds)).toFixed(0)+'s')
    +'</div>';
  h+='<div class="grid cols2"><section class="card reveal"><h3>Detected candlestick patterns <span class="r">markers on final closed bar</span></h3>'
    +(patterns.length?'<div class="observer-patterns">'+patterns.map(p=>'<span class="chip">'+esc(p.name||'pattern')+' · '+esc(p.direction||'neutral')+' · '+esc(chartNumber(Number(p.strength))||'—')+'</span>').join('')+'</div>':'<div class="empty">No named pattern detected on the latest closed bar.</div>')
    +'</section><section class="card reveal"><h3>Artifact warnings <span class="r">fail-closed labels</span></h3>'
    +((d.warnings||[]).length?'<div class="observer-patterns">'+d.warnings.map(w=>'<span class="chip">'+esc(w)+'</span>').join('')+'</div>':'<div class="empty">No persisted warnings.</div>')
    +'</section></div>';
  return h+observerAuthorityBanner();
}
function observerMetaCell(label,value){return '<div class="cell"><span>'+esc(label)+'</span><b>'+esc(value)+'</b></div>';}
function observerAuthorityBanner(){
  return '<div class="observer-banner reveal" style="margin-top:var(--s3)"><div><b>Observational research only.</b> '
    +'Execution, order, cancel, amend, allocation, and promotion authority are all false. The page can only GET validated immutable artifacts and cannot refresh a provider, change a forecast, or reach the broker.</div></div>';
}
async function ensureMarketChartData(force=false){
  if(!ROUTE.startsWith('#/charts'))return;
  const c=STATE.marketChart,key=c.asset+'|'+c.timeframe;
  if(c.pending||(!force&&c.loadedKey===key))return;
  c.pending=true;c.error=null;
  try{
    const r=await fetch('/api/market-observer/chart/'+encodeURIComponent(c.asset)+'/'+encodeURIComponent(c.timeframe),{method:'GET',cache:'no-store',credentials:'same-origin'});
    const data=await r.json();
    if(key!==STATE.marketChart.asset+'|'+STATE.marketChart.timeframe)return;
    c.data=data;c.loadedKey=key;c.error=r.ok?null:(data.detail||'Stored chart artifact is unavailable.');
  }catch(_){
    if(key!==STATE.marketChart.asset+'|'+STATE.marketChart.timeframe)return;
    c.data=null;c.loadedKey=key;c.error='Artifact-only chart request failed. No provider refresh was attempted.';
  }finally{
    if(key===STATE.marketChart.asset+'|'+STATE.marketChart.timeframe)c.pending=false;
    if(ROUTE.startsWith('#/charts'))render();
  }
}
function disposeMarketChart(){
  if(!ACTIVE_MARKET_CHART)return;
  try{if(ACTIVE_MARKET_CHART.resize)ACTIVE_MARKET_CHART.resize.disconnect();ACTIVE_MARKET_CHART.chart.remove();}catch(_){}
  ACTIVE_MARKET_CHART=null;
}
function mountMarketChart(){
  const host=document.getElementById('marketChart'),d=STATE.marketChart.data,bundle=d&&d.available&&d.chart_bundle;
  if(!host||!bundle||!Array.isArray(bundle.candles)||!bundle.candles.length)return;
  const L=window.LightweightCharts;
  if(!L||typeof L.createChart!=='function'){host.innerHTML='<div class="empty">Pinned local chart renderer is unavailable.</div>';return;}
  const chart=L.createChart(host,{autoSize:true,layout:{background:{type:'solid',color:'#050c13'},textColor:'#8291a3',fontFamily:'IBM Plex Mono, monospace'},
    grid:{vertLines:{color:'rgba(125,148,169,.08)'},horzLines:{color:'rgba(125,148,169,.08)'}},
    rightPriceScale:{borderColor:'rgba(125,148,169,.18)'},timeScale:{borderColor:'rgba(125,148,169,.18)',timeVisible:true,secondsVisible:false},
    crosshair:{mode:L.CrosshairMode?L.CrosshairMode.Normal:0},localization:{priceFormatter:p=>Number(p).toLocaleString(undefined,{minimumFractionDigits:2,maximumFractionDigits:2})}});
  const options={upColor:'#2fe38f',downColor:'#ff627d',borderUpColor:'#2fe38f',borderDownColor:'#ff627d',wickUpColor:'#7ff2bb',wickDownColor:'#ff91a3'};
  const series=typeof chart.addSeries==='function'&&L.CandlestickSeries?chart.addSeries(L.CandlestickSeries,options):chart.addCandlestickSeries(options);
  series.setData(bundle.candles.map(row=>({time:Number(row.open_time_s),open:Number(row.open),high:Number(row.high),low:Number(row.low),close:Number(row.close)})));
  const markers=(bundle.patterns||[]).map(p=>{const up=String(p.direction||'').toLowerCase()==='up';
    return {time:Number(p.bar_open_time_s||bundle.candles[bundle.candles.length-1].open_time_s),position:up?'belowBar':'aboveBar',color:up?'#2fe38f':'#ff627d',shape:up?'arrowUp':'arrowDown',text:String(p.name||'pattern').slice(0,28)};});
  if(markers.length){if(typeof L.createSeriesMarkers==='function')L.createSeriesMarkers(series,markers);else if(typeof series.setMarkers==='function')series.setMarkers(markers);}
  chart.timeScale().fitContent();
  let resize=null;
  if(typeof ResizeObserver!=='undefined'&&!chart.options().autoSize){resize=new ResizeObserver(()=>chart.resize(host.clientWidth,host.clientHeight));resize.observe(host);}
  ACTIVE_MARKET_CHART={chart:chart,resize:resize};
}

function modelArsenalView(){
  const a=STATE.arsenal;
  let h=topbar('Model Arsenal','exact four-model routing · stored proof · zero dashboard authority');
  if(!a||a.error)return h+'<div class="card reveal"><div class="empty">Model Arsenal status is unavailable.<br><span style="color:var(--faint)">No provider call was attempted; local status remains UNKNOWN.</span></div></div>';
  const pc=a.panel_configuration||{},access=a.openrouter_access||{},sm=a.live_smoke||{},auth=a.authorities||{},models=Array.isArray(a.models)?a.models:[];
  const live=sm.all_models_live_proven===true,proofTitle=live?String(sm.models_proven==null?4:sm.models_proven)+' / 4 exact identities live-proven':'Stored connectivity proof is not current';
  h+='<div class="arsenal-hero"><section class="card arsenal-lead reveal" aria-label="Model connectivity summary"><div class="arsenal-kicker">OpenRouter intelligence layer</div><div class="arsenal-title">Four minds. Separate jobs.<br>Zero automatic authority.</div><div class="arsenal-copy">This surface reads local configuration, redacted credential presence, and a previously stored smoke witness. Opening or refreshing it never sends a prompt, contacts OpenRouter, changes routing, or places an order.</div><div class="proof-banner"><div class="proof-orb">'+esc(String(sm.models_proven==null?'?':sm.models_proven))+'/4</div><div><b>'+esc(proofTitle)+'</b><span>'+esc(sm.verdict||'UNKNOWN')+' · witness '+shortAge(sm.age_seconds)+' old · response content not stored</span></div></div></section>';
  h+='<section class="card reveal" aria-label="Model access facts"><h3>Local access truth <span class="r">secret-free</span></h3><div class="arsenal-facts">'
    +'<div class="arsenal-fact"><div class="afl">Credential present</div><div class="afv '+(access.present===true?'ok':'lock')+'">'+truthText(access.present,'YES','NO')+'</div></div>'
    +'<div class="arsenal-fact"><div class="afl">Resolver source</div><div class="afv">'+esc(access.source||'UNKNOWN')+'</div></div>'
    +'<div class="arsenal-fact"><div class="afl">Exact configuration</div><div class="afv '+(pc.exact===true?'ok':'lock')+'">'+truthText(pc.exact,'MATCH','MISMATCH')+'</div></div>'
    +'<div class="arsenal-fact"><div class="afl">Stored response text</div><div class="afv '+(sm.response_content_stored===false?'ok':'lock')+'">'+(sm.response_content_stored===false?'NONE':truthText(sm.response_content_stored,'PRESENT','NONE'))+'</div></div>'
    +'</div><div class="sub" style="margin-top:10px;color:var(--faint);font:9.5px var(--mono);overflow-wrap:anywhere">'+esc((a.source&&a.source.smoke)||'UNKNOWN')+'</div></section></div>';
  h+='<div class="section-head"><h2>Paid-call controls</h2><p>Both keys must be open; credentials and exact routing are additional readiness checks</p></div><div class="gate-strip">'
    +gateBox('01','Persistent config gate',pc.configured_gate,'configs/model_routing.json')
    +gateBox('02','Runtime opt-in',pc.runtime_opt_in,(pc.runtime_opt_in_state||'UNKNOWN')+' · dashboard process')
    +gateBox('=','Two-key gate',pc.two_key_paid_call_gate_open,(pc.background_panel_ready===true?'panel ready':'panel not armed'),true)+'</div>';
  h+='<div class="section-head"><h2>Intelligent routing roster</h2><p>Every stored call must match its configured model, task, identity, and response schema</p></div><div class="arsenal-grid">';
  if(!models.length)h+='<div class="card"><div class="empty">No exact model roster is available.</div></div>';
  models.forEach((m,i)=>{const s=m.smoke||{};h+='<article class="model-unit reveal" data-index="'+(i+1)+'"><div class="unit-head"><div><div class="unit-name">'+esc(m.display_name||m.provider_alias||'UNKNOWN')+'</div><div class="unit-slug">'+esc(m.model||'UNKNOWN')+'</div></div>'+proofPill('route',m.configuration_match,true)+'</div><div class="unit-role">'+esc(m.role||'Role unavailable')+'</div><div class="unit-meta"><span>task <b>'+esc(m.task||'UNKNOWN')+'</b></span><span>reasoning <b>'+esc(m.reasoning_effort||'UNKNOWN')+'</b></span><span>latency <b>'+(s.latency_ms==null?'UNKNOWN':esc(Math.round(Number(s.latency_ms)))+' ms')+'</b></span>'+statePill('smoke',s.status,'LIVE_PROVEN')+proofPill('identity',s.identity_ok,true)+proofPill('schema',s.schema_ok,true)+'</div></article>';});
  h+='</div><section class="card reveal" aria-label="Model authority locks"><h3>Separation of powers <span class="r">connectivity is not predictive skill</span></h3><div class="sub" style="margin:-2px 0 12px;color:var(--muted)">A valid key and 4/4 smoke prove bounded reachability only. They cannot promote evidence, change operational probabilities, or authorize a broker order.</div><div class="authority-row">'
    +authorityLock('Evidence authority',auth.evidence,'Stored model output remains research evidence only.')
    +authorityLock('Probability authority',auth.probability,'Operational model weight remains zero without exact-scope proof.')
    +authorityLock('Order authority',auth.order,'The central live firewall and operator gates remain separate.')+'</div>';
  const blockers=Array.isArray(sm.blockers)?sm.blockers:[];if(blockers.length)h+='<div class="sub" style="margin-top:12px;color:var(--amber)"><b>Stored-proof blockers:</b> '+esc(blockers.join(' · '))+'</div>';
  h+='</section>';
  return h;
}

const GLOSSARY=[
  ['Forecast','Probability','Dummy’s estimated chance that a contract settles YES. It is a calibrated estimate, not certainty or a guaranteed result.'],
  ['Forecast','Market probability','The probability implied by the executable market price or midpoint. A 63¢ YES price is roughly a 63% market view before fees.'],
  ['Forecast','Model-to-market gap','The absolute difference between Dummy’s probability and the market probability. A large gap is a research lead, not automatically a trade.'],
  ['Forecast','Edge','Expected advantage after choosing YES or NO. Dummy evaluates both sides and then applies uncertainty, fees, entry-price, and liquidity rules.'],
  ['Forecast','Uncertainty','How unsure the model is. Higher uncertainty increases the safety haircut and can turn an apparent edge into an abstention.'],
  ['Forecast','Calibration','Whether events predicted at a given probability happen at about that rate over time—for example, whether 70% calls win near 70% of the time.'],
  ['Evidence','Brier score','Mean squared probability error. Lower is better: confident wrong calls are penalized more heavily than cautious ones.'],
  ['Evidence','Market Brier','The same Brier calculation applied to the contemporaneous market probability. Dummy must beat this benchmark, not merely beat a coin flip.'],
  ['Evidence','Hit rate','The percentage of directional calls that settled correctly. It ignores confidence and price, so it is never sufficient by itself.'],
  ['Evidence','Contested market','A settlement where Dummy and the market had meaningfully different views. These cases are especially useful for measuring genuine model value.'],
  ['Evidence','CLV','Closing-line value: whether a quoted entry later looked better than the price near game start or market close. Positive CLV is useful but is not settled profit.'],
  ['Evidence','Point-in-time','Data that was actually available at the decision moment. Backtests exclude future results, later revisions, and other look-ahead leakage.'],
  ['Execution','YES / NO','The two sides of a binary contract. YES pays $1 if the event happens; NO pays $1 if it does not, subject to the venue’s settlement rules.'],
  ['Execution','Expected value (EV)','Estimated payout value minus entry price and fees, after Dummy’s uncertainty haircut. Positive raw edge can still have negative EV.'],
  ['Execution','Spread','The gap between the best bid and ask. Wide spreads increase execution cost and reduce the chance that an apparent opportunity is real.'],
  ['Execution','Liquidity','Available market depth and trading activity. Thin books are harder to enter or exit without paying a worse price.'],
  ['Execution','Maker / taker','A maker rests a limit order; a taker trades against an available quote. They have different fill evidence, queue risk, and fees.'],
  ['Execution','Shadow fill','A simulated fill backed by observable public prints or quote movement. It is stronger than a model assumption but is not a live broker fill.'],
  ['Execution','Exposure','Capital currently at risk across open positions. Correlated contracts are grouped so one underlying event cannot silently dominate the bankroll.'],
  ['Risk','Drawdown','The decline from a previous bankroll peak. Drawdown gates automatically shrink or stop risk before losses compound unchecked.'],
  ['Risk','Profit factor','Gross winning P&L divided by gross losing P&L. Above 1 is profitable before considering the confidence interval and sample quality.'],
  ['Risk','Confidence tier','Versioned executable-value labels. A requires at least 4% edge after the quoted ask and modeled taker fee, with uncertainty at or below 12%; B requires 2% and 18%; C requires 1% and 25%. A letter also requires an independent governed predictive source, a valid two-sided selected-side quote, and positive executable depth witnessed by selected-side Kalshi quote sizes or positive legacy liquidity. A is capped at one A-tier market per correlated event and five per scope per cycle. WATCH clears no letter-tier hurdle; UNATTRIBUTED means required evidence is missing or invalid. These versioned display and research labels never grant execution authority.'],
  ['Evidence','Unattributed tier','A row without current verifiable attribution—for example, market-price-only evidence, a missing exact model timestamp, no executable depth, a failed series refresh, or an older tier-policy snapshot. UNATTRIBUTED is not WATCH, is never retroactively relabelled, and is excluded from tier-performance claims.'],
  ['Evidence','Tier forecast diagnostics','Forward-only forecast results for the policy version issued with each forecast or decision: settled value-side hit rate, event clusters, and Brier. Paper/shadow realized economics are retired from the primary operator view and have no live authority.'],
  ['Risk','Event cluster','Contracts sharing the same underlying outcome or expiry. Clustering prevents double-counting evidence and over-allocating correlated risk.'],
  ['Operation','15m / 1h / 1d / 1w','Crypto horizons: 15-minute, hourly, daily, and weekly. BTC, ETH, and SOL are monitored separately at every listed horizon.'],
  ['Operation','Retired paper history','Historical local simulation retained unchanged for audit. Paper bankroll, P&L, and promotion results can neither enable nor block live trading and are removed from the primary operator view.'],
  ['Operation','Shadow mode','The production decision path runs against public market data, but live submission remains locked. This is Dummy’s current operating mode.'],
  ['Operation','Live authorization','A separate, time-bounded, one-controlled-proof operator grant required before any broker submission. It also requires protected caps, a command seal, central firewall, local credential resolution, an unused proof lock, an active LIVE session, and limit orders only. Model confidence and paper history cannot create or extend this authority.'],
  ['Operation','Champion / challenger','The incumbent model is the champion. New methods remain challengers until later, out-of-sample settlements show a reliable improvement.'],
  ['Operation','Live risk stage','A live-only persisted risk state used by the central firewall to cap an already-authorized order. It is separate from the retired shadow bankroll and never creates live authority by itself.'],
  ['Operation','Live account snapshot','A cached authenticated GET-only view of Kalshi balance, open positions, and open orders. Dashboard page requests read the local artifact and never contact the broker. The snapshot is account visibility, not order authority.'],
  ['Operation','Daily betting guide','The sports page’s current-day event list, separated by market category and ranked by quoted, taker-fee-adjusted executable value. Matchups expand into every priced contract. It is a forecast guide, not an order screen.'],
  ['Data','Data-only source','Weather and commodity feeds may inform sports or crypto context, but their contracts cannot become predictions, picks, or orders.'],
  ['Data','Abstain','A deliberate no-trade result caused by missing listings, incomplete quotes, weak EV, excessive uncertainty, stale data, or a safety gate.']
];
function glossaryView(){
  const steps=[
    ['Discover','Read the supported crypto and sports listings from public market data.'],
    ['Collect','Attach point-in-time price, book, sports, and contextual data with provenance.'],
    ['Forecast','Independent specialists estimate probability and uncertainty for eligible targets.'],
    ['Challenge','The ensemble compares models with the market, fees, liquidity, and correlation.'],
    ['Gate','Live submission requires explicit one-proof operator, caps, seal, session, risk, and central-firewall authority. Paper results are ignored.'],
    ['Learn','Fills and settlements update calibration, backtests, diagnostics, and challenger evidence.']
  ];
  let h=topbar('Glossary & how Dummy works','plain-language operating guide');
  h+='<div class="card reveal" style="margin-bottom:var(--s3)"><h3>How Dummy works <span class="r">evidence first · fail closed</span></h3>'
    +'<div class="sub" style="color:var(--muted)">Dummy is a probability and execution-research engine. It looks for mispricing, but it can also decide that doing nothing is the best action. Weather and commodities supply context only; prediction targets are crypto and sports.</div>'
    +'<div class="how-flow">'+steps.map(s=>'<div class="how-step"><b>'+esc(s[0])+'</b><span>'+esc(s[1])+'</span></div>').join('')+'</div></div>';
  h+='<div class="glossary-tools"><label for="glossarySearch">Find a term</label><input class="glossary-search" id="glossarySearch" type="search" placeholder="Search probability, Brier, shadow, EV…" autocomplete="off"><span class="sub" id="glossaryCount" aria-live="polite">'+GLOSSARY.length+' terms</span></div>';
  h+='<div class="glossary-grid" id="glossaryGrid">'+GLOSSARY.map(g=>'<article class="gloss reveal" data-search="'+esc(g.join(' ').toLowerCase())+'"><div class="gt"><h4>'+esc(g[1])+'</h4><span class="cat">'+esc(g[0])+'</span></div><p>'+esc(g[2])+'</p></article>').join('')+'</div><div class="glossary-empty" id="glossaryEmpty">No glossary term matches that search.</div>';
  return h;
}
function wireGlossary(){
  const q=document.getElementById('glossarySearch'),cards=[...document.querySelectorAll('.gloss')],count=document.getElementById('glossaryCount'),empty=document.getElementById('glossaryEmpty');
  if(!q)return;q.addEventListener('input',()=>{const needle=q.value.trim().toLowerCase();let shown=0;cards.forEach(card=>{const hit=!needle||(card.dataset.search||'').includes(needle);card.hidden=!hit;if(hit)shown++;});count.textContent=shown+' of '+cards.length+' terms';empty.classList.toggle('show',shown===0);});
}
function cryptoHorizonCard(asset){
  const twin=(STATE.status&&STATE.status.crypto_paper_twin)||{},coverage=twin.forced_crypto_coverage||{},matrix=coverage.matrix||[];
  const horizons=[['1h','Hourly'],['1d','Daily'],['1w','Weekly'],['15m','15-minute']];
  const rows=horizons.map(([key,label])=>{const row=matrix.find(r=>String(r.asset).toUpperCase()===String(asset).toUpperCase()&&r.timeframe===key)||{};
    const observed=Number(row.targets_observed_this_cycle||0),tracked=Number(row.tracked_decisions||0),open=Number(row.open_decisions||0);
    const active=observed>0||open>0,status=observed>0?'research tracking':(open>0?'research position open':(tracked>0?'awaiting next listing':'no listing yet'));
    return '<div class="horizon"><div class="hh"><span>'+label+'</span><span class="state '+(active?'':'wait')+'">'+status+'</span></div>'
      +'<div class="hs">Every real, compatible '+label.toLowerCase()+' listing is evaluated. Normal positions still require positive fee- and uncertainty-adjusted EV.</div>'
      +'<div class="hm"><span>'+observed+' targets now</span><span>'+open+' open · '+tracked+' tracked</span></div></div>';}).join('');
  return '<div class="card reveal" style="margin-bottom:var(--s3)"><h3>'+esc(asset)+' crypto horizon research <span class="r">read-only observer · '+ago(twin.completed_at)+'</span></h3>'
    +'<div class="sub" style="margin:-3px 0 12px;color:var(--muted)">Hourly, daily, and weekly forecast coverage is monitored for BTC, ETH, and SOL whenever a compatible market is listed. This retired paper observer supplies research coverage only; its results have no live authority and it never contacts the broker.</div>'
    +'<div class="horizon-grid">'+rows+'</div></div>';
}
function scopeView(vert,label){return '<div class="dock">'+scopeViewInner(vert,label)+'</div>';}
function scopeViewInner(vert,label){
  const block=STATE.scopes&&STATE.scopes.verticals&&STATE.scopes.verticals[vert];
  const sc=block&&block.scopes&&block.scopes[label];
  if(!sc){
    let empty=topbar(label,vert.toLowerCase());
    if(vert==='SPORTS')empty+=dailyGuideCard(label)+tierPerformanceCard(label);
    if(vert==='CRYPTO')empty+=cryptoHorizonCard(label)+tierPerformanceCard(label);
    return empty+'<div class="card"><div class="empty">'+esc(label)+' — no graded history yet.<br><span style="color:var(--faint)">the live slate above refreshes independently from settled model diagnostics</span></div></div>';
  }
  const s=sc.summary;
  // Season is a SPORTS-only concept -- crypto trades 24/7 and has no season, so
  // none of the season badge / status / basis applies to a coin scope.
  const isSports=vert==='SPORTS';
  const inSeason=sc.in_season!==false, basis=sc.basis||'';
  // Three-state season, so an off-season league awake for preseason never reads
  // "in season · awaiting grades". Backend sets season_status; fall back for old snapshots.
  const status=sc.season_status||(!inSeason?'off':(basis==='current'?'in':'upcoming'));
  const seasonBadge=!isSports?''
    :(status==='off'
      ? '<span class="badge off"><span class="d"></span>out of season'+(basis==='last-season'?' · last season':'')+'</span>'
      : (status==='upcoming'?'<span class="badge"><span class="d"></span>preseason · not yet playing</span>':''));
  const seasonWord=status==='in'?'in season':(status==='upcoming'?'preseason':'off season');
  let h=topbar(label,vert.toLowerCase()+' · graded forecast quality',seasonBadge);
  if(isSports)h+=dailyGuideCard(label)+tierPerformanceCard(label);
  if(!isSports)h+=cryptoHorizonCard(label)+tierPerformanceCard(label);
  // scope hero: edge gauge + key figures
  h+='<div class="grid hero">';
  h+='<div class="card gaugecard reveal">'+gauge(s.brier_edge,{span:0.15,label:'Edge vs market',fmt:(x)=>signed(x,2)})+'</div>';
  h+='<div class="card reveal"><div class="mini">'
    +miniRow('Graded picks',commaN(s.n||0),'')
    +miniRow('Hit rate',pct(s.hit_rate),s.hit_rate>=.5?'pos':'neg')
    +miniRow('Brier',num(s.brier),'')
    +miniRow('Contested',commaN(s.contested_n||0),'cy')
    +'</div></div>';
  h+='<div class="card reveal"><div class="mini">'
    +miniRow('Open forecasts',commaN(sc.picks?sc.picks.length:0),'amb')
    +(isSports
      ? miniRow('Season',seasonWord,status==='in'?'pos':(status==='upcoming'?'amb':'neg'))
        +miniRow('Data basis',basis==='current'?'current window':(basis==='last-season'?'last season':(status==='upcoming'?'preseason — no games yet':'no history')),basis==='last-season'?'amb':'')
      : miniRow('Traded',commaN(s.traded||0),'')
        +miniRow('Coverage','24/7 live','pos'))
    +miniRow('Market Brier',num(s.market_brier),'')
    +'</div></div>';
  h+='</div>';
  const prog=sc.progression||[];
  const hitPts=prog.filter(p=>p.hit_rate!=null).map(p=>({v:p.hit_rate}));
  const brPts=prog.filter(p=>p.brier!=null).map(p=>({v:p.brier}));
  h+='<div class="card reveal" style="margin-bottom:var(--s3)"><h3>Progression <span class="r">'+prog.length+' windows · oldest→newest</span></h3>'
    +lineChart([{name:'hit',color:'var(--green)',pts:hitPts},{name:'brier',color:'var(--amber)',pts:brPts,dash:true}],{h:150})
    +'<div class="legend"><span><i style="background:var(--green)"></i>hit rate</span><span><i style="background:var(--amber)"></i>Brier</span></div></div>';
  h+='<div class="grid cols2">';
  h+='<div class="card reveal"><h3>Model vs market <span class="r">Brier, lower better</span></h3>'+accuracyBars(s)+'</div>';
  h+='<div class="card pad0 reveal"><h3 style="padding:var(--s3) var(--s3) var(--s2)">Model shortlist <span class="r">forecast gaps · not orders</span></h3>'+picksTable(sc.picks)+'</div>';
  h+='</div>';
  h+=betTypeCard(sc.bet_types);
  h+=settledTodayCard(sc);
  h+=walkCard(vert,label);
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
  if(!picks||!picks.length)return '<div class="empty">no open forecasts in this scope right now</div>';
  let h='<div style="max-height:326px;overflow:auto"><table><thead><tr><th>Market</th><th>Side</th><th>Model P</th><th>Market P</th><th>Gap (¢)</th></tr></thead><tbody>';
  picks.forEach(p=>{h+='<tr><td title="'+esc(p.ticker)+'">'+esc(p.label||p.ticker)+dateTag(p.game_date)+'</td>'
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
  h+='<div class="card pad0 reveal"><h3 style="padding:var(--s3) var(--s3) var(--s2)">Mispricing monitor <span class="r">model vs book vs market · non-authoritative research</span></h3>'+mispTable(x.mispricing)+'</div>';
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
    h+='<tr><td title="'+esc(r.ticker)+' — '+esc(r.rationale||'')+'">'+esc(r.label||r.ticker||'')+'</td>'
      +'<td><span class="pill '+((r.side||'').toUpperCase().includes('NO')?'no':'yes')+'">'+esc(r.side||'')+'</span></td>'
      +'<td class="'+(e>=0?'pos':'neg')+'">'+(e==null?'—':(e>0?'+':'')+e.toFixed(1)+'%')+'</td>'
      +'<td>'+(r.model_prob==null?'—':num(r.model_prob,2))+'</td><td>'+(r.book_prob==null?'—':num(r.book_prob,2))+'</td>'
      +'<td>'+(r.market_prob==null?'—':num(r.market_prob,2))+'</td><td style="color:var(--muted)">'+esc(r.confidence||'—')+'</td></tr>';});
  return h+'</tbody></table></div>';
}
function topbar(title,crumb,badge){
  const stamp=STATE.overview&&STATE.overview.generated_at;
  return '<div class="topbar"><h2>'+esc(title)+'</h2><span class="crumb">'+esc(crumb)+'</span>'
    +(badge?' '+badge:'')+'<span class="spacer"></span>'
    +'<span class="stamp"><span class="beat"></span>updated '+ago(stamp)+'</span>'
    +'<span class="top-actions"><button class="ghostbtn" type="button" data-action="refresh" aria-label="Refresh dashboard data">Refresh</button>'
    +'<button class="ghostbtn" type="button" data-action="search" aria-label="Open market search">Jump <span class="key">Ctrl K</span></button></span></div>';
}

// ---------- 3D tilt + cursor glare on cards ----------
if(!REDUCE){
  let cur=null;
  document.addEventListener('pointermove',e=>{
    const card=e.target.closest&&e.target.closest('.card');
    if(card!==cur){if(cur)resetTilt(cur);cur=card;}
    if(!card)return;
    const r=card.getBoundingClientRect();
    const px=(e.clientX-r.left)/r.width,py=(e.clientY-r.top)/r.height;
    card.style.setProperty('--rx',((.5-py)*4.5).toFixed(2)+'deg');
    card.style.setProperty('--ry',((px-.5)*5.5).toFixed(2)+'deg');
    card.style.setProperty('--mx',(px*100).toFixed(1)+'%');
    card.style.setProperty('--my',(py*100).toFixed(1)+'%');
    card.classList.add('tilt');
  },{passive:true});
  document.addEventListener('pointerleave',()=>{if(cur){resetTilt(cur);cur=null;}});
  function resetTilt(el){el.classList.remove('tilt');el.style.removeProperty('--rx');el.style.removeProperty('--ry');}
}

// ---------- complete application theme switcher ----------
const THEMES=[['emerald','#2fe38f'],['amber','#ffc24d'],['cyan','#6fe0ff'],['violet','#b79cff']];
function setTheme(a){document.documentElement.setAttribute('data-theme',a);document.documentElement.setAttribute('data-accent',a);try{localStorage.setItem('dummy-theme',a);}catch(_){}
  [...document.querySelectorAll('.tube')].forEach(t=>t.setAttribute('aria-pressed',String(t.dataset.a===a)));
  try{if(GT.gl&&GT.model)glBuild(sceneModel());else if(GT.model)GT.model=sceneModel();}catch(_){/* GL initializes after the saved theme is applied. */}}
(function(){const box=document.getElementById('tubes');
  THEMES.forEach(([a,c])=>{const label=a[0].toUpperCase()+a.slice(1)+' full theme';const b=$('<button class="tube" data-a="'+a+'" title="'+label+'" aria-label="'+label+'" style="--c:'+c+'"></button>');
    b.addEventListener('click',()=>setTheme(a));box.appendChild(b);});
  let saved='emerald';try{saved=localStorage.getItem('dummy-theme')||localStorage.getItem('dummy-accent')||'emerald';}catch(_){}
  setTheme(THEMES.some(x=>x[0]===saved)?saved:'emerald');})();
function cycleTheme(){const cur=document.documentElement.getAttribute('data-theme');
  const i=THEMES.findIndex(x=>x[0]===cur);setTheme(THEMES[(i+1)%THEMES.length][0]);}

// ---------- command palette ----------
const cmdk=document.getElementById('cmdk'),cmdq=document.getElementById('cmdq'),cmdlist=document.getElementById('cmdlist');
let cmdRoutes=[],cmdSel=0,lastFocus=null;
function cmdBuild(){
  cmdRoutes=[{icon:'overview',label:'Overview',hint:'performance & readiness',href:'#/overview'},
    {icon:'chart',label:'Crypto Research Charts',hint:'stored BTC ETH SOL candles',href:'#/charts'},
    {icon:'arsenal',label:'Model Arsenal',hint:'four-model routing & stored proof',href:'#/arsenal'},
    {icon:'glossary',label:'Glossary & how Dummy works',hint:'terms and operating model',href:'#/glossary'}];
  const v=(STATE.scopes&&STATE.scopes.verticals)||{};
  ['CRYPTO','SPORTS'].forEach(vert=>{
    if(vert==='CRYPTO'&&!v[vert])return;
    const vb=v[vert]||{scopes:{}};
    scopeLabels(vert,vb).forEach(lab=>cmdRoutes.push({icon:verticalIcon(vert),label:lab===vert?'All '+((VERTICAL_META[vert]||['',titleCase(vert)])[1]):lab,hint:vert.toLowerCase(),href:'#/scope/'+vert+'/'+lab}));
  });
  THEMES.forEach(([a])=>cmdRoutes.push({icon:'overview',label:'Theme: '+a,hint:'apply full theme',action:()=>setTheme(a)}));
}
function fuzzy(q,s){q=q.toLowerCase();s=s.toLowerCase();let i=0;for(const ch of s){if(ch===q[i])i++;if(i===q.length)return true;}return q.length===0;}
function cmdRender(){
  const q=cmdq.value.trim();
  const rows=cmdRoutes.filter(r=>fuzzy(q,r.label+' '+r.hint));
  cmdSel=Math.max(0,Math.min(cmdSel,rows.length-1));
  cmdlist.innerHTML=rows.map((r,i)=>'<div class="opt'+(i===cmdSel?' sel':'')+'" role="option" aria-selected="'+(i===cmdSel?'true':'false')+'" data-i="'+i+'">'+svgIcon(r.icon)
    +'<span>'+esc(r.label)+'</span><span class="oh">'+esc(r.hint)+'</span></div>').join('')||'<div class="empty">no match</div>';
  cmdlist._rows=rows;
  const sel=cmdlist.querySelector('.opt.sel');if(sel)sel.scrollIntoView({block:'nearest'});
}
function cmdOpen(){cmdBuild();cmdSel=0;cmdq.value='';cmdRender();lastFocus=document.activeElement;
  cmdk.classList.add('open');cmdk.setAttribute('aria-hidden','false');requestAnimationFrame(()=>cmdq.focus());}
function cmdClose(){cmdk.classList.remove('open');cmdk.setAttribute('aria-hidden','true');if(lastFocus&&lastFocus.focus)lastFocus.focus();}
function cmdGo(){const rows=cmdlist._rows||[];const r=rows[cmdSel];if(!r)return;
  if(r.action){r.action();cmdClose();return;}location.hash=r.href;cmdClose();}
cmdq.addEventListener('input',()=>{cmdSel=0;cmdRender();});
cmdlist.addEventListener('click',e=>{const o=e.target.closest('.opt');if(!o)return;
  const r=(cmdlist._rows||[])[+o.dataset.i];if(!r)return;
  if(r.action){r.action();cmdClose();return;}location.hash=r.href;cmdClose();});
document.addEventListener('keydown',e=>{
  const open=cmdk.classList.contains('open');
  if((e.key==='k'||e.key==='K')&&(e.metaKey||e.ctrlKey)){e.preventDefault();open?cmdClose():cmdOpen();return;}
  if(!open){
    const tag=(document.activeElement&&document.activeElement.tagName)||'';
    if(e.key==='/'&&tag!=='INPUT'){e.preventDefault();cmdOpen();}
    else if((e.key==='t'||e.key==='T')&&tag!=='INPUT'&&!e.metaKey&&!e.ctrlKey){cycleTheme();}
    return;
  }
  if(e.key==='Escape'){e.preventDefault();cmdClose();}
  else if(e.key==='ArrowDown'){e.preventDefault();cmdSel++;cmdRender();}
  else if(e.key==='ArrowUp'){e.preventDefault();cmdSel--;cmdRender();}
  else if(e.key==='Enter'){e.preventDefault();cmdGo();}
});
cmdk.addEventListener('click',e=>{if(e.target===cmdk)cmdClose();});

// ---------- GL ----------
// Raw-WebGL neural organism. The DOM remains the complete source of truth.
const GL_TIER={STATIC:0,CANVAS2D:1,WEBGL:2,WEBGL_BLOOM:3};
const GL_TIER_NAME=['static','canvas2d','webgl','webgl-bloom'];
let GT={tier:GL_TIER.STATIC,gl:null,ver:0,w:0,h:0,dpr:1,run:false,raf:0,
  progP:null,progL:null,locP:null,locL:null,bufPts:null,bufLines:null,bufDust:null,bufPulse:null,
  nPts:0,nLines:0,nDust:0,pulses:[],dust:null,mood:0,moodTarget:0,model:null};
const CAM={pos:[0,1.6,10.5],tgt:[0,0,0],anim:null};
const CAM_PRESETS={overview:{pos:[0,1.6,10.5],tgt:[0,0,0]}};
const PAR={x:.5,y:.5};

const VS_P=`
attribute vec3 aPos;attribute float aSize;attribute vec3 aCol;attribute float aBright;
uniform mat4 uProj;uniform mat4 uView;uniform float uDpr;uniform float uTime;uniform float uHalo;
varying vec3 vCol;varying float vB;
void main(){vCol=aCol;vB=aBright;
  vec4 mv=uView*vec4(aPos,1.0);
  float tw=1.0+0.06*sin(uTime*0.0012+aPos.x*3.1+aPos.y*2.3);
  gl_PointSize=aSize*tw*uDpr*(180.0/max(1.0,-mv.z))*(uHalo>0.5?2.2:1.0);
  gl_Position=uProj*mv;}`;
const FS_P=`
precision mediump float;varying vec3 vCol;varying float vB;
uniform float uMood;uniform float uHalo;
void main(){vec2 d=gl_PointCoord-vec2(0.5);float r=length(d);if(r>0.5)discard;
  float a=smoothstep(0.5,0.0,r);a*=a;
  vec3 col=mix(vCol,vec3(1.0,0.42,0.48),uMood);
  float b=vB*(uHalo>0.5?0.16:1.0);
  gl_FragColor=vec4(col*b,a*min(1.0,vB)*(uHalo>0.5?0.34:1.0));}`;
const VS_L=`
attribute vec3 aPos;attribute vec3 aCol;attribute float aA;
uniform mat4 uProj;uniform mat4 uView;
varying vec3 vC;varying float vA;
void main(){vC=aCol;vA=aA;gl_Position=uProj*uView*vec4(aPos,1.0);}`;
const FS_L=`
precision mediump float;varying vec3 vC;varying float vA;uniform float uMood;
void main(){gl_FragColor=vec4(mix(vC,vec3(1.0,0.42,0.48),uMood),vA);}`;

// WebGL2 requires GLSL ES 3.00. WebGL1 keeps the compact ES 1.00 source.
function glslFor(src,ver,fragment){
  if(ver!==2)return src;
  let out=fragment
    ?src.replace(/\bvarying\b/g,'in').replace(/\bgl_FragColor\b/g,'fragColor')
    :src.replace(/\battribute\b/g,'in').replace(/\bvarying\b/g,'out');
  if(fragment)out=out.replace('precision mediump float;','precision mediump float;out vec4 fragColor;');
  return '#version 300 es\n'+out;
}
function m4Persp(fov,asp,n,f){const t=1/Math.tan(fov/2),d=1/(n-f);
  return new Float32Array([t/asp,0,0,0,0,t,0,0,0,0,(f+n)*d,-1,0,0,2*f*n*d,0]);}
function m4LookAt(e,c,up){let zx=e[0]-c[0],zy=e[1]-c[1],zz=e[2]-c[2];
  let zl=Math.hypot(zx,zy,zz)||1;zx/=zl;zy/=zl;zz/=zl;
  let xx=up[1]*zz-up[2]*zy,xy=up[2]*zx-up[0]*zz,xz=up[0]*zy-up[1]*zx;
  let xl=Math.hypot(xx,xy,xz)||1;xx/=xl;xy/=xl;xz/=xl;
  const yx=zy*xz-zz*xy,yy=zz*xx-zx*xz,yz=zx*xy-zy*xx;
  return new Float32Array([xx,yx,zx,0,xy,yy,zy,0,xz,yz,zz,0,
    -(xx*e[0]+xy*e[1]+xz*e[2]),-(yx*e[0]+yy*e[1]+yz*e[2]),-(zx*e[0]+zy*e[1]+zz*e[2]),1]);}
function bootGL(canvas){
  let gl=null;
  try{gl=canvas.getContext('webgl2',{alpha:true,antialias:true,powerPreference:'high-performance'});}catch(_){gl=null;}
  if(gl)return{gl,ver:2};
  try{gl=canvas.getContext('webgl',{alpha:true,antialias:true});}catch(_){gl=null;}
  return gl?{gl,ver:1}:null;
}
function probeTier(done){let frames=0;const started=performance.now();
  (function sample(){frames++;if(frames<90){requestAnimationFrame(sample);return;}
    done(frames/((performance.now()-started)/1000));})();}
function mkProg(gl,vs,fs,ver){
  const compile=(type,source,fragment)=>{const shader=gl.createShader(type);
    gl.shaderSource(shader,glslFor(source,ver,fragment));gl.compileShader(shader);
    if(!gl.getShaderParameter(shader,gl.COMPILE_STATUS))throw new Error(gl.getShaderInfoLog(shader)||'shader compile failed');
    return shader;};
  const program=gl.createProgram();
  gl.attachShader(program,compile(gl.VERTEX_SHADER,vs,false));
  gl.attachShader(program,compile(gl.FRAGMENT_SHADER,fs,true));
  gl.linkProgram(program);
  if(!gl.getProgramParameter(program,gl.LINK_STATUS))throw new Error(gl.getProgramInfoLog(program)||'shader link failed');
  return program;
}
function locs(gl,program,names){const out={};names.forEach(name=>{
  out[name]=name.charAt(0)==='u'?gl.getUniformLocation(program,name):gl.getAttribLocation(program,name);});
  return out;}
function glSetup(boot){
  const gl=boot.gl;GT.gl=gl;GT.ver=boot.ver;
  GT.progP=mkProg(gl,VS_P,FS_P,boot.ver);GT.progL=mkProg(gl,VS_L,FS_L,boot.ver);
  GT.locP=locs(gl,GT.progP,['aPos','aSize','aCol','aBright','uProj','uView','uDpr','uTime','uMood','uHalo']);
  GT.locL=locs(gl,GT.progL,['aPos','aCol','aA','uProj','uView','uMood']);
  GT.bufPts=gl.createBuffer();GT.bufLines=gl.createBuffer();GT.bufDust=gl.createBuffer();GT.bufPulse=gl.createBuffer();
  glResize();
}
function glResize(){
  const canvas=document.getElementById('gl');if(!canvas)return;
  GT.dpr=Math.min(GT.tier===GL_TIER.WEBGL_BLOOM?2:1.6,window.devicePixelRatio||1);
  GT.w=canvas.width=Math.floor(innerWidth*GT.dpr);GT.h=canvas.height=Math.floor(innerHeight*GT.dpr);
}
function glAttrs(loc,stride,kind){
  const gl=GT.gl,F=Float32Array.BYTES_PER_ELEMENT;
  const on=(name,size,offset)=>{const slot=loc[name];if(slot==null||slot<0)return;
    gl.enableVertexAttribArray(slot);gl.vertexAttribPointer(slot,size,gl.FLOAT,false,stride*F,offset*F);};
  on('aPos',3,0);
  if(kind==='P'){on('aSize',1,3);on('aCol',3,4);on('aBright',1,7);}
  else{on('aCol',3,3);on('aA',1,6);}
}
function glDrawPoints(proj,view,t,halo){
  const gl=GT.gl,u=GT.locP;gl.useProgram(GT.progP);
  gl.uniformMatrix4fv(u.uProj,false,proj);gl.uniformMatrix4fv(u.uView,false,view);
  gl.uniform1f(u.uDpr,GT.dpr);gl.uniform1f(u.uTime,t||0);gl.uniform1f(u.uMood,GT.mood);gl.uniform1f(u.uHalo,halo?1:0);
  gl.bindBuffer(gl.ARRAY_BUFFER,GT.bufPts);glAttrs(u,8,'P');gl.drawArrays(gl.POINTS,0,GT.nPts);
  if(GT.nDust){gl.bindBuffer(gl.ARRAY_BUFFER,GT.bufDust);glAttrs(u,8,'P');gl.drawArrays(gl.POINTS,0,GT.nDust);}
  if(GT.pulses.length){gl.bindBuffer(gl.ARRAY_BUFFER,GT.bufPulse);glAttrs(u,8,'P');gl.drawArrays(gl.POINTS,0,GT.pulses.length);}
}
function glFrame(t){
  const gl=GT.gl;if(!gl)return;
  camTick(t);GT.mood+=(GT.moodTarget-GT.mood)*0.04;updatePulses(t);
  gl.viewport(0,0,GT.w,GT.h);gl.clearColor(0,0,0,0);gl.clear(gl.COLOR_BUFFER_BIT);
  gl.enable(gl.BLEND);gl.blendFunc(gl.SRC_ALPHA,gl.ONE);
  const drift=REDUCE?0:(t||0)*0.00005;
  const eye=[CAM.pos[0]+Math.sin(drift)*0.55+(REDUCE?0:(PAR.x-0.5)*1.3),
    CAM.pos[1]+(REDUCE?0:(0.5-PAR.y)*0.7),
    CAM.pos[2]+Math.cos(drift)*0.35-0.35];
  const proj=m4Persp(0.9,GT.w/Math.max(1,GT.h),0.1,100),view=m4LookAt(eye,CAM.tgt,[0,1,0]);
  if(GT.nLines){gl.useProgram(GT.progL);const u=GT.locL;
    gl.uniformMatrix4fv(u.uProj,false,proj);gl.uniformMatrix4fv(u.uView,false,view);gl.uniform1f(u.uMood,GT.mood);
    gl.bindBuffer(gl.ARRAY_BUFFER,GT.bufLines);glAttrs(u,7,'L');gl.drawArrays(gl.LINES,0,GT.nLines);}
  glDrawPoints(proj,view,t,false);
  if(GT.tier===GL_TIER.WEBGL_BLOOM)glDrawPoints(proj,view,t,true);
}
function glLoop(t){glFrame(t);if(GT.run)GT.raf=requestAnimationFrame(glLoop);}
function drawOnce(){if(GT.gl)glFrame(0);}
function glSetMood(value){GT.moodTarget=value?1:0;}
function glStart(){if(GT.tier<GL_TIER.WEBGL||!GT.gl||document.hidden)return;
  if(REDUCE){drawOnce();return;}if(!GT.run){GT.run=true;GT.raf=requestAnimationFrame(glLoop);}}
function glStop(){GT.run=false;if(GT.raf)cancelAnimationFrame(GT.raf);GT.raf=0;}
function markSceneTier(){document.body.dataset.sceneTier=GL_TIER_NAME[GT.tier]||'static';}

// Canvas fallback is the previous phosphor field, started only when needed.
function startFx2D(){
  const canvas=document.getElementById('fx');if(!canvas)return;canvas.style.display='block';
  const ctx=canvas.getContext('2d');if(!ctx)return;
  let W=0,H=0,DPR=1,particles=[],raf=0,run=true,mx=.5,my=.4;
  const accRGB=()=>getComputedStyle(document.documentElement).getPropertyValue('--acc-rgb').trim()||'77,255,160';
  function size(){DPR=Math.min(1.6,window.devicePixelRatio||1);W=canvas.width=Math.floor(innerWidth*DPR);H=canvas.height=Math.floor(innerHeight*DPR);
    const n=Math.max(24,Math.round(innerWidth*innerHeight/26000));particles=[];
    for(let i=0;i<n;i++)particles.push({x:Math.random()*W,y:Math.random()*H,r:(Math.random()*1.5+.35)*DPR,s:(Math.random()*.26+.05)*DPR,a:Math.random()*.45+.13,d:Math.random()*6.28});}
  addEventListener('pointermove',e=>{mx=e.clientX/Math.max(1,innerWidth);my=e.clientY/Math.max(1,innerHeight);},{passive:true});
  function drawFxOrganism(){
    const model=GT.model;if(!model)return;
    const scale=Math.min(W,H)/13,ox=W*.54+(mx-.5)*24*DPR,oy=H*.48+(my-.5)*16*DPR;
    const project=point=>[ox+(point[0]+point[2]*.18)*scale,oy-(point[1]-point[2]*.10)*scale];
    model.edges.forEach(edge=>{const a=project(edge.a),b=project(edge.b),c=edge.col.map(x=>Math.round(x*255));
      ctx.beginPath();ctx.moveTo(a[0],a[1]);ctx.lineTo(b[0],b[1]);ctx.strokeStyle='rgba('+c.join(',')+','+Math.min(.42,edge.alpha)+')';
      ctx.lineWidth=DPR;ctx.stroke();});
    const route=(ROUTE||'').replace('#/scope/',''),active=route.includes('/')?route:null;
    model.nodes.forEach(node=>{const point=project(node.pos),c=node.col.map(x=>Math.round(x*255));
      const selected=node.id===active,radius=Math.max(2.5,(node.size/4)*(selected?1.45:1))*DPR;
      ctx.beginPath();ctx.arc(point[0],point[1],radius,0,6.29);
      ctx.shadowBlur=(selected?24:12)*DPR;ctx.shadowColor='rgba('+c.join(',')+','+Math.max(.25,node.bright)+')';
      ctx.fillStyle='rgba('+c.join(',')+','+Math.max(.18,node.bright*.78)+')';ctx.fill();});
    ctx.shadowBlur=0;
  }
  function draw(t){const rgb=accRGB();ctx.clearRect(0,0,W,H);
    const gx=mx*W,gy=my*H,g=ctx.createRadialGradient(gx,gy,0,gx,gy,340*DPR);
    g.addColorStop(0,'rgba('+rgb+',.045)');g.addColorStop(1,'rgba('+rgb+',0)');ctx.fillStyle=g;ctx.fillRect(0,0,W,H);
    drawFxOrganism();
    for(const p of particles){p.y-=p.s;p.x+=Math.sin(t*0.0004+p.d)*0.14*DPR;
      if(p.y<-4){p.y=H+4;p.x=Math.random()*W;}ctx.beginPath();ctx.arc(p.x,p.y,p.r,0,6.29);
      ctx.fillStyle='rgba('+rgb+','+p.a+')';ctx.fill();}}
  function loop(t){draw(t);if(run)raf=requestAnimationFrame(loop);}
  size();addEventListener('resize',size);
  if(REDUCE)draw(0);else{raf=requestAnimationFrame(loop);
    document.addEventListener('visibilitychange',()=>{run=!document.hidden;
      if(run)raf=requestAnimationFrame(loop);else cancelAnimationFrame(raf);});}
}

// Stable data geometry. Randomness is confined to makeDust below.
function cssRGB(name,fallback){const value=getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const parts=(value||fallback).split(',').map(Number);return [parts[0]/255,parts[1]/255,parts[2]/255];}
const clamp01=value=>Math.max(0,Math.min(1,value));
const mix3=(a,b,t)=>[a[0]+(b[0]-a[0])*t,a[1]+(b[1]-a[1])*t,a[2]+(b[2]-a[2])*t];
function edgeBright(edge){return edge==null?0.42:clamp01(0.25+((edge+0.02)/0.04)*0.75);}
function nSize(n){return Math.min(34,10+22*(Math.log10(1+(n||0))/3));}
function sceneModel(){
  const model={nodes:[],edges:[],byScope:{}};
  const acc=cssRGB('--acc-rgb','77,255,160'),secondary=cssRGB('--secondary-rgb','111,224,255');
  const status=STATE.status||{},ages=status.data_ages||{},gray=[0.45,0.52,0.48];
  const sportsStale=!!(ages.sports_model_seed&&ages.sports_model_seed.stale);
  const arsenal=STATE.arsenal||{},models=Array.isArray(arsenal.models)?arsenal.models:[],smoke=arsenal.live_smoke||{};
  const cortexGlow=smoke.all_models_live_proven===true?1:(smoke.all_models_live_proven===false?.3:.55);
  model.nodes.push({id:'cortex',kind:'cortex',pos:[0,0,0],size:30,col:acc,bright:cortexGlow});
  models.forEach((entry,i)=>{const angle=i*2.399963,radius=1.05;
    const pos=[Math.cos(angle)*radius,.25*Math.sin(angle*2),Math.sin(angle)*radius];
    model.nodes.push({id:'model:'+String(entry.model||i),kind:'cortex',pos,size:12,col:acc,bright:cortexGlow*.9});
    model.edges.push({a:[0,0,0],b:pos,col:acc,alpha:.5});});
  const sources=((STATE.overview&&STATE.overview.active_sources)||[]).slice().sort((a,b)=>
    String(a.source||a.name||a.id||'').localeCompare(String(b.source||b.name||b.id||'')));
  sources.forEach((source,i)=>{const angle=i*2.399963+.7,radius=2.1;
    const pos=[Math.cos(angle)*radius,.5*Math.sin(angle*3),Math.sin(angle)*radius];
    const weight=Number(source.weight),known=Number.isFinite(weight),bright=known?clamp01(.3+Math.abs(weight)*.7):.55;
    model.nodes.push({id:'source:'+String(source.source||source.name||i),kind:'source',pos,size:6,col:secondary,bright});
    model.edges.push({a:pos,b:[0,0,0],col:secondary,alpha:known?clamp01(.12+Math.abs(weight)*.35):.22});});
  const verticals=(STATE.scopes&&STATE.scopes.verticals)||{};
  ['CRYPTO','SPORTS'].forEach((vertical,verticalIndex)=>{
    const scopes=(verticals[vertical]&&verticals[vertical].scopes)||{};
    Object.keys(scopes).sort().forEach((label,labelIndex)=>{
      const scope=scopes[label]||{},summary=scope.summary||{},index=verticalIndex*16+labelIndex;
      const angle=index*2.399963,radius=3.4+.28*Math.sqrt(index);
      const pos=[Math.cos(angle)*radius,(verticalIndex?-1:1)+.15*Math.sin(angle*2),Math.sin(angle)*radius];
      const inSeason=scope.in_season!==false&&String(scope.season_status||'')!=='off';
      const stale=vertical==='SPORTS'&&sportsStale;
      let bright=edgeBright(summary.brier_edge);if(!inSeason)bright*=.5;if(stale)bright*=.35;
      const base=vertical==='CRYPTO'?acc:secondary,col=stale?mix3(base,gray,.65):base;
      model.nodes.push({id:vertical+'/'+label,kind:'scope',pos,
        size:nSize(summary.contested_n!=null?summary.contested_n:summary.n),col,bright});
      model.edges.push({a:[0,0,0],b:pos,col,alpha:.3});model.byScope[vertical+'/'+label]=pos;
    });
  });
  return model;
}

// ambient dust -- the ONLY decorative element; represents nothing.
function makeDust(count){
  const nodes=[];
  for(let i=0;i<count;i++)nodes.push({pos:[(Math.random()-.5)*22,(Math.random()-.5)*10,(Math.random()-.5)*22],
    size:2.2+Math.random()*2.4,bright:.05+Math.random()*.1});
  return nodes;
}
const flat8=node=>[node.pos[0],node.pos[1],node.pos[2],node.size,node.col[0],node.col[1],node.col[2],node.bright];
function glBuild(model){
  GT.model=model;const gl=GT.gl;if(!gl)return;
  const points=new Float32Array(model.nodes.length*8);
  model.nodes.forEach((node,i)=>points.set(flat8(node),i*8));GT.nPts=model.nodes.length;
  gl.bindBuffer(gl.ARRAY_BUFFER,GT.bufPts);gl.bufferData(gl.ARRAY_BUFFER,points,gl.STATIC_DRAW);
  const lines=new Float32Array(model.edges.length*14);
  model.edges.forEach((edge,i)=>{lines.set([...edge.a,...edge.col,edge.alpha],i*14);
    lines.set([...edge.b,...edge.col,edge.alpha],i*14+7);});
  GT.nLines=model.edges.length*2;gl.bindBuffer(gl.ARRAY_BUFFER,GT.bufLines);gl.bufferData(gl.ARRAY_BUFFER,lines,gl.STATIC_DRAW);
  const count=GT.tier===GL_TIER.WEBGL_BLOOM?600:(GT.tier===GL_TIER.WEBGL?320:0);
  if(!GT.dust||GT.dust.length!==count)GT.dust=makeDust(count);
  const dustColor=cssRGB('--acc-rgb','77,255,160'),dustPoints=new Float32Array(GT.dust.length*8);
  GT.dust.forEach((node,i)=>dustPoints.set([node.pos[0],node.pos[1],node.pos[2],node.size,
    dustColor[0],dustColor[1],dustColor[2],node.bright],i*8));
  GT.nDust=GT.dust.length;gl.bindBuffer(gl.ARRAY_BUFFER,GT.bufDust);gl.bufferData(gl.ARRAY_BUFFER,dustPoints,gl.STATIC_DRAW);
  if(REDUCE)drawOnce();
}

// ---------- camera ----------
addEventListener('pointermove',e=>{PAR.x=e.clientX/Math.max(1,innerWidth);PAR.y=e.clientY/Math.max(1,innerHeight);},{passive:true});
const easeIO=t=>t<.5?4*t*t*t:1-Math.pow(-2*t+2,3)/2;
function flyTo(preset,ms){
  if(REDUCE){CAM.pos=preset.pos.slice();CAM.tgt=preset.tgt.slice();CAM.anim=null;drawOnce();return;}
  CAM.anim={p0:CAM.pos.slice(),t0:CAM.tgt.slice(),p1:preset.pos.slice(),t1:preset.tgt.slice(),
    start:performance.now(),ms:ms||900};
}
function scopePreset(id){
  const point=GT.model&&GT.model.byScope&&GT.model.byScope[id];if(!point)return CAM_PRESETS.overview;
  const length=Math.hypot(point[0],point[2])||1;
  return {pos:[point[0]+point[0]/length*2.4,point[1]+1.15,point[2]+point[2]/length*2.4],
    tgt:[point[0],point[1],point[2]]};
}
function syncCameraToRoute(immediate){
  if(!GT.gl)return;
  const parts=(ROUTE||location.hash||'#/overview').replace('#/','').split('/');
  const scope=parts[0]==='scope'&&(parts[1]==='CRYPTO'||parts[1]==='SPORTS')&&parts[2]
    ?parts[1]+'/'+parts[2]:null;
  flyTo(scope?scopePreset(scope):CAM_PRESETS.overview,immediate?1:900);
}
function camTick(t){
  if(!CAM.anim)return;const animation=CAM.anim;
  const k=Math.min(1,(performance.now()-animation.start)/animation.ms),e=easeIO(k);
  CAM.pos=[0,1,2].map(i=>animation.p0[i]+(animation.p1[i]-animation.p0[i])*e);
  CAM.tgt=[0,1,2].map(i=>animation.t0[i]+(animation.t1[i]-animation.t0[i])*e);
  if(k>=1)CAM.anim=null;
}

function glInit(){
  const canvas=document.getElementById('gl');if(!canvas)return;
  const boot=bootGL(canvas);
  probeTier(fps=>{
    if(boot&&fps>=50)GT.tier=GL_TIER.WEBGL_BLOOM;
    else if(boot&&fps>=28)GT.tier=GL_TIER.WEBGL;
    else if(fps>=24)GT.tier=GL_TIER.CANVAS2D;
    else GT.tier=GL_TIER.STATIC;
    if(GT.tier>=GL_TIER.WEBGL){try{glSetup(boot);}catch(_){GT.gl=null;GT.tier=GL_TIER.CANVAS2D;}}
    markSceneTier();
    if(GT.tier===GL_TIER.CANVAS2D){GT.model=sceneModel();canvas.style.display='none';startFx2D();return;}
    if(GT.tier===GL_TIER.STATIC){document.body.classList.add('no-gl');return;}
    canvas.addEventListener('webglcontextlost',event=>{event.preventDefault();glStop();GT.gl=null;
      GT.tier=GL_TIER.CANVAS2D;markSceneTier();canvas.style.display='none';startFx2D();});
    addEventListener('resize',()=>{glResize();if(REDUCE)drawOnce();});
    document.addEventListener('visibilitychange',()=>{if(document.hidden)glStop();else glStart();});
    glBuild(sceneModel());syncCameraToRoute(true);glStart();
  });
}

// ---------- EVENTS ----------
// Semantic bridge: all scene activity derives from already-polled STATE.
const EV={map:{}};
EV.on=(name,handler)=>{(EV.map[name]=EV.map[name]||[]).push(handler);};
EV.emit=(name,data)=>{(EV.map[name]||[]).forEach(handler=>{try{handler(data);}catch(_){}});};
let prevWatch=null;
function watchSnapshot(){
  const summary=statusSummary(),ages=((STATE.status||{}).data_ages)||{};
  const watch={bal:((STATE.overview||{}).live_account||{}).balance_cents,auth:summary.auth,
    liveAuth:summary.liveAuth,healthy:summary.healthy,mode:summary.mode,freshness:{},scopes:{}};
  Object.keys(ages).sort().forEach(key=>{watch.freshness[key]=ages[key]&&ages[key].stale;});
  const verticals=(STATE.scopes&&STATE.scopes.verticals)||{};
  ['CRYPTO','SPORTS'].forEach(vertical=>{const scopes=(verticals[vertical]&&verticals[vertical].scopes)||{};
    Object.keys(scopes).forEach(label=>{const scope=scopes[label]||{},s=scope.summary||{};
      watch.scopes[vertical+'/'+label]=[s.hit_rate,s.brier_edge,s.contested_n,(scope.picks||[]).length,
        scope.in_season,scope.season_status];});});
  return watch;
}
function watchDiff(next){
  if(!prevWatch){prevWatch=next;glSetMood(next.liveAuth||next.healthy===false);return;}
  if(next.bal!==prevWatch.bal)EV.emit('balance:changed',{from:prevWatch.bal,to:next.bal});
  if(next.auth!==prevWatch.auth)EV.emit('authority:changed',{to:next.auth});
  if(next.healthy!==prevWatch.healthy)EV.emit('health:changed',{to:next.healthy});
  if(JSON.stringify(next.freshness)!==JSON.stringify(prevWatch.freshness))EV.emit('freshness:changed',{to:next.freshness});
  Object.keys(next.scopes).forEach(key=>{const current=next.scopes[key],before=prevWatch.scopes[key];
    if(!before||current.some((value,i)=>value!==before[i]))EV.emit('scope:changed',{id:key});});
  prevWatch=next;glSetMood(next.liveAuth||next.healthy===false);
}

// pulses: one real data change travels from the cortex to its scope cluster.
function glPulse(scopeId){
  if(REDUCE||!GT.gl||!GT.model)return;const target=GT.model.byScope[scopeId];if(!target)return;
  if(GT.pulses.length>=64)GT.pulses.shift();
  GT.pulses.push({a:[0,0,0],b:target.slice(),t0:performance.now(),dur:1400});
}
function updatePulses(t){
  if(!GT.gl)return;const now=performance.now();
  GT.pulses=GT.pulses.filter(pulse=>now-pulse.t0<pulse.dur);if(!GT.pulses.length)return;
  const acc=cssRGB('--acc-rgb','77,255,160'),data=new Float32Array(GT.pulses.length*8);
  GT.pulses.forEach((pulse,i)=>{const k=(now-pulse.t0)/pulse.dur,e=k*k*(3-2*k);
    data.set([pulse.a[0]+(pulse.b[0]-pulse.a[0])*e,pulse.a[1]+(pulse.b[1]-pulse.a[1])*e,
      pulse.a[2]+(pulse.b[2]-pulse.a[2])*e,9,...acc,1],i*8);});
  const gl=GT.gl;gl.bindBuffer(gl.ARRAY_BUFFER,GT.bufPulse);gl.bufferData(gl.ARRAY_BUFFER,data,gl.DYNAMIC_DRAW);
}
EV.on('scope:changed',event=>glPulse(event.id));
EV.on('snapshot:arrived',()=>{const model=sceneModel();if(GT.gl)glBuild(model);else GT.model=model;});
function shock(){if(REDUCE)return;const s=document.getElementById('shock');s.classList.remove('go');void s.offsetWidth;s.classList.add('go');}

// ---------- data ----------
async function poll(){
  if(POLLING)return;
  POLLING=true;STATE.connection.pending=true;
  try{
    const get=async(url)=>{const r=await fetch(url);if(!r.ok)throw new Error(url+' returned '+r.status);return r.json();};
    const results=await Promise.allSettled(['/api/overview','/api/scopes','/api/status','/api/walk_forward','/api/bet_board','/api/model-arsenal','/api/tier-performance'].map(get));
    const [ov,sc,st,wf,bb,arsenal,tiers]=results.map(r=>r.status==='fulfilled'?r.value:null);
    // Tier-performance is deliberately fail-closed until a validated forward
    // artifact exists. Its own card explains that state; it must not make the
    // otherwise healthy operator board look generically degraded.
    const failed=results.slice(0,6).filter(r=>r.status==='rejected');
    STATE.connection.error=failed.length?failed.length+' data source'+(failed.length===1?' is':'s are')+' unavailable; showing the last good snapshot.':null;
    STATE.tierPerformanceFetchOk=results[6].status==='fulfilled';
    if(ov)STATE.overview=ov;if(sc)STATE.scopes=sc;if(st)STATE.status=st;
    if(wf)STATE.walk=wf.leagues||{};
    STATE.boardFetchOk=results[4].status==='fulfilled';
    if(bb){STATE.board=bb.groups||{};STATE.boardMeta=bb;}
    if(arsenal)STATE.arsenal=arsenal;
    if(tiers)STATE.tierPerformance=tiers;
    const live=document.getElementById('live'),fs=document.getElementById('footstat'),sideMode=document.getElementById('sideMode');
    const fresh=ov&&ov.generated_at&&(Date.now()-Date.parse(ov.generated_at))<30*60*1000;
    live.className='dot'+(fresh?' live':'');
    fs.textContent=fresh?'snapshot · '+ago(ov.generated_at):'snapshot stale';
    const summary=statusSummary();
    sideMode.textContent=summary.mode;sideMode.className='modechip '+(summary.liveAuth?'live-auth':(summary.mode==='SHADOW'?'shadow':''));
    // re-render (and re-flip the flaps) only when the data actually changed --
    // like a real tote board, the numbers roll when new results land.
    const sig=JSON.stringify([STATE.overview,STATE.scopes,STATE.status&&STATE.status.system_health,STATE.status&&STATE.status.edge_quality,STATE.boardFetchOk,STATE.boardMeta&&STATE.boardMeta.generated_at,STATE.boardMeta&&STATE.boardMeta.artifact_status,STATE.boardMeta&&STATE.boardMeta.stale,STATE.arsenal,STATE.tierPerformance,STATE.tierPerformanceFetchOk,summary.mode,summary.title,summary.healthy,summary.accountFresh,summary.auth,summary.stale.map(([k])=>k),STATE.connection.error]);
    if(sig!==lastSig){const had=lastSig!=='';lastSig=sig;render();watchDiff(watchSnapshot());EV.emit('snapshot:arrived',{had});if(had)shock();}
  }catch(e){STATE.connection.error='Dashboard refresh failed; showing the last good snapshot.';render();}
  finally{POLLING=false;STATE.connection.pending=false;}
}
window.addEventListener('hashchange',()=>{ROUTE=location.hash||'#/overview';render();});
window.addEventListener('resize',()=>moveGlide());
glInit();render();poll();setInterval(poll,20000);
</script>
</body></html>"""
