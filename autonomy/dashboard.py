"""Operator dashboard for the autonomy predator.

A read-only view over everything the operator needs to watch an unattended
run: liveness (heartbeat), recent cycles, source calibration (backtest),
live-canary readiness, trust weights, bankroll curve, and alerts. The state
assembler is pure and testable; a tiny FastAPI app serves it plus a
self-contained HTML page that polls it.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path("runtime/autonomy")


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _tail_jsonl(path: Path, limit: int) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    try:
        lines = path.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out


def assemble_dashboard_state(runtime_dir: Path | None = None) -> dict[str, Any]:
    """Assemble the full read-only dashboard state (pure)."""
    rd = runtime_dir or RUNTIME_DIR
    heartbeat = _load_json(rd / "heartbeat.json") or {"alive": False}
    cycles = _tail_jsonl(rd / "cycles.jsonl", 30)
    alerts = _tail_jsonl(rd / "alerts.jsonl", 20)
    risk_state = _load_json(rd / "risk_state.json")

    ledger_summary: dict[str, Any] = {}
    canary: dict[str, Any] = {}
    backtest: dict[str, Any] = {}
    try:
        from autonomy.backtest import run_backtest
        from autonomy.canary import evaluate_canary_readiness
        from autonomy.ledger import AutonomyLedger

        ledger = AutonomyLedger(db_path=rd / "ledger.db")
        try:
            ledger_summary = ledger.performance_summary()
            backtest = run_backtest(ledger, bootstrap_weights=False)
            canary = evaluate_canary_readiness(ledger).to_dict()
        finally:
            ledger.close()
    except Exception as exc:
        ledger_summary = {"error": f"{type(exc).__name__}"}

    # Compress the backtest to a per-source scoreboard for the UI.
    scoreboard = []
    for source, s in (backtest.get("sources") or {}).items():
        scoreboard.append({
            "source": source,
            "n": s.get("n"),
            "mean_brier": s.get("mean_brier"),
            "beat_market_rate": s.get("beat_market_rate"),
            "weight": (backtest.get("derived_weights") or {}).get(source),
        })
    scoreboard.sort(key=lambda r: (r["beat_market_rate"] or 0), reverse=True)

    return {
        "heartbeat": heartbeat,
        "risk_state": risk_state,
        "ledger": ledger_summary,
        "canary": canary,
        "scoreboard": scoreboard,
        "settled_markets": backtest.get("settled_markets", 0),
        "realized_shadow_pnl_cents": backtest.get("realized_decision_pnl_cents", 0),
        "recent_cycles": cycles[-10:],
        "bankroll_curve": [
            {"at": c.get("at"), "bankroll": c.get("bankroll_cents"), "stage": c.get("stage")}
            for c in cycles if c.get("bankroll_cents") is not None
        ][-30:],
        "alerts": alerts,
    }


_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Dummy Predator</title>
<style>
 body{font-family:ui-monospace,Menlo,Consolas,monospace;background:#0b0e14;color:#c9d1d9;margin:0;padding:20px}
 h1{color:#58a6ff;font-size:18px;margin:0 0 4px} .sub{color:#6e7681;font-size:12px;margin-bottom:16px}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
 .card{background:#11161f;border:1px solid #21262d;border-radius:8px;padding:14px}
 .card h2{font-size:12px;text-transform:uppercase;letter-spacing:.5px;color:#8b949e;margin:0 0 10px}
 .kv{display:flex;justify-content:space-between;font-size:13px;padding:2px 0}
 .kv b{color:#e6edf3} .ok{color:#3fb950} .warn{color:#d29922} .bad{color:#f85149}
 table{width:100%;border-collapse:collapse;font-size:12px} td,th{text-align:left;padding:3px 6px;border-bottom:1px solid #21262d}
 th{color:#8b949e;font-weight:600} .pill{padding:1px 7px;border-radius:10px;font-size:11px}
 .live{background:#0d3b1e;color:#3fb950} .dead{background:#3b0d0d;color:#f85149}
</style></head><body>
<h1>DUMMY // autonomous prediction-market predator</h1>
<div class="sub" id="ts">loading…</div>
<div class="grid">
 <div class="card"><h2>Liveness</h2><div id="live"></div></div>
 <div class="card"><h2>Live canary gate</h2><div id="canary"></div></div>
 <div class="card"><h2>Risk</h2><div id="risk"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Source scoreboard</h2><div id="board"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Recent cycles</h2><div id="cycles"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Alerts</h2><div id="alerts"></div></div>
</div>
<script>
const kv=(k,v,c)=>`<div class="kv"><span>${k}</span><b class="${c||''}">${v}</b></div>`;
async function tick(){
 let d; try{ d=await (await fetch('/api/autonomy')).json(); }catch(e){ document.getElementById('ts').textContent='backend unreachable'; return; }
 document.getElementById('ts').textContent='updated '+new Date().toLocaleTimeString();
 const hb=d.heartbeat||{};
 document.getElementById('live').innerHTML =
   kv('status', `<span class="pill ${hb.alive?'live':'dead'}">${hb.alive?'ALIVE':'STALE'}</span>`)
   +kv('last cycle', hb.last_cycle_at||'—')+kv('last status', hb.last_status||'—')
   +kv('mode', hb.mode||'—')+kv('orders', hb.last_orders_placed??'—')+kv('signals', hb.last_signals??'—');
 const c=d.canary||{};
 document.getElementById('canary').innerHTML =
   kv('ready', c.ready?'<b class="ok">YES</b>':'<b class="warn">NO</b>')
   +kv('settled', (d.settled_markets||0)+' / 20')
   +(c.blockers||[]).map(b=>`<div class="kv"><span class="bad">✗</span><span>${b}</span></div>`).join('');
 const r=d.risk_state||{};
 document.getElementById('risk').innerHTML =
   kv('stage', r.stage??'—')+kv('bankroll¢', r.bankroll_cents??'—')
   +kv('open exposure¢', r.open_exposure_cents??'—')+kv('open markets', r.open_markets??'—')
   +kv('hard stopped', r.hard_stopped?'<b class="bad">YES</b>':'no')
   +kv('shadow P&L¢', d.realized_shadow_pnl_cents??0);
 document.getElementById('board').innerHTML =
   '<table><tr><th>source</th><th>n</th><th>Brier</th><th>beat mkt</th><th>weight</th></tr>'
   +(d.scoreboard||[]).map(s=>`<tr><td>${s.source}</td><td>${s.n??'—'}</td><td>${s.mean_brier??'—'}</td><td>${s.beat_market_rate??'—'}</td><td>${s.weight??'—'}</td></tr>`).join('')+'</table>';
 document.getElementById('cycles').innerHTML =
   '<table><tr><th>at</th><th>status</th><th>mkts</th><th>signals</th><th>orders</th><th>settle</th></tr>'
   +(d.recent_cycles||[]).slice().reverse().map(c=>`<tr><td>${(c.at||'').slice(11,19)}</td><td>${c.status||''}</td><td>${c.markets_scanned??''}</td><td>${c.signals_generated??''}</td><td>${c.orders_placed??''}</td><td>${c.settlements??''}</td></tr>`).join('')+'</table>';
 document.getElementById('alerts').innerHTML =
   (d.alerts||[]).slice().reverse().map(a=>`<div class="kv"><span class="${a.severity=='critical'?'bad':a.severity=='warning'?'warn':'ok'}">${a.kind}</span><span>${a.message}</span><b>${(a.at||'').slice(11,19)}</b></div>`).join('') || '<div class="sub">no alerts</div>';
}
tick(); setInterval(tick, 15000);
</script></body></html>"""


def build_app():
    """Construct the read-only FastAPI dashboard app."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse

    app = FastAPI(title="Dummy Autonomy Dashboard")

    @app.get("/api/autonomy")
    def api_state() -> JSONResponse:
        return JSONResponse(assemble_dashboard_state())

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(_HTML)

    return app
