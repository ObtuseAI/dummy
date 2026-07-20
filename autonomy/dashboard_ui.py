"""Wave-51/53/55: the operator dashboard (single-page, vanilla, offline).

A dark, data-dense board in the house tote-green "totalizator" identity, pushed
to a premium, *living* finish (Wave-55):

  * an ambient phosphor field on a <canvas> backdrop -- slow drifting embers and
    a soft glow that parallaxes toward the pointer (one static frame under
    prefers-reduced-motion, paused when the tab is hidden);
  * an always-on pari-mutuel ticker tape that streams the live picks and
    mispricing across every scope, right-to-left, pausing under the pointer;
  * a hero band with an animated radial ROI gauge and a bankroll sparkline;
  * split-flap flip counters that roll only when new data actually lands;
  * cards that tilt in 3D and catch a specular highlight under the cursor;
  * a Cmd/Ctrl-K command palette to jump to any scope from the keyboard;
  * a phosphor-tube accent switcher (emerald / amber / cyan / violet, saved);
  * a faint shockwave that sweeps the board the moment a new snapshot lands;
  * hand-drawn SVG charts that draw themselves in and answer a hover crosshair.

Left nav = Overview plus a Crypto and a Sports section listing their coins /
leagues; the stage shows the overview (paper account, balance curve, promotion
ladder) or a per-scope breakdown (graded accuracy, progression, model-vs-market,
current picks) with the legacy surfaces folded into each scope's "Other data".

No build step, no CDN: served as one string, system fonts (Bahnschrift/Cascadia
for tabular numerics), hand-drawn SVG, CSS-only motion + a tiny canvas loop.
Consumes /api/overview, /api/scopes, /api/status -- all from the persisted
snapshot (never the ledger). prefers-reduced-motion freezes every animation;
semantic up/down stays green/red whatever the accent tube; contrast holds AA.

Design intelligence: ui-ux-pro-max Data-Dense Dashboard x a restrained slice of
terminal/phosphor treatment; motion tiers + chart specs from its motion/chart DB.
"""
from __future__ import annotations

DASHBOARD_HTML = r"""<!doctype html>
<html lang="en" data-accent="emerald"><head>
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
  /* accent = the phosphor "tube" colour; swaps the chrome, never the pos/neg semantics */
  --acc:#2fe38f; --acc-2:#0f7a52; --acc-glow:rgba(77,255,160,.22); --acc-rgb:77,255,160;
  --mono:"Cascadia Mono","Consolas",ui-monospace,monospace;
  --disp:"Bahnschrift","DIN Alternate Bold","Segoe UI Semibold","Segoe UI",sans-serif;
  --body:"Segoe UI",system-ui,-apple-system,sans-serif;
  --s1:6px; --s2:10px; --s3:16px; --s4:24px; --r:14px;
  --ease:cubic-bezier(.2,.8,.2,1); --spring:cubic-bezier(.16,1.1,.3,1);
}
html[data-accent=amber] {--acc:#ffc24d;--acc-2:#7a4e12;--acc-glow:rgba(255,194,77,.22);--acc-rgb:255,194,77}
html[data-accent=cyan]  {--acc:#6fe0ff;--acc-2:#12667a;--acc-glow:rgba(111,224,255,.22);--acc-rgb:111,224,255}
html[data-accent=violet]{--acc:#b79cff;--acc-2:#4a3a8a;--acc-glow:rgba(183,156,255,.24);--acc-rgb:183,156,255}
*{box-sizing:border-box}
html,body{margin:0;height:100%}
body{background:
    radial-gradient(1300px 760px at 82% -14%, rgba(var(--acc-rgb),.10), transparent 60%),
    radial-gradient(1000px 640px at -6% 112%, rgba(111,224,255,.045), transparent 55%),
    var(--bg);
  color:var(--txt);font-family:var(--body);font-size:14px;line-height:1.5;
  -webkit-font-smoothing:antialiased;overflow:hidden}
/* ambient phosphor field */
#fx{position:fixed;inset:0;z-index:0;pointer-events:none;display:block}
/* faint CRT scanline — static (no motion), very low contrast */
body::after{content:"";position:fixed;inset:0;pointer-events:none;z-index:9;
  background:repeating-linear-gradient(0deg,rgba(0,0,0,.16) 0 1px,transparent 1px 3px);
  opacity:.30;mix-blend-mode:overlay}
a{color:inherit;text-decoration:none}
::-webkit-scrollbar{width:10px;height:10px}
::-webkit-scrollbar-thumb{background:var(--line-2);border-radius:8px;border:2px solid transparent;background-clip:padding-box}
::-webkit-scrollbar-thumb:hover{background:var(--line-3);background-clip:padding-box}
::-webkit-scrollbar-track{background:transparent}
:focus-visible{outline:2px solid var(--acc);outline-offset:2px;border-radius:6px}

#app{position:relative;z-index:1;display:grid;grid-template-columns:250px 1fr;height:100vh}

/* ---------- sidebar ---------- */
.side{position:relative;background:linear-gradient(180deg,rgba(7,24,17,.86),rgba(4,16,10,.92));
  backdrop-filter:blur(8px);border-right:1px solid var(--line);display:flex;flex-direction:column;min-height:0}
.side::after{content:"";position:absolute;top:0;right:0;width:1px;height:100%;
  background:linear-gradient(180deg,transparent,var(--line-2) 30%,var(--line-2) 70%,transparent)}
.brand{padding:var(--s4) var(--s3) var(--s3);display:flex;align-items:center;gap:11px}
.brand .mark{position:relative;width:36px;height:36px;border-radius:10px;display:grid;place-items:center;
  background:radial-gradient(circle at 32% 26%,var(--acc),var(--acc-2));
  box-shadow:0 0 22px var(--acc-glow),inset 0 1px 1px rgba(255,255,255,.35);
  color:#04140d;font-family:var(--disp);font-weight:700;font-size:19px}
.brand .mark::before{content:"";position:absolute;inset:-3px;border-radius:13px;
  background:conic-gradient(from 0deg,transparent,rgba(var(--acc-rgb),.55),transparent 42%);
  animation:spin 6s linear infinite;z-index:-1;opacity:.9}
@keyframes spin{to{transform:rotate(360deg)}}
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
  display:flex;align-items:center;gap:8px;font-size:11px;color:var(--muted)}
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

/* pari-mutuel ticker tape */
.tape{position:sticky;top:0;z-index:8;margin:0 calc(-1*var(--s4)) var(--s3);
  background:linear-gradient(180deg,rgba(6,20,14,.94),rgba(6,20,14,.82));
  backdrop-filter:blur(8px);border-bottom:1px solid var(--line);overflow:hidden;height:44px;display:flex;align-items:stretch}
.tape::before{content:"LIVE TAPE";position:absolute;left:0;top:0;bottom:0;z-index:2;display:flex;align-items:center;
  padding:0 13px;font-family:var(--disp);font-size:10px;letter-spacing:.22em;color:var(--acc);
  background:linear-gradient(90deg,var(--bg-1) 74%,transparent);text-shadow:0 0 10px var(--acc-glow)}
.tape::after{content:"";position:absolute;right:0;top:0;bottom:0;width:48px;z-index:2;
  background:linear-gradient(270deg,var(--bg-1),transparent);pointer-events:none}
/* NB: class is "ttrack" not "track" -- the progress-bar .track rule (height:8px;
   overflow:hidden) was clipping the ticker to an unreadable sliver. */
.tape .ttrack{display:flex;align-items:center;height:100%;gap:0;white-space:nowrap;padding-left:104px;
  will-change:transform;animation:marq var(--dur,60s) linear infinite}
.tape:hover .ttrack{animation-play-state:paused}
@keyframes marq{to{transform:translateX(-50%)}}
.tape .ti{display:inline-flex;align-items:center;gap:9px;padding:0 20px;font-family:var(--mono);font-size:13.5px;
  color:var(--muted);border-right:1px solid var(--line)}
.tape .ti .sc{color:var(--faint);font-size:11px;letter-spacing:.12em;text-transform:uppercase}
.tape .ti .mk{color:var(--txt)}
.tape .ti .bt2{color:var(--acc);font-size:12px}
.tape .ti b{color:var(--phos)}
.tape .ti .up{color:var(--green)} .tape .ti .dn{color:var(--red)}
.tape.off{display:none}

#view{animation:swap .42s var(--ease);padding-top:var(--s3)}
@keyframes swap{from{opacity:0;transform:translateY(8px)}}
.topbar{display:flex;align-items:baseline;gap:14px;margin-bottom:var(--s3)}
.topbar h2{margin:0;font-family:var(--disp);font-size:27px;letter-spacing:.02em;text-shadow:0 0 22px var(--acc-glow)}
.topbar .crumb{font-size:10.5px;letter-spacing:.24em;text-transform:uppercase;color:var(--faint)}
.topbar .spacer{flex:1}
.stamp{font-family:var(--mono);font-size:11px;color:var(--muted);display:flex;align-items:center;gap:7px}
.stamp .beat{width:6px;height:6px;border-radius:50%;background:var(--acc);box-shadow:0 0 8px var(--acc);animation:pulse 2.4s infinite}

.grid{display:grid;gap:var(--s3)}
.kpis{grid-template-columns:repeat(auto-fit,minmax(172px,1fr))}
.cols2{grid-template-columns:1fr 1fr}
.hero{grid-template-columns:1.25fr .85fr 1fr;margin-bottom:var(--s3)}
@media(max-width:1040px){.hero{grid-template-columns:1fr 1fr}.hero .gaugecard{grid-column:span 2}}
@media(max-width:920px){.cols2,.hero{grid-template-columns:1fr}.hero .gaugecard{grid-column:auto}
  #app{grid-template-columns:64px 1fr}
  .brand h1,.brand .sub,.item span:not(.tag),.grp span:last-child,.foot #footstat,.foot .kbd{display:none}}

.card{position:relative;background:linear-gradient(180deg,rgba(8,28,19,.80),rgba(7,24,17,.90));
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
.acct .spark{margin-top:6px}
.mini{display:grid;grid-template-columns:1fr;gap:9px}
.mini .row{display:flex;align-items:baseline;justify-content:space-between;gap:10px;
  padding-bottom:8px;border-bottom:1px solid rgba(18,53,40,.5)}
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
td{padding:8px 10px;border-bottom:1px solid rgba(18,53,40,.55);white-space:nowrap}
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
.bt-tab .c{color:var(--faint);font-size:10px;margin-left:2px}
.bt-panel{display:none} .bt-panel.on{display:block}
.res-ok{color:var(--green)} .res-no{color:var(--red)}
/* day's games, click to expand */
.games{display:flex;flex-direction:column;gap:8px;max-height:440px;overflow:auto}
.game{border:1px solid var(--line);border-radius:10px;overflow:hidden;transition:border-color .15s}
.game:hover{border-color:var(--line-2)}
.ghead{display:grid;grid-template-columns:22px 1fr auto auto;gap:10px;align-items:center;padding:10px 12px;cursor:pointer;
  font-family:var(--mono);font-size:12.5px;background:var(--panel-2)}
.ghead:hover{background:var(--panel-3)}
.ghead .gx{color:var(--faint);transition:transform .2s}
.game.open .ghead .gx{transform:rotate(90deg);color:var(--acc)}
.ghead .gc{color:var(--faint);font-size:11px} .ghead .ge{color:var(--acc);font-size:11.5px}
.gbody{display:none;padding:2px 8px 8px}
.game.open .gbody{display:block}
.game.open .ghead{border-bottom:1px solid var(--line)}

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
  padding-top:14vh;background:rgba(2,8,5,.55);backdrop-filter:blur(3px)}
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

/* snapshot shockwave — one-shot phosphor ripple when new data lands */
#shock{position:fixed;inset:0;z-index:7;pointer-events:none;opacity:0}
#shock.go{animation:shock 1.1s var(--ease)}
@keyframes shock{0%{opacity:.9;background:radial-gradient(circle at 50% 42%,rgba(var(--acc-rgb),.16),transparent 8%)}
  100%{opacity:0;background:radial-gradient(circle at 50% 42%,rgba(var(--acc-rgb),0),transparent 120%)}}

@media(prefers-reduced-motion:reduce){*{animation:none!important;transition:none!important}
  .chart .draw{stroke-dashoffset:0}.fill{width:var(--w,60%)!important}
  .gauge .val-arc{stroke-dashoffset:var(--off)!important}.tape .ttrack{transform:none}}
</style>
</head><body>
<canvas id="fx"></canvas>
<div id="shock"></div>
<div id="app">
  <aside class="side">
    <div class="brand">
      <div class="mark">D</div>
      <div><h1>DUMMY</h1><div class="sub">totalizator</div></div>
    </div>
    <nav class="nav" id="nav"><div class="glide" id="glide"></div></nav>
    <div class="foot">
      <span class="dot" id="live"></span><span id="footstat">connecting…</span>
      <span class="kbd" title="command palette">⌘K</span>
      <span class="tubes" id="tubes" role="group" aria-label="phosphor accent"></span>
    </div>
  </aside>
  <main class="stage">
    <div class="tape off" id="tape" aria-hidden="true"><div class="ttrack" id="tapetrack"></div></div>
    <div id="view"></div>
  </main>
</div>
<div class="cmdk" id="cmdk" role="dialog" aria-modal="true" aria-label="Jump to">
  <div class="box">
    <input id="cmdq" type="text" placeholder="Jump to a scope…  (type to filter)" autocomplete="off" spellcheck="false">
    <div class="list" id="cmdlist"></div>
    <div class="foot2"><span>↑↓ navigate</span><span>⏎ open</span><span>esc close</span><span>t · cycle tube</span></div>
  </div>
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
const REDUCE=matchMedia('(prefers-reduced-motion:reduce)').matches;

let STATE={overview:null,scopes:null,status:null,walk:null,board:null};
let ROUTE=location.hash||'#/overview';
let lastSig='';
// every sport league the board lists, in season or not (backend enriches each
// with season + last-season grades; this keeps the slate whole even before the
// next snapshot lands).
const SPORTS_ROSTER=['MLB','WNBA','NBA','NFL','NHL','NCAAF','NCAAMB'];

function svgIcon(k){return '<svg viewBox="0 0 24 24">'+(ICON[k]||ICON.overview)+'</svg>';}

// ---------- charts ----------
function areaChart(pts,{h=170,color='var(--acc)'}={}){
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
  const v=(STATE.scopes&&STATE.scopes.verticals)||{};
  [['CRYPTO','coin'],['SPORTS','ball']].forEach(([key,cicon])=>{
    const block=v[key];
    nav.appendChild($('<div class="grp"><span>'+key+'</span><span>'+(block?pct(block.summary.hit_rate,0):'')+'</span></div>'));
    const labels=scopeLabels(key,block);
    if(!labels.length){nav.appendChild($('<div class="item child" style="color:var(--faint)"><span>no data</span></div>'));return;}
    labels.forEach(lab=>{
      const sc=block&&block.scopes&&block.scopes[lab];
      const off=sc?sc.in_season===false:false;
      const tag=sc&&sc.summary&&sc.summary.hit_rate!=null?pct(sc.summary.hit_rate,0):(off?'off':'·');
      const it=navItem(cicon,lab,'#/scope/'+key+'/'+lab,tag);
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
    return [...new Set([...have,...SPORTS_ROSTER])].sort((a,b)=>{
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

// ---------- live ticker tape (today's markets only, from the bet board) ----------
function buildTape(){
  const tape=document.getElementById('tape'),track=document.getElementById('tapetrack');
  const board=STATE.board||{};
  const today=new Date().toISOString().slice(0,10);
  const items=[];
  Object.entries(board).forEach(([scope,grp])=>{
    if(!grp||typeof grp!=='object')return;
    Object.values(grp).forEach(rows=>(rows||[]).forEach(r=>{
      if((r.close_time||'').slice(0,10)!==today)return;      // current date only
      items.push({scope:String(scope).toUpperCase(),matchup:r.matchup,bet:r.bet_type,
                  side:r.pick,model:r.probability,edge:r.edge});
    }));
  });
  if(!items.length){tape.classList.add('off');tape.setAttribute('aria-hidden','true');return;}
  tape.classList.remove('off');tape.setAttribute('aria-hidden','false');
  // cap per scope so one high-edge scope (usually crypto) can't crowd out the rest
  const byScope={};items.forEach(it=>{(byScope[it.scope]=byScope[it.scope]||[]).push(it);});
  let top=[];Object.values(byScope).forEach(list=>{list.sort((a,b)=>Math.abs(b.edge||0)-Math.abs(a.edge||0));top=top.concat(list.slice(0,6));});
  top.sort((a,b)=>Math.abs(b.edge||0)-Math.abs(a.edge||0));
  top=top.slice(0,40);
  const CRYPTO={btc:1,eth:1,sol:1,doge:1,xrp:1};
  const teamsOnly=(m)=>{const mm=String(m||'').match(/^\d{2}[A-Z]{3}\d{2}\d{0,4}([A-Z]+)$/);return mm?mm[1]:'';};
  const cell=(it)=>{
    const e=it.edge,cls=e==null?'':(e>=0?'up':'dn');
    const es=e==null?'':' <span class="'+cls+'">'+signed(e,1)+'</span>';
    const md=it.model==null?'':' <b>'+(+it.model).toFixed(2)+'</b>';
    const side=it.side?' <span class="pill '+(String(it.side).toLowerCase()==='no'?'no':'yes')+'" style="font-size:9px;padding:1px 5px">'+esc(String(it.side).toUpperCase())+'</span>':'';
    const teams=CRYPTO[String(it.scope).toLowerCase()]?'':teamsOnly(it.matchup);
    const mk=teams?'<span class="mk">'+esc(teams)+'</span>':'';
    return '<span class="ti"><span class="sc">'+esc(it.scope)+'</span>'+mk
      +'<span class="bt2">'+esc(prettyBet(it.bet))+'</span>'+side+md+es+'</span>';
  };
  const html=top.map(cell).join('');
  track.innerHTML=html+html;   // two copies for a seamless -50% loop
  track.style.setProperty('--dur',Math.max(30,top.length*4.6)+'s');
}

// ---------- views ----------
function render(){
  const view=document.getElementById('view');
  const parts=ROUTE.replace('#/','').split('/');
  view.style.animation='none';void view.offsetWidth;view.style.animation='';
  if(parts[0]==='scope'&&parts[1]&&parts[2])view.innerHTML=scopeView(parts[1],parts[2]);
  else view.innerHTML=overviewView();
  [...view.querySelectorAll('.reveal')].forEach((el,i)=>el.style.animationDelay=(i*45)+'ms');
  buildNav();buildTape();
}
function kpi(lab,val,cls,sub,doFlip){
  return '<div class="card kpi reveal"><div class="lab">'+lab+'</div><div class="val '+(cls||'')+'">'+(doFlip?flip(val):val)+'</div>'+(sub?'<div class="sub">'+sub+'</div>':'')+'</div>';
}
function overviewView(){
  const o=STATE.overview;
  if(!o||o.error||o.bankroll_cents==null)return topbar('Overview','account & promotion ladder')+skeleton();
  const rts=o.realized_trade_statistics||{};
  const curveRaw=o.balance_curve||[];
  const curve=curveRaw.map(p=>({v:p.bankroll_cents,disp:(p.bankroll_cents/100),t:(p.t||'').slice(0,10)}));
  const sparkPts=curveRaw.slice(-30).map(p=>p.bankroll_cents);
  let h=topbar('Overview','account & promotion ladder');
  // hero band: account + ROI gauge + quick stats
  h+='<div class="grid hero">';
  h+='<div class="card acct reveal"><div><div class="lab" style="font-size:9.5px;letter-spacing:.2em;text-transform:uppercase;color:var(--faint);display:flex;gap:8px;align-items:center">Paper account <span class="badge"><span class="d"></span>paper</span></div>'
    +'<div class="big">'+flip(fmtUSD(o.bankroll_cents))+'</div>'
    +'<div class="sub" style="font-family:var(--mono);color:var(--muted);margin-top:4px">base '+fmtUSD(o.base_bankroll_cents)+'</div></div>'
    +'<div class="spark">'+(spark(sparkPts,{color:o.account_roi>=0?'var(--green)':'var(--red)'})||'<div class="sub" style="color:var(--faint)">curve warming up…</div>')+'</div></div>';
  h+='<div class="card gaugecard reveal">'+gauge(o.account_roi,{span:0.5,label:'Account ROI'})+'</div>';
  h+='<div class="card reveal"><div class="mini">'
    +miniRow('Open exposure',fmtUSD(o.exposure_cents),'amb')
    +miniRow('Realized P&amp;L',fmtUSD(o.realized_pnl_cents),sgn(o.realized_pnl_cents))
    +miniRow('Settled trades',commaN(rts.trades||0),'')
    +miniRow('Stage',esc(o.stage==null?'—':o.stage),'cy')
    +'</div></div>';
  h+='</div>';
  h+='<div class="card reveal" style="margin-bottom:var(--s3)"><h3>Balance curve <span class="r">'+curveRaw.length+' pts · paper $</span></h3>'
    +areaChart(curve,{h:176,color:o.account_roi>=0?'var(--green)':'var(--red)'})
    +'<div class="legend"><span><i style="background:var(--green)"></i>paper bankroll</span><span style="color:var(--faint)">hover for value · date</span></div></div>';
  h+=accuracyPanel();
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
  let h='<div class="card reveal" style="margin-bottom:var(--s3)"><h3>Accuracy &amp; improvement <span class="r">'+commaN(s.n)+' graded · recent vs prior window</span></h3>';
  h+='<div class="acc-hero">'
    +'<div class="acc-stat"><div class="lab">Brier</div><div class="val">'+flip(num(s.brier))+'</div><div class="sub">lower = sharper</div></div>'
    +'<div class="acc-stat"><div class="lab">Hit rate</div><div class="val '+(s.hit_rate>=.5?'pos':'')+'">'+flip(pct(s.hit_rate))+'</div><div class="sub">directional</div></div>'
    +'<div class="acc-stat"><div class="lab">Edge vs market</div><div class="val '+sgn(s.brier_edge)+'">'+flip(signed(s.brier_edge,2))+'</div><div class="sub">'+commaN(s.contested_n||0)+' contested</div></div>'
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
function pickRows(picks){
  return '<div style="max-height:300px;overflow:auto"><table><thead><tr><th>Market</th><th>Side</th><th>Model</th><th>Mkt</th><th>Edge¢</th></tr></thead><tbody>'
    +picks.map(p=>'<tr><td title="'+esc(p.ticker)+'">'+esc(p.ticker)+'</td>'
      +'<td><span class="pill '+((p.side||'').toUpperCase().includes('NO')?'no':'yes')+'">'+esc(p.side||'')+'</span></td>'
      +'<td>'+num(p.prob,2)+'</td><td>'+(p.market==null?'—':num(p.market,2))+'</td>'
      +'<td class="'+(p.edge_cents>=0?'pos':'neg')+'">'+(p.edge_cents>0?'+':'')+num(p.edge_cents,1)+'</td></tr>').join('')
    +'</tbody></table></div>';
}
function pickBoardCard(scope){
  const board=scope.pick_board||{};
  const types=Object.keys(board).filter(t=>board[t]&&board[t].length);
  if(!types.length)return '';
  let h='<div class="card reveal" style="margin-top:var(--s3)"><h3>Bet-type rankings <span class="r">open edge · choose a bet</span></h3>';
  h+='<div class="bt-tabs">'+types.map((t,i)=>'<button class="bt-tab'+(i===0?' on':'')+'" data-bt="'+esc(t)+'">'+esc(t)+'<span class="c">'+board[t].length+'</span></button>').join('')+'</div>';
  h+='<div class="bt-panels">'+types.map((t,i)=>'<div class="bt-panel'+(i===0?' on':'')+'" data-bt="'+esc(t)+'">'+pickRows(board[t])+'</div>').join('')+'</div>';
  return h+'</div>';
}
function settledTodayCard(scope){
  const rows=scope.settled_today||[];
  if(!rows.length)return '';
  const correct=rows.filter(r=>r.correct).length;
  const pctc=Math.round(correct/rows.length*100);
  let h='<div class="card pad0 reveal" style="margin-top:var(--s3)"><h3 style="padding:var(--s3) var(--s3) var(--s2)">Settled today '
    +'<span class="r"><b class="'+(pctc>=50?'res-ok':'res-no')+'">'+correct+'/'+rows.length+'</b> correct · '+pctc+'%</span></h3>';
  h+='<div style="max-height:300px;overflow:auto"><table><thead><tr><th>Market</th><th>Bet</th><th>Lean</th><th>Model</th><th>Result</th><th>Call</th></tr></thead><tbody>';
  rows.forEach(r=>{h+='<tr><td title="'+esc(r.ticker)+'">'+esc((r.ticker||'').slice(0,26))+'</td><td>'+esc(prettyBet(r.bet_type))+'</td>'
    +'<td>'+esc(r.lean)+(r.traded?' <span style="color:var(--amber);font-size:10px">·traded</span>':'')+'</td>'
    +'<td>'+num(r.prob,2)+'</td><td>'+(r.result?'YES':'NO')+'</td>'
    +'<td>'+(r.correct?'<span class="res-ok">✓</span>':'<span class="res-no">✗</span>')+'</td></tr>';});
  return h+'</tbody></table></div></div>';
}
// delegated bet-type tab switch (survives re-renders)
document.addEventListener('click',e=>{
  const tab=e.target.closest&&e.target.closest('.bt-tab');
  if(tab){const card=tab.closest('.card'),bt=tab.getAttribute('data-bt');
    card.querySelectorAll('.bt-tab').forEach(t=>t.classList.toggle('on',t===tab));
    card.querySelectorAll('.bt-panel').forEach(p=>p.classList.toggle('on',p.getAttribute('data-bt')===bt));return;}
  const gh=e.target.closest&&e.target.closest('.ghead');
  if(gh){gh.parentElement.classList.toggle('open');}
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
function prettyDay(d,today){
  if(d===today)return 'Today';
  const t=Date.parse(today+'T00:00:00Z'),dd=Date.parse(d+'T00:00:00Z');
  if(!isNaN(t)&&!isNaN(dd)){const diff=Math.round((dd-t)/86400000);
    if(diff===1)return 'Tomorrow';if(diff===-1)return 'Yesterday';}
  const p=d.split('-');return (_MON[(+p[1]||1)-1]||'')+' '+(+p[2]||'');
}
// ---- day's games (from the bet board, grouped by day then matchup) ----
function boardFor(label){return STATE.board&&STATE.board[String(label).toLowerCase()];}
function boardRows(rows){
  return '<div style="max-height:340px;overflow:auto"><table><thead><tr><th>Matchup</th><th>Market</th><th>Pick</th><th>Model</th><th>Mkt</th><th>Edge</th></tr></thead><tbody>'
    +rows.map(r=>'<tr><td>'+esc(prettyMatchup(r.matchup))+'</td><td title="'+esc(r.ticker)+'">'+esc((r.ticker||'').slice(0,24))+'</td>'
      +'<td>'+(r.pick?'<span class="pill '+(String(r.pick).toLowerCase()==='no'?'no':'yes')+'">'+esc(String(r.pick).toUpperCase())+'</span>':'—')+'</td>'
      +'<td>'+num(r.probability,2)+'</td><td>'+(r.market_probability==null?'—':num(r.market_probability,2))+'</td>'
      +'<td class="'+((r.edge||0)>=0?'pos':'neg')+'">'+signed(r.edge||0,1)+'</td></tr>').join('')
    +'</tbody></table></div>';
}
function betRankCard(label){
  const grp=boardFor(label);
  const types=grp?Object.keys(grp).filter(t=>grp[t]&&grp[t].length):[];
  if(!types.length)return '';
  types.sort((a,b)=>grp[b].length-grp[a].length);
  const total=types.reduce((n,t)=>n+grp[t].length,0);
  let h='<div class="card reveal" style="margin-top:var(--s3)"><h3>All markets by category <span class="r">'+total+' priced now · every market, not just traded</span></h3>';
  h+='<div class="bt-tabs">'+types.map((t,i)=>'<button class="bt-tab'+(i===0?' on':'')+'" data-bt="'+esc(t)+'">'+esc(prettyBet(t))+'<span class="c">'+grp[t].length+'</span></button>').join('')+'</div>';
  h+='<div class="bt-panels">'+types.map((t,i)=>{const rows=[...grp[t]].sort((a,b)=>(b.edge||0)-(a.edge||0));
    return '<div class="bt-panel'+(i===0?' on':'')+'" data-bt="'+esc(t)+'">'+boardRows(rows)+'</div>';}).join('')+'</div>';
  return h+'</div>';
}
function gameBreakdown(rows){
  rows=[...rows].sort((a,b)=>Math.abs(b.edge||0)-Math.abs(a.edge||0));
  return '<table><thead><tr><th>Bet type</th><th>Market</th><th>Pick</th><th>Model</th><th>Mkt</th><th>Edge</th></tr></thead><tbody>'
    +rows.map(r=>'<tr><td>'+esc(prettyBet(r.bet_type))+'</td><td title="'+esc(r.ticker)+'">'+esc((r.ticker||'').slice(0,26))+'</td>'
      +'<td>'+(r.pick?'<span class="pill '+(String(r.pick).toLowerCase()==='no'?'no':'yes')+'">'+esc(String(r.pick).toUpperCase())+'</span>':'—')+'</td>'
      +'<td>'+num(r.probability,2)+'</td><td>'+(r.market_probability==null?'—':num(r.market_probability,2))+'</td>'
      +'<td class="'+((r.edge||0)>=0?'pos':'neg')+'">'+signed(r.edge||0,1)+'</td></tr>').join('')
    +'</tbody></table>';
}
function dayGames(rows){
  const byGame={};rows.forEach(r=>{const m=r.matchup||'?';(byGame[m]=byGame[m]||[]).push(r);});
  const games=Object.keys(byGame).sort((a,b)=>Math.max(...byGame[b].map(r=>Math.abs(r.edge||0)))-Math.max(...byGame[a].map(r=>Math.abs(r.edge||0))));
  return '<div class="games">'+games.map(m=>{const rows2=byGame[m];const be=Math.max(...rows2.map(r=>Math.abs(r.edge||0)));
    return '<div class="game"><div class="ghead"><span class="gx">▸</span><span class="gm">'+esc(prettyMatchup(m))+'</span><span class="gc">'+rows2.length+' markets</span><span class="ge">'+signed(be,1)+' best</span></div>'
      +'<div class="gbody">'+gameBreakdown(rows2)+'</div></div>';}).join('')+'</div>';
}
function gamesCard(vert,label){
  if(vert!=='SPORTS')return '';
  const grp=boardFor(label);
  if(!grp)return '';
  const all=[];Object.values(grp).forEach(rows=>rows.forEach(r=>all.push(r)));
  if(!all.length)return '';
  const byDay={};all.forEach(r=>{const d=(r.close_time||'').slice(0,10);if(d)(byDay[d]=byDay[d]||[]).push(r);});
  const days=Object.keys(byDay).sort();
  if(!days.length)return '';
  const today=new Date().toISOString().slice(0,10);
  let defIdx=days.findIndex(d=>d>=today);if(defIdx<0)defIdx=days.length-1;
  const nGames=(rows)=>{const s=new Set();rows.forEach(r=>s.add(r.matchup||'?'));return s.size;};
  let h='<div class="card reveal" style="margin-top:var(--s3)"><h3>Games — full breakdown <span class="r">pick a day, then a game</span></h3>';
  h+='<div class="bt-tabs">'+days.map((d,i)=>'<button class="bt-tab'+(i===defIdx?' on':'')+'" data-bt="day-'+d+'">'+esc(prettyDay(d,today))+'<span class="c">'+nGames(byDay[d])+'</span></button>').join('')+'</div>';
  h+='<div class="bt-panels">'+days.map((d,i)=>'<div class="bt-panel'+(i===defIdx?' on':'')+'" data-bt="day-'+d+'">'+dayGames(byDay[d])+'</div>').join('')+'</div>';
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
  if(!sc)return topbar(label,vert.toLowerCase())+'<div class="card"><div class="empty">'+esc(label)+' — no snapshot data yet.<br><span style="color:var(--faint)">the board refreshes every 20 min; leagues populate as their markets settle</span></div></div>';
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
    +miniRow('Open picks',commaN(sc.picks?sc.picks.length:0),'amb')
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
  h+='<div class="card pad0 reveal"><h3 style="padding:var(--s3) var(--s3) var(--s2)">Current picks <span class="r">by edge</span></h3>'+picksTable(sc.picks)+'</div>';
  h+='</div>';
  h+=betTypeCard(sc.bet_types);
  h+=gamesCard(vert,label);
  h+='<div class="grid cols2">'+betRankCard(label)+settledTodayCard(sc)+'</div>';
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
function topbar(title,crumb,badge){
  const stamp=STATE.overview&&STATE.overview.generated_at;
  return '<div class="topbar"><h2>'+esc(title)+'</h2><span class="crumb">'+esc(crumb)+'</span>'
    +(badge?' '+badge:'')+'<span class="spacer"></span>'
    +'<span class="stamp"><span class="beat"></span>updated '+ago(stamp)+'</span></div>';
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

// ---------- accent tube switcher ----------
const ACCENTS=[['emerald','#2fe38f'],['amber','#ffc24d'],['cyan','#6fe0ff'],['violet','#b79cff']];
function setAccent(a){document.documentElement.setAttribute('data-accent',a);try{localStorage.setItem('dummy-accent',a);}catch(_){}
  [...document.querySelectorAll('.tube')].forEach(t=>t.setAttribute('aria-pressed',String(t.dataset.a===a)));}
(function(){const box=document.getElementById('tubes');
  ACCENTS.forEach(([a,c])=>{const b=$('<button class="tube" data-a="'+a+'" title="'+a+'" aria-label="'+a+' tube" style="--c:'+c+'"></button>');
    b.addEventListener('click',()=>setAccent(a));box.appendChild(b);});
  let saved='emerald';try{saved=localStorage.getItem('dummy-accent')||'emerald';}catch(_){}
  setAccent(ACCENTS.some(x=>x[0]===saved)?saved:'emerald');})();
function cycleAccent(){const cur=document.documentElement.getAttribute('data-accent');
  const i=ACCENTS.findIndex(x=>x[0]===cur);setAccent(ACCENTS[(i+1)%ACCENTS.length][0]);}

// ---------- command palette ----------
const cmdk=document.getElementById('cmdk'),cmdq=document.getElementById('cmdq'),cmdlist=document.getElementById('cmdlist');
let cmdRoutes=[],cmdSel=0,lastFocus=null;
function cmdBuild(){
  cmdRoutes=[{icon:'overview',label:'Overview',hint:'account & ladder',href:'#/overview'}];
  const v=(STATE.scopes&&STATE.scopes.verticals)||{};
  Object.entries(v).forEach(([vert,vb])=>Object.keys(vb.scopes||{}).forEach(lab=>
    cmdRoutes.push({icon:vert==='CRYPTO'?'coin':'ball',label:lab,hint:vert.toLowerCase(),href:'#/scope/'+vert+'/'+lab})));
}
function fuzzy(q,s){q=q.toLowerCase();s=s.toLowerCase();let i=0;for(const ch of s){if(ch===q[i])i++;if(i===q.length)return true;}return q.length===0;}
function cmdRender(){
  const q=cmdq.value.trim();
  const rows=cmdRoutes.filter(r=>fuzzy(q,r.label+' '+r.hint));
  cmdSel=Math.max(0,Math.min(cmdSel,rows.length-1));
  cmdlist.innerHTML=rows.map((r,i)=>'<div class="opt'+(i===cmdSel?' sel':'')+'" data-href="'+r.href+'">'+svgIcon(r.icon)
    +'<span>'+esc(r.label)+'</span><span class="oh">'+esc(r.hint)+'</span></div>').join('')||'<div class="empty">no match</div>';
  cmdlist._rows=rows;
  const sel=cmdlist.querySelector('.opt.sel');if(sel)sel.scrollIntoView({block:'nearest'});
}
function cmdOpen(){cmdBuild();cmdSel=0;cmdq.value='';cmdRender();lastFocus=document.activeElement;
  cmdk.classList.add('open');requestAnimationFrame(()=>cmdq.focus());}
function cmdClose(){cmdk.classList.remove('open');if(lastFocus&&lastFocus.focus)lastFocus.focus();}
function cmdGo(){const rows=cmdlist._rows||[];const r=rows[cmdSel];if(r){location.hash=r.href;cmdClose();}}
cmdq.addEventListener('input',()=>{cmdSel=0;cmdRender();});
cmdlist.addEventListener('click',e=>{const o=e.target.closest('.opt');if(o&&o.dataset.href){location.hash=o.dataset.href;cmdClose();}});
document.addEventListener('keydown',e=>{
  const open=cmdk.classList.contains('open');
  if((e.key==='k'||e.key==='K')&&(e.metaKey||e.ctrlKey)){e.preventDefault();open?cmdClose():cmdOpen();return;}
  if(!open){
    const tag=(document.activeElement&&document.activeElement.tagName)||'';
    if(e.key==='/'&&tag!=='INPUT'){e.preventDefault();cmdOpen();}
    else if((e.key==='t'||e.key==='T')&&tag!=='INPUT'&&!e.metaKey&&!e.ctrlKey){cycleAccent();}
    return;
  }
  if(e.key==='Escape'){e.preventDefault();cmdClose();}
  else if(e.key==='ArrowDown'){e.preventDefault();cmdSel++;cmdRender();}
  else if(e.key==='ArrowUp'){e.preventDefault();cmdSel--;cmdRender();}
  else if(e.key==='Enter'){e.preventDefault();cmdGo();}
});
cmdk.addEventListener('click',e=>{if(e.target===cmdk)cmdClose();});

// ---------- ambient phosphor field ----------
(function(){
  const c=document.getElementById('fx');if(!c)return;const x=c.getContext('2d');
  let W=0,H=0,DPR=1,ps=[],raf=0,run=true,mx=.5,my=.4;
  const accRGB=()=>getComputedStyle(document.documentElement).getPropertyValue('--acc-rgb').trim()||'77,255,160';
  function size(){DPR=Math.min(1.6,window.devicePixelRatio||1);W=c.width=Math.floor(innerWidth*DPR);H=c.height=Math.floor(innerHeight*DPR);
    c.style.width=innerWidth+'px';c.style.height=innerHeight+'px';
    const n=Math.max(24,Math.round(innerWidth*innerHeight/26000));ps=[];
    for(let i=0;i<n;i++)ps.push({x:Math.random()*W,y:Math.random()*H,r:(Math.random()*1.5+.35)*DPR,s:(Math.random()*.26+.05)*DPR,a:Math.random()*.45+.13,d:Math.random()*6.28});}
  addEventListener('pointermove',e=>{mx=e.clientX/innerWidth;my=e.clientY/innerHeight;},{passive:true});
  function draw(t){const rgb=accRGB();x.clearRect(0,0,W,H);
    const gx=mx*W,gy=my*H,g=x.createRadialGradient(gx,gy,0,gx,gy,340*DPR);
    g.addColorStop(0,'rgba('+rgb+',.045)');g.addColorStop(1,'rgba('+rgb+',0)');x.fillStyle=g;x.fillRect(0,0,W,H);
    for(const p of ps){p.y-=p.s;p.x+=Math.sin(t*0.0004+p.d)*0.14*DPR;if(p.y<-4){p.y=H+4;p.x=Math.random()*W;}
      x.beginPath();x.arc(p.x,p.y,p.r,0,6.29);x.fillStyle='rgba('+rgb+','+p.a+')';x.fill();}
  }
  function loop(t){draw(t);if(run)raf=requestAnimationFrame(loop);}
  size();addEventListener('resize',size);
  if(REDUCE){draw(0);}   // one static frame, no loop
  else{raf=requestAnimationFrame(loop);
    document.addEventListener('visibilitychange',()=>{run=!document.hidden;if(run){raf=requestAnimationFrame(loop);}else cancelAnimationFrame(raf);});}
})();
function shock(){if(REDUCE)return;const s=document.getElementById('shock');s.classList.remove('go');void s.offsetWidth;s.classList.add('go');}

// ---------- data ----------
async function poll(){
  try{
    const [ov,sc,st,wf,bb]=await Promise.all([
      fetch('/api/overview').then(r=>r.json()).catch(()=>null),
      fetch('/api/scopes').then(r=>r.json()).catch(()=>null),
      fetch('/api/status').then(r=>r.json()).catch(()=>null),
      fetch('/api/walk_forward').then(r=>r.json()).catch(()=>null),
      fetch('/api/bet_board').then(r=>r.json()).catch(()=>null),
    ]);
    if(ov)STATE.overview=ov;if(sc)STATE.scopes=sc;if(st)STATE.status=st;
    if(wf)STATE.walk=wf.leagues||{};
    if(bb){STATE.board=bb.groups||{};buildTape();}   // tape tracks the board, independent of view re-render
    const live=document.getElementById('live'),fs=document.getElementById('footstat');
    const fresh=ov&&ov.generated_at&&(Date.now()-Date.parse(ov.generated_at))<30*60*1000;
    live.className='dot'+(fresh?' live':'');
    fs.textContent=fresh?'live · '+ago(ov.generated_at):'stale snapshot';
    // re-render (and re-flip the flaps) only when the data actually changed --
    // like a real tote board, the numbers roll when new results land.
    const sig=JSON.stringify([STATE.overview,STATE.scopes]);
    if(sig!==lastSig){const had=lastSig!=='';lastSig=sig;render();if(had)shock();}
  }catch(e){}
}
window.addEventListener('hashchange',()=>{ROUTE=location.hash||'#/overview';render();});
window.addEventListener('resize',()=>moveGlide());
render();poll();setInterval(poll,20000);
</script>
</body></html>"""
