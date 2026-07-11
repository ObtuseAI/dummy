"""Operator dashboard for the autonomy predator.

A query-only evidence view plus narrowly scoped local controls for the public
paper scheduler. The control path cannot reach the broker, live executor,
weights, risk settings, or capital authority.
"""
from __future__ import annotations

import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from starlette.requests import Request

RUNTIME_DIR = Path("runtime/autonomy")
SHADOW_TASK_NAME = "DummyShadowPredator"
TRAINER_TASK_NAME = "DummySimulationTrainer"
DASHBOARD_TASK_NAME = "DummyDashboard"


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


def session_authorization_state(runtime_dir: Path) -> dict[str, Any]:
    """Summarize the operator session authorization with explicit expiry truth.

    A LIVE session file whose ``expires_at`` has passed is the daemon's cue to
    fall back to SHADOW; surface that state loudly instead of leaving the
    operator to infer it from the heartbeat mode.
    """
    session = _load_json(runtime_dir / "session.json")
    if not isinstance(session, dict) or not session:
        return {"present": False, "mode": None, "status": "NO_SESSION_FILE"}
    expires_raw = session.get("expires_at")
    expired: bool | None = None
    seconds_remaining: float | None = None
    try:
        expires = datetime.fromisoformat(str(expires_raw).replace("Z", "+00:00"))
        if expires.tzinfo is not None:
            remaining = (expires - datetime.now(timezone.utc)).total_seconds()
            seconds_remaining = round(remaining, 1)
            expired = remaining <= 0
    except (TypeError, ValueError):
        pass
    mode = str(session.get("mode") or "").upper() or None
    if mode == "LIVE" and expired:
        status = "LIVE_AUTHORIZATION_EXPIRED"
    elif mode == "LIVE" and expired is False:
        status = "LIVE_AUTHORIZED"
    elif mode:
        status = mode
    else:
        status = "UNKNOWN"
    return {
        "present": True,
        "mode": mode,
        "operator": session.get("operator"),
        "started_at": session.get("started_at"),
        "expires_at": expires_raw,
        "expired": expired,
        "seconds_remaining": seconds_remaining,
        "limit_orders_only": bool(session.get("limit_orders_only")),
        "status": status,
    }


def assemble_dashboard_state(runtime_dir: Path | None = None) -> dict[str, Any]:
    """Assemble the full read-only dashboard state (pure)."""
    rd = runtime_dir or RUNTIME_DIR
    heartbeat = _load_json(rd / "heartbeat.json") or {"alive": False}
    cycles = _tail_jsonl(rd / "cycles.jsonl", 30)
    alerts = _tail_jsonl(rd / "alerts.jsonl", 20)
    risk_state = _load_json(rd / "risk_state.json")
    simulation_training = _load_json(rd / "simulation_training_latest.json") or {}
    crypto_paper_twin = _load_json(rd / "crypto_paper_twin_latest.json") or {}
    from autonomy.paper_dashboard import assemble_paper_dashboard, scheduled_task_status
    from autonomy.sports.dashboard import SPORTS_TASK_NAME, assemble_sports_dashboard

    paper_operation = assemble_paper_dashboard(rd)
    sports_operation = assemble_sports_dashboard(rd)

    def _task_status(task_name: str) -> dict[str, Any]:
        if runtime_dir is None:
            return scheduled_task_status(task_name)
        return {
            "task_name": task_name,
            "supported": False,
            "enabled": False,
            "state": "ALTERNATE_RUNTIME",
            "healthy": False,
        }

    paper_scheduler = _task_status("DummyCryptoPaperTwin")
    sports_scheduler = _task_status(SPORTS_TASK_NAME)
    scheduler_fleet = [
        {"role": "shadow predator", **_task_status(SHADOW_TASK_NAME)},
        {"role": "crypto paper twin", **paper_scheduler},
        {"role": "sports paper twin", **sports_scheduler},
        {"role": "simulation trainer", **_task_status(TRAINER_TASK_NAME)},
        {"role": "dashboard", **_task_status(DASHBOARD_TASK_NAME)},
    ]
    session = session_authorization_state(rd)

    ledger_summary: dict[str, Any] = {}
    statistics_intake: dict[str, Any] = {}
    canary: dict[str, Any] = {}
    backtest: dict[str, Any] = {}
    try:
        from autonomy.backtest import run_backtest
        from autonomy.canary import evaluate_canary_readiness
        from autonomy.ledger import AutonomyLedger

        ledger = AutonomyLedger(db_path=rd / "ledger.db")
        try:
            ledger_summary = ledger.performance_summary()
            statistics_intake = ledger.external_observation_summary()
            backtest = run_backtest(ledger, bootstrap_weights=False)
            canary = evaluate_canary_readiness(
                ledger, backtest_report=backtest,
            ).to_dict()
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
            "contested_n": s.get("contested_n"),
            "contested_beat_rate": s.get("contested_beat_rate"),
            "contested_edge_lower": (
                (s.get("contested_mean_brier_edge_ci95") or {}).get("lower")
            ),
            "calibration_error": s.get("expected_calibration_error"),
            "weight": (backtest.get("derived_weights") or {}).get(source),
        })
    scoreboard.sort(key=lambda r: (r["beat_market_rate"] or 0), reverse=True)

    return {
        "heartbeat": heartbeat,
        "session": session,
        "scheduler_fleet": scheduler_fleet,
        "risk_state": risk_state,
        "ledger": ledger_summary,
        "canary": canary,
        "scoreboard": scoreboard,
        "settled_markets": backtest.get("settled_markets", 0),
        "realized_shadow_pnl_cents": backtest.get("realized_decision_pnl_cents", 0),
        "decision_policy": backtest.get("decision_policy", {}),
        "fill_conditioned_policy": backtest.get("fill_conditioned_decision_policy", {}),
        "shadow_ttl_sensitivity": backtest.get("shadow_ttl_sensitivity", {}),
        "crypto_diagnostics": backtest.get("crypto_diagnostics", {}),
        "crypto_challenger_gates": backtest.get("crypto_challenger_gates", {}),
        "signal_data_quality": backtest.get("signal_data_quality", {}),
        "statistics_intake": statistics_intake,
        "simulation_training": simulation_training,
        "crypto_paper_twin": crypto_paper_twin,
        "paper_operation": paper_operation,
        "paper_scheduler": paper_scheduler,
        "sports_operation": sports_operation,
        "sports_scheduler": sports_scheduler,
        "execution_quality": (
            (backtest.get("execution_quality_by_book") or {}).get("shadow", {})
        ),
        "execution_drift": (
            (backtest.get("execution_drift_by_book") or {}).get("shadow", {})
        ),
        "scale_readiness": (canary.get("evidence") or {}).get("scale_readiness", {}),
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
 :root{color-scheme:dark;--bg:#080b11;--panel:#101620;--panel2:#151d29;--line:#243041;--text:#e6edf3;--muted:#8b98a8;--blue:#58a6ff;--green:#3fb950;--amber:#d29922;--red:#f85149}
 *{box-sizing:border-box} body{font-family:Inter,ui-sans-serif,system-ui,-apple-system,Segoe UI,sans-serif;background:radial-gradient(circle at 15% -10%,#14233a 0,transparent 35%),var(--bg);color:var(--text);margin:0;padding:24px;max-width:1800px;margin-inline:auto}
 h1{color:var(--text);font-size:22px;margin:0 0 4px;letter-spacing:-.4px} .sub{color:var(--muted);font-size:12px;margin-bottom:16px}
 .topbar{display:flex;align-items:flex-start;justify-content:space-between;gap:18px;margin-bottom:18px}.eyebrow{font-size:10px;letter-spacing:1.4px;text-transform:uppercase;color:var(--blue);font-weight:800}.controls{display:flex;align-items:center;gap:8px;flex-wrap:wrap;justify-content:flex-end}.btn{border:1px solid var(--line);border-radius:8px;padding:9px 14px;background:#172131;color:var(--text);font-weight:750;cursor:pointer}.btn:hover{border-color:var(--blue)}.btn.start{background:#12331f;border-color:#245f38;color:#78dc91}.btn.stop{background:#35191b;border-color:#713034;color:#ff8b91}.btn:disabled{opacity:.45;cursor:wait}
 .hero{display:grid;grid-template-columns:repeat(auto-fit,minmax(170px,1fr));gap:10px;margin-bottom:14px}.metric{background:linear-gradient(145deg,var(--panel2),#0e141d);border:1px solid var(--line);border-radius:10px;padding:13px}.metric .label{text-transform:uppercase;letter-spacing:.7px;color:var(--muted);font-size:10px;font-weight:750}.metric .value{font-size:24px;font-weight:800;margin-top:5px}.metric .note{font-size:10px;color:var(--muted);margin-top:3px}
 .grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(260px,1fr));gap:14px}
 .card{background:linear-gradient(145deg,var(--panel),#0d121a);border:1px solid var(--line);border-radius:10px;padding:14px;overflow:hidden}
 .card h2{font-size:11px;text-transform:uppercase;letter-spacing:.8px;color:var(--muted);margin:0 0 10px}
 .kv{display:flex;justify-content:space-between;font-size:13px;padding:2px 0}
 .kv b{color:#e6edf3} .ok{color:#3fb950} .warn{color:#d29922} .bad{color:#f85149}
 table{width:100%;border-collapse:collapse;font-size:12px} td,th{text-align:left;padding:7px 8px;border-bottom:1px solid #21262d;vertical-align:top}
 th{color:#8b949e;font-weight:600} .pill{padding:1px 7px;border-radius:10px;font-size:11px}
 .live{background:#0d3b1e;color:#3fb950} .dead{background:#3b0d0d;color:#f85149}
 .paper-grid{display:grid;grid-template-columns:1.1fr .9fr;gap:14px;margin-bottom:14px}.span{grid-column:1/-1}.table-wrap{overflow:auto;max-height:420px}.explain{max-width:520px;color:#b7c2cf;line-height:1.35}.muted{color:var(--muted)}.bar{height:7px;background:#202a37;border-radius:5px;overflow:hidden;margin:5px 0 10px}.bar>i{display:block;height:100%;background:linear-gradient(90deg,var(--blue),#7ee787);border-radius:5px}.chart{width:100%;height:170px}.control-msg{min-height:16px;color:var(--muted);font-size:11px}.section-title{font-size:14px;margin:22px 0 10px}.truth{border-left:3px solid var(--amber);padding:8px 10px;background:#211b10;color:#d7c8a0;font-size:11px;margin-top:10px}
 .banner{display:none;border-radius:10px;padding:11px 14px;margin-bottom:14px;font-size:13px;font-weight:700;border:1px solid var(--line)}
 .banner.show{display:block}.banner.bad{background:#2d1113;border-color:#713034;color:#ff9ba0}.banner.warn{background:#2a2109;border-color:#6b5518;color:#e8c76c}.banner.ok{background:#0e2a18;border-color:#245f38;color:#7ee787}.banner.muted{background:#141b26;color:var(--muted)}
 @media(max-width:900px){body{padding:14px}.topbar{display:block}.controls{justify-content:flex-start;margin-top:12px}.paper-grid{grid-template-columns:1fr}}
</style></head><body>
<div class="topbar"><div><div class="eyebrow">Evidence-gated operations</div><h1>DUMMY // paper trading command center</h1><div class="sub" id="ts">loading…</div></div>
<div class="controls"><span id="schedulerBadge" class="pill dead">CHECKING</span><button id="startBtn" class="btn start" onclick="controlPaper('start')">Start paper twin</button><button id="stopBtn" class="btn stop" onclick="controlPaper('stop')">Stop after cycle</button><div id="controlMsg" class="control-msg"></div></div></div>
<div id="authBanner" class="banner"></div>
<div class="hero">
 <div class="metric"><div class="label">Scheduler</div><div class="value" id="mScheduler">—</div><div class="note" id="mNext">Windows task</div></div>
 <div class="metric"><div class="label">Active paper trades</div><div class="value" id="mOpen">—</div><div class="note" id="mRisk">quote-simulated positions</div></div>
 <div class="metric"><div class="label">Settled paper trades</div><div class="value" id="mSettled">—</div><div class="note" id="mWin">forward ledger</div></div>
 <div class="metric"><div class="label">Quote-simulated P&amp;L</div><div class="value" id="mPnl">—</div><div class="note">not witnessed-fill P&amp;L</div></div>
 <div class="metric"><div class="label">Target evidence</div><div class="value" id="mTargets">—</div><div class="note" id="mClusters">settled candidates</div></div>
 <div class="metric"><div class="label">Forced crypto papers</div><div class="value" id="mForcedOpen">—</div><div class="note" id="mForcedSettled">coverage-probe lane</div></div>
 <div class="metric"><div class="label">Crypto scopes covered</div><div class="value" id="mForcedCoverage">—</div><div class="note" id="mForcedCoverageNote">of 12 designated scopes</div></div>
 <div class="metric"><div class="label">Promotion state</div><div class="value warn" id="mPromotion">HOLD</div><div class="note">explicit review required</div></div>
</div>
<div class="paper-grid">
 <div class="card"><h2>Cumulative quote-simulated P&amp;L</h2><div id="pnlChart"></div><div class="truth">Unrealized P&amp;L is intentionally blank without a fresh executable mark. Quote entries and public-print maker witnesses remain research evidence, not live-fill proof.</div></div>
 <div class="card"><h2>Forward evidence progress</h2><div id="progress"></div></div>
 <div class="card span"><h2>Active paper trades</h2><div id="activeTrades" class="table-wrap"></div></div>
 <div class="card span"><h2>Lane performance</h2><div id="lanePerformance" class="table-wrap"></div></div>
 <div class="card span"><h2>Forced crypto target coverage</h2><div id="cryptoCoverage" class="table-wrap"></div></div>
 <div class="card span"><h2>Active forced crypto papers</h2><div id="cryptoCoverageTrades" class="table-wrap"></div></div>
 <div class="card"><h2>Recent decisions and explanations</h2><div id="paperDecisions" class="table-wrap"></div></div>
 <div class="card"><h2>Weakness and improvement queue</h2><div id="paperWeaknesses" class="table-wrap"></div></div>
</div>
<div class="section-title">Sports forced-coverage paper twin</div>
<div class="topbar"><div><div class="eyebrow">Every designated prediction type</div><div class="sub">Real listed markets only · forced diagnostic trades never count toward promotion</div></div>
<div class="controls"><span id="sportsSchedulerBadge" class="pill dead">CHECKING</span><button id="sportsStartBtn" class="btn start" onclick="controlSports('start')">Start sports twin</button><button id="sportsStopBtn" class="btn stop" onclick="controlSports('stop')">Stop sports after cycle</button><div id="sportsControlMsg" class="control-msg"></div></div></div>
<div class="hero">
 <div class="metric"><div class="label">Sports scheduler</div><div class="value" id="sScheduler">—</div><div class="note" id="sNext">Windows task</div></div>
 <div class="metric"><div class="label">Active sports papers</div><div class="value" id="sOpen">—</div><div class="note">policy + coverage-probe lanes</div></div>
 <div class="metric"><div class="label">Settled sports papers</div><div class="value" id="sSettled">—</div><div class="note" id="sWin">forward outcomes</div></div>
 <div class="metric"><div class="label">Sports paper P&amp;L</div><div class="value" id="sPnl">—</div><div class="note">one-contract quote simulation</div></div>
 <div class="metric"><div class="label">Types without gaps</div><div class="value" id="sCoverage">—</div><div class="note" id="sCoverageNote">of 17 designated types</div></div>
 <div class="metric"><div class="label">Promotion use</div><div class="value warn">EXCLUDED</div><div class="note">forced lane is diagnostic only</div></div>
</div>
<div class="paper-grid">
 <div class="card span"><h2>Designated prediction-type coverage</h2><div id="sportsCoverage" class="table-wrap"></div></div>
 <div class="card span"><h2>Active forced and policy sports papers</h2><div id="sportsTrades" class="table-wrap"></div></div>
 <div class="card"><h2>Sports lane results</h2><div id="sportsLanes" class="table-wrap"></div></div>
 <div class="card"><h2>Recent sports explanations</h2><div id="sportsExplanations" class="table-wrap"></div></div>
</div>
<div class="section-title">Autonomy evidence and risk detail</div>
<div class="grid">
 <div class="card"><h2>Session authorization</h2><div id="session"></div></div>
 <div class="card"><h2>Scheduler fleet</h2><div id="fleet"></div></div>
 <div class="card"><h2>Liveness</h2><div id="live"></div></div>
 <div class="card"><h2>Live canary gate</h2><div id="canary"></div></div>
 <div class="card"><h2>Risk</h2><div id="risk"></div></div>
 <div class="card"><h2>Forecast validation</h2><div id="validation"></div></div>
 <div class="card"><h2>Online drift</h2><div id="drift"></div></div>
 <div class="card"><h2>Execution / scale</h2><div id="execution"></div></div>
 <div class="card"><h2>Signal intake</h2><div id="quality"></div></div>
 <div class="card"><h2>Statistics intake</h2><div id="statistics"></div></div>
 <div class="card"><h2>Simulation training</h2><div id="training"></div></div>
 <div class="card"><h2>Recursive evolution lab</h2><div id="evolution"></div></div>
 <div class="card"><h2>Always-on market paper twin</h2><div id="paper"></div></div>
 <div class="card"><h2>Crypto execution truth</h2><div id="crypto"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Source scoreboard</h2><div id="board"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Recent cycles</h2><div id="cycles"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Alerts</h2><div id="alerts"></div></div>
</div>
<script>
const kv=(k,v,c)=>`<div class="kv"><span>${k}</span><b class="${c||''}">${v}</b></div>`;
const pct=v=>v==null?'—':(100*Number(v)).toFixed(1)+'%';
const esc=v=>String(v??'—').replace(/[&<>"']/g,c=>({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const cents=v=>v==null?'—':`${Number(v)>=0?'+':''}$${(Number(v)/100).toFixed(2)}`;
const dt=v=>{if(!v)return '—';const x=new Date(v);return isNaN(x)?esc(v):x.toLocaleString([], {month:'short',day:'numeric',hour:'numeric',minute:'2-digit'});};
const bar=(label,value,target)=>{const n=Number(value||0),t=Math.max(1,Number(target||1)),w=Math.min(100,100*n/t);return `<div class="kv"><span>${esc(label)}</span><b>${n} / ${t}</b></div><div class="bar"><i style="width:${w}%"></i></div>`;};
function pnlChart(rows){
 if(!rows.length)return '<div class="muted">No settled paper trades yet.</div>';
 const values=rows.map(r=>Number(r.pnl_cents||0)), min=Math.min(0,...values), max=Math.max(0,...values), span=Math.max(1,max-min), w=720,h=150,p=12;
 const points=values.map((v,i)=>`${p+(w-2*p)*(i/Math.max(1,values.length-1))},${p+(h-2*p)*(1-(v-min)/span)}`).join(' ');
 const zero=p+(h-2*p)*(1-(0-min)/span),last=values[values.length-1];
 return `<svg class="chart" viewBox="0 0 ${w} ${h}" preserveAspectRatio="none"><line x1="${p}" y1="${zero}" x2="${w-p}" y2="${zero}" stroke="#334155" stroke-dasharray="4 4"/><polyline fill="none" stroke="${last>=0?'#3fb950':'#f85149'}" stroke-width="3" points="${points}"/></svg><div class="kv"><span>range</span><b>${cents(min)} to ${cents(max)}</b></div>`;
}
function renderScheduler(s){
 const enabled=!!s.enabled,healthy=!!s.healthy;
 document.getElementById('schedulerBadge').className=`pill ${enabled&&healthy?'live':'dead'}`;
 document.getElementById('schedulerBadge').textContent=enabled?(s.running?'RUNNING':healthy?'SCHEDULED':'DEGRADED'):'STOPPED';
 document.getElementById('mScheduler').textContent=enabled?(s.running?'RUNNING':'ON'):'OFF';
 document.getElementById('mScheduler').className=`value ${enabled&&healthy?'ok':'bad'}`;
 document.getElementById('mNext').textContent=`next ${dt(s.next_run_time)} · result ${s.last_result??'—'}`;
 document.getElementById('startBtn').disabled=!!s.running;
 document.getElementById('stopBtn').disabled=!enabled;
}
function renderPaper(d){
 const op=d.paper_operation||{},m=op.metrics||{},s=d.paper_scheduler||{},latest=op.latest_cycle||{},tc=op.target_candidate_counts||{};
 const forced=op.forced_crypto_coverage||{},forcedSummary=forced.summary||{};
 renderScheduler(s);
 document.getElementById('mOpen').textContent=m.open_trades??0;
 document.getElementById('mRisk').textContent=`${cents(m.open_paper_cost_cents)} paper cost at risk`;
 document.getElementById('mSettled').textContent=m.settled_trades??0;
 document.getElementById('mWin').textContent=`${pct(m.win_rate)} quote-simulated win rate`;
 document.getElementById('mPnl').textContent=cents(m.quote_simulated_net_pnl_cents);
 document.getElementById('mPnl').className=`value ${Number(m.quote_simulated_net_pnl_cents||0)>=0?'ok':'bad'}`;
 document.getElementById('mTargets').textContent=tc.settled_forecasts??0;
 document.getElementById('mClusters').textContent=`${tc.settled_event_clusters??0} event clusters · ${tc.forecasts??0} captured`;
 document.getElementById('mForcedOpen').textContent=forcedSummary.open_decisions??0;
 document.getElementById('mForcedSettled').textContent=`${forcedSummary.settled_decisions??0} settled · ${cents(forcedSummary.net_pnl_cents)} P&L`;
 document.getElementById('mForcedCoverage').textContent=forced.scopes_observed_this_cycle??0;
 document.getElementById('mForcedCoverageNote').textContent=`of ${forced.designated_scopes??12} scopes · ${forced.coverage_gap_count??0} gaps`;
 const hp=((op.hourly_calibration||{}).profile)||{}, auth=op.authority||{};
 const promotion=(auth.execution_authority||auth.capital_authority)?'AUTHORITY ERROR':(hp.status==='ACTIVE_FORWARD_CALIBRATION'?'REVIEW':'HOLD');
 document.getElementById('mPromotion').textContent=promotion;
 document.getElementById('mPromotion').className=`value ${promotion==='REVIEW'?'ok':promotion==='AUTHORITY ERROR'?'bad':'warn'}`;
 document.getElementById('pnlChart').innerHTML=pnlChart(op.pnl_curve||[]);
 const rule=(op.hourly_calibration||{}).activation_rule||{};
 document.getElementById('progress').innerHTML=
   kv('latest cycle', latest.status||'—',latest.status==='CYCLE_OK'?'ok':'warn')+kv('freshness',op.freshness_seconds==null?'—':Math.round(op.freshness_seconds)+' sec')
   +bar('hourly settled forecasts',hp.settled_forecasts,rule.minimum_settled_forecasts||20)
   +bar('hourly event clusters',hp.event_clusters,rule.minimum_event_clusters||10)
   +bar('walk-forward forecasts',hp.walk_forward_forecasts,rule.minimum_walk_forward_forecasts||10)
   +kv('Brier advantage lower 95%',(hp.walk_forward_advantage_ci95||{}).lower??'—')
   +kv('model share',pct(hp.model_share))+kv('authority','paper only','warn');
 const active=op.active_trades||[];
 document.getElementById('activeTrades').innerHTML=active.length?'<table><tr><th>closes</th><th>asset / horizon</th><th>target</th><th>side</th><th>entry</th><th>model / market</th><th>edge / EV</th><th>maker witness</th><th>decision</th></tr>'
   +active.map(t=>`<tr><td>${dt(t.close_time)}</td><td><b>${esc(t.asset)} ${esc(t.timeframe)}</b><br><span class="muted">${esc(t.strategy)}</span></td><td>${esc((t.target||{}).label||t.ticker)}</td><td>${esc(t.side)}</td><td>${t.entry_price_cents}¢ + ${t.fee_cents}¢</td><td>${pct(t.probability_yes)} / ${pct(t.market_probability)}</td><td>${Number(t.edge_cents||0).toFixed(2)}¢ / ${Number(t.conservative_ev_cents||0).toFixed(2)}¢</td><td>${esc(t.maker_status)}</td><td class="explain">${esc(t.explanation)}</td></tr>`).join('')+'</table>':'<div class="muted">No open paper trades. The engine is scanning and may abstain when no target clears policy.</div>';
 const allLanes=op.lanes||[];
 const lanes=allLanes.filter(x=>Number(x.trades||0)>0||Number(x.settled_trades||0)>0);
 const silent=allLanes.filter(x=>!(Number(x.trades||0)>0||Number(x.settled_trades||0)>0)).map(x=>`${x.vertical}·${x.timeframe}·${x.strategy}`);
 const silentNote=silent.length?`<div class="muted" style="margin-top:8px">never traded (abstain-only so far): ${silent.map(esc).join(', ')}</div>`:'';
 document.getElementById('lanePerformance').innerHTML=(lanes.length?'<table><tr><th>lane</th><th>trades</th><th>settled</th><th>wins</th><th>quote P&amp;L</th><th>Brier skill</th><th>maker fills</th><th>maker P&amp;L</th><th>drawdown</th></tr>'
   +lanes.map(x=>`<tr><td>${esc(x.vertical)} · ${esc(x.timeframe)} · ${esc(x.strategy)}</td><td>${x.trades??0}</td><td>${x.settled_trades??0}</td><td>${x.wins??0}</td><td class="${Number(x.net_pnl_cents||0)>=0?'ok':'bad'}">${cents(x.net_pnl_cents)}</td><td>${pct(x.brier_skill_vs_market)}</td><td>${x.maker_fills??0} / ${x.maker_orders??0}</td><td>${cents(x.maker_net_pnl_cents)}</td><td>${cents(-(Number(x.max_drawdown_cents||0)))}</td></tr>`).join('')+'</table>':'<div class="muted">No lane evidence yet.</div>')+silentNote;
 const coverageMatrix=forced.matrix||[];
 document.getElementById('cryptoCoverage').innerHTML=coverageMatrix.length?'<table><tr><th>asset</th><th>horizon</th><th>status</th><th>targets now</th><th>new forced</th><th>open</th><th>settled</th><th>P&amp;L</th><th>explanation</th></tr>'
   +coverageMatrix.map(x=>`<tr><td><b>${esc(x.asset)}</b></td><td>${esc(x.timeframe)}</td><td class="${x.is_coverage_gap?'warn':'ok'}">${esc(x.status)}</td><td>${x.targets_observed_this_cycle??0}</td><td>${x.forced_trades_recorded_this_cycle??0}</td><td>${x.open_decisions??0}</td><td>${x.settled_decisions??0}</td><td>${cents(x.net_pnl_cents)}</td><td class="explain">${esc(x.explanation)}</td></tr>`).join('')+'</table>':'<div class="muted">Waiting for the first forced crypto coverage cycle.</div>';
 const coverageTrades=forced.active_trades||[];
 document.getElementById('cryptoCoverageTrades').innerHTML=coverageTrades.length?'<table><tr><th>closes</th><th>asset / horizon</th><th>target</th><th>side</th><th>entry</th><th>model / market</th><th>EV</th><th>normal-policy status</th><th>explanation</th></tr>'
   +coverageTrades.map(x=>`<tr><td>${dt(x.close_time)}</td><td><b>${esc(x.asset)} ${esc(x.timeframe)}</b><br><span class="muted">coverage_probe</span></td><td>${esc((x.target||{}).label||x.ticker)}</td><td>${esc(String(x.side||'').toUpperCase())}</td><td>${x.entry_price_cents}¢ + ${x.fee_cents}¢</td><td>${pct(x.probability_yes)} / ${pct(x.market_probability)}</td><td>${Number(x.conservative_ev_cents||0).toFixed(2)}¢</td><td class="${x.normal_policy_eligible?'ok':'warn'}">${esc(x.normal_policy_reason)}</td><td class="explain">${esc(x.explanation)}</td></tr>`).join('')+'</table>':'<div class="muted">No open forced crypto papers. Coverage gaps remain explicit when no real quoted target exists.</div>';
 const decisions=op.recent_decisions||[];
 document.getElementById('paperDecisions').innerHTML=decisions.length?decisions.slice(0,12).map(x=>`<div style="padding:8px 0;border-bottom:1px solid #243041"><div><b>${esc(x.asset)} ${esc(x.timeframe)} · ${esc(x.action)}</b> <span class="muted">${dt(x.created_at)}</span></div><div class="explain">${esc(x.explanation)}</div></div>`).join(''):'<div class="muted">No decisions recorded.</div>';
 const weak=op.weaknesses||[];
 document.getElementById('paperWeaknesses').innerHTML=weak.length?weak.slice(0,12).map(x=>`<div style="padding:8px 0;border-bottom:1px solid #243041"><b class="warn">${esc(x.component)}</b><div class="explain">${esc(x.reason)}</div><span class="muted">${x.observations!=null?esc(x.observations)+' observations':''}${x.net_pnl_cents!=null?' · '+cents(x.net_pnl_cents):''}</span></div>`).join(''):'<div class="muted">No current weaknesses reported.</div>';
}
function renderSportsScheduler(s){
 const enabled=!!s.enabled,healthy=!!s.healthy;
 document.getElementById('sportsSchedulerBadge').className=`pill ${enabled&&healthy?'live':'dead'}`;
 document.getElementById('sportsSchedulerBadge').textContent=enabled?(s.running?'RUNNING':healthy?'SCHEDULED':'DEGRADED'):'STOPPED';
 document.getElementById('sScheduler').textContent=enabled?(s.running?'RUNNING':'ON'):'OFF';
 document.getElementById('sScheduler').className=`value ${enabled&&healthy?'ok':'bad'}`;
 document.getElementById('sNext').textContent=`next ${dt(s.next_run_time)} · result ${s.last_result??'—'}`;
 document.getElementById('sportsStartBtn').disabled=!!s.running;
 document.getElementById('sportsStopBtn').disabled=!enabled;
}
function renderSports(d){
 const op=d.sports_operation||{},m=op.metrics||{},coverage=op.coverage||{},s=d.sports_scheduler||{};
 renderSportsScheduler(s);
 document.getElementById('sOpen').textContent=m.open_trades??0;
 document.getElementById('sSettled').textContent=m.settled_trades??0;
 document.getElementById('sWin').textContent=`${pct(m.win_rate)} quote-simulated win rate`;
 document.getElementById('sPnl').textContent=cents(m.net_pnl_cents);
 document.getElementById('sPnl').className=`value ${Number(m.net_pnl_cents||0)>=0?'ok':'bad'}`;
 document.getElementById('sCoverage').textContent=coverage.types_covered_without_gap??coverage.types_observed_this_cycle??0;
 document.getElementById('sCoverageNote').textContent=`${coverage.coverage_gap_count??0} explicit gaps · ${coverage.types_observed_this_cycle??0} types observed`;
 const matrix=coverage.matrix||[];
 document.getElementById('sportsCoverage').innerHTML=matrix.length?'<table><tr><th>sport</th><th>prediction type</th><th>status</th><th>markets now</th><th>forced now</th><th>tracked</th><th>explanation</th></tr>'
   +matrix.map(x=>`<tr><td>${esc(String(x.sport||'').toUpperCase())}</td><td>${esc(x.market_type)}</td><td class="${x.is_coverage_gap===false||(!('is_coverage_gap' in x)&&x.status==='TRACKING_FORCED_PAPER')?'ok':'warn'}">${esc(x.status)}</td><td>${x.markets_observed_this_cycle??0}</td><td>${x.forced_trades_recorded_this_cycle??0}</td><td>${x.tracked_forced_trades??0}</td><td class="explain">${esc(x.explanation)}</td></tr>`).join('')+'</table>':'<div class="muted">Waiting for the first forced-coverage sports cycle.</div>';
 const trades=op.active_trades||[];
 document.getElementById('sportsTrades').innerHTML=trades.length?'<table><tr><th>event</th><th>sport / type</th><th>lane</th><th>side</th><th>entry</th><th>model / market</th><th>EV</th><th>decision explanation</th></tr>'
   +trades.map(x=>`<tr><td>${dt(x.event_start)}</td><td><b>${esc(String(x.sport||'').toUpperCase())}</b><br><span class="muted">${esc(x.market_type)}</span></td><td class="${x.lane==='coverage_probe'?'warn':'ok'}">${esc(x.lane)}</td><td>${esc(String(x.side||'').toUpperCase())}</td><td>${x.price_cents}¢ + ${x.fee_cents}¢</td><td>${pct(x.model_probability)} / ${pct(x.market_probability)}</td><td>${Number(x.conservative_ev_cents||0).toFixed(2)}¢</td><td class="explain">${esc(x.explanation)}</td></tr>`).join('')+'</table>':'<div class="muted">No active sports paper trades yet.</div>';
 const lanes=op.lane_summary||[];
 document.getElementById('sportsLanes').innerHTML=lanes.length?'<table><tr><th>lane / scope</th><th>paper</th><th>settled</th><th>wins</th><th>P&amp;L</th></tr>'
   +lanes.map(x=>`<tr><td>${esc(x.lane)} · ${esc(String(x.sport||'').toUpperCase())} ${esc(x.market_type)}</td><td>${x.decisions??0}</td><td>${x.settled_decisions??0}</td><td>${x.wins??0}</td><td class="${Number(x.pnl_cents||0)>=0?'ok':'bad'}">${cents(x.pnl_cents)}</td></tr>`).join('')+'</table>':'<div class="muted">No settled sports lane evidence yet.</div>';
 const explanations=[...(op.active_trades||[]),...(op.recent_settlements||[])];
 document.getElementById('sportsExplanations').innerHTML=explanations.length?explanations.slice(0,12).map(x=>`<div style="padding:8px 0;border-bottom:1px solid #243041"><div><b>${esc(String(x.sport||'').toUpperCase())} ${esc(x.market_type)} · ${esc(x.lane)}</b> <span class="muted">${dt(x.observed_at)}</span></div><div class="explain">${esc(x.explanation)}</div></div>`).join(''):'<div class="muted">Waiting for explained sports paper decisions.</div>';
}
const remain=s=>{if(s==null)return '—';const v=Math.abs(Number(s)),h=Math.floor(v/3600),m=Math.floor((v%3600)/60);return (Number(s)<0?'-':'')+(h?h+'h ':'')+m+'m';};
function renderSession(s,hb){
 const banner=document.getElementById('authBanner');
 let cls='muted',text='';
 if(s.status==='LIVE_AUTHORIZATION_EXPIRED'){cls='bad';text=`LIVE authorization EXPIRED ${dt(s.expires_at)} (${remain(s.seconds_remaining)} ago). Daemon fail-closed to SHADOW. Re-run start --live --ack to re-authorize.`;}
 else if(s.status==='LIVE_AUTHORIZED'){const warn=Number(s.seconds_remaining||0)<7200;cls=warn?'warn':'ok';text=`LIVE authorized by ${esc(s.operator||'operator')} · expires ${dt(s.expires_at)} (${remain(s.seconds_remaining)} left)${s.limit_orders_only?' · LIMIT only':''}${warn?' · EXPIRING SOON':''}`;}
 else if(s.present){cls='muted';text=`Session mode ${esc(s.mode||s.status)} · no live authorization active.`;}
 else{cls='muted';text='No session file. Daemon runs SHADOW only until an operator authorizes live.';}
 banner.className='banner show '+cls; banner.textContent=text;
 const modeMismatch=s.status==='LIVE_AUTHORIZED'&&hb.mode&&hb.mode!=='LIVE';
 document.getElementById('session').innerHTML=
   kv('status',esc(s.status||'—'),s.status==='LIVE_AUTHORIZED'?'ok':s.status==='LIVE_AUTHORIZATION_EXPIRED'?'bad':'warn')
   +kv('operator',esc(s.operator||'—'))+kv('started',dt(s.started_at))+kv('expires',dt(s.expires_at))
   +kv('remaining',s.expired?'expired '+remain(s.seconds_remaining)+' ago':remain(s.seconds_remaining),s.expired?'bad':'ok')
   +kv('limit orders only',s.limit_orders_only?'yes':'—')
   +kv('daemon mode',esc(hb.mode||'—'),modeMismatch?'warn':'')
   +(modeMismatch?'<div class="kv"><span class="warn">!</span><span>daemon has not picked up the live session yet</span></div>':'');
}
function renderFleet(fleet){
 document.getElementById('fleet').innerHTML=fleet.length?fleet.map(t=>{
  const enabled=!!t.enabled,healthy=!!t.healthy;
  const badge=t.state==='ALTERNATE_RUNTIME'?'—':enabled?(t.running?'RUNNING':healthy?'READY':'DEGRADED'):'STOPPED';
  return `<div class="kv"><span>${esc(t.role)}</span><b><span class="pill ${enabled&&healthy?'live':'dead'}">${badge}</span> <span class="muted">${dt(t.next_run_time)}</span></b></div>`;
 }).join(''):'<div class="muted">No scheduler telemetry.</div>';
}
let tickGeneration=0;
async function controlPaper(action){
 const msg=document.getElementById('controlMsg'),buttons=[document.getElementById('startBtn'),document.getElementById('stopBtn')];buttons.forEach(x=>x.disabled=true);msg.textContent=action==='start'?'Starting paper scheduler…':'Pausing future cycles…';
 try{const r=await fetch('/api/paper-scheduler/'+action,{method:'POST',headers:{'X-Dummy-Paper-Control':'paper-twin-scheduler-v1'}});const v=await r.json();msg.textContent=v.message||v.detail||v.error||'Control completed';tickGeneration++;if(v.scheduler)renderScheduler(v.scheduler);tick();}catch(e){msg.textContent='Control request failed';}finally{setTimeout(()=>{msg.textContent='';},6000);}
}
async function controlSports(action){
 const msg=document.getElementById('sportsControlMsg'),buttons=[document.getElementById('sportsStartBtn'),document.getElementById('sportsStopBtn')];buttons.forEach(x=>x.disabled=true);msg.textContent=action==='start'?'Starting sports scheduler…':'Pausing future sports cycles…';
 try{const r=await fetch('/api/sports-paper-scheduler/'+action,{method:'POST',headers:{'X-Dummy-Paper-Control':'paper-twin-scheduler-v1'}});const v=await r.json();msg.textContent=v.message||v.detail||v.error||'Control completed';tickGeneration++;if(v.scheduler)renderSportsScheduler(v.scheduler);tick();}catch(e){msg.textContent='Sports control request failed';}finally{setTimeout(()=>{msg.textContent='';},6000);}
}
async function tick(){
 const generation=++tickGeneration;
 let d; try{ d=await (await fetch('/api/autonomy')).json(); }catch(e){ document.getElementById('ts').textContent='backend unreachable'; return; }
 if(generation!==tickGeneration)return;
 document.getElementById('ts').textContent='updated '+new Date().toLocaleTimeString();
 try{renderPaper(d);renderSports(d);}catch(e){document.getElementById('ts').textContent+=' · paper render error: '+e.message;console.error('paper render',e);}
 renderSession(d.session||{},d.heartbeat||{});
 renderFleet(d.scheduler_fleet||[]);
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
 const p=d.decision_policy||{}, em=p.ensemble_metrics||{}, ca=p.cluster_robust_advantage||{}, cb=ca.brier||{};
 const fc=d.fill_conditioned_policy||{};
 const wf=(p.walk_forward_threshold_selection||{}).aggregate_out_of_sample||{};
 const dr=p.online_forecast_drift||{}, dd=dr.latest_detection||{};
 document.getElementById('validation').innerHTML =
   kv('decision snapshots', p.settled_markets??0)+kv('event clusters', p.event_clusters??0)
   +kv('Brier skill vs market', pct(em.brier_skill_vs_market))
   +kv('cluster Brier CI lower', cb.lower??'—', (cb.lower||0)>0?'ok':'bad')
   +kv('calibration error', pct(em.expected_calibration_error))
   +kv('filled/settled forecasts', fc.n??0)
   +kv('fill-conditioned skill', pct(fc.brier_skill_vs_market), (fc.brier_skill_vs_market||0)>0?'ok':'bad')
   +kv('walk-forward trades', wf.trades??0)+kv('walk-forward ROI', pct(wf.roi_on_entry_cost), (wf.roi_on_entry_cost||0)>0?'ok':'bad');
 document.getElementById('drift').innerHTML =
   kv('ADWIN available', dr.available?'yes':'no')+kv('observations', dr.observations??0)
   +kv('change detected', dr.drift_detected?'YES':'no', dr.drift_detected?'warn':'ok')
   +kv('negative drift', dr.negative_drift?'<b class="bad">YES</b>':'no')
   +kv('latest local change', dd.change??'—');
 const ex=d.execution_quality||{}, sr=d.scale_readiness||{};
 const ed=d.execution_drift||{};
 const ttl5=(((d.shadow_ttl_sensitivity||{}).thresholds||[]).find(x=>x.ttl_minutes===5))||{};
 document.getElementById('execution').innerHTML =
   kv('confirmed fills', (ex.orders_with_confirmed_fill??0)+' / '+(ex.orders_submitted??0))
   +kv('order fill rate', pct(ex.observed_fill_rate))+kv('contract fill rate', pct(ex.contract_fill_rate))
   +kv('fill CI95 lower', pct((ex.observed_fill_rate_ci95||{}).lower))
   +kv('resolved orders', (ex.orders_with_known_outcome??0)+' / '+(ex.orders_submitted??0))
   +kv('fill degradation', ed.negative_drift?'<b class="bad">YES</b>':'no')
   +kv('5m retained fills', ttl5.witnessed_fills_retained??'—')
   +kv('precise witnesses', pct((ex.fill_witness_quality||{}).precise_witness_rate))
   +kv('median fill seconds', ex.median_seconds_to_first_fill??'—')
   +kv('scale ready', sr.ready?'<b class="ok">YES</b>':'<b class="warn">NO</b>')
   +(sr.blockers||[]).map(b=>`<div class="kv"><span class="bad">✗</span><span>${b}</span></div>`).join('');
 const q=d.signal_data_quality||{};
 document.getElementById('quality').innerHTML =
   kv('status', q.status||'—', q.status==='PASS'?'ok':q.status==='FAIL'?'bad':'warn')
   +kv('signals stored', q.signals_stored??0)+kv('feature payload rows', q.feature_payload_rows??0)
   +kv('quarantined', q.quarantined_attempts??0)+kv('decision gaps', q.decisions_without_prior_signal??0)
   +(q.blocking_issues||[]).map(b=>`<div class="kv"><span class="bad">✗</span><span>${b}</span></div>`).join('')
   +(q.warnings||[]).slice(0,2).map(b=>`<div class="kv"><span class="warn">!</span><span>${b}</span></div>`).join('');
 const st=d.statistics_intake||{}, sts=st.sources||{};
 document.getElementById('statistics').innerHTML =
   kv('raw observations', st.total_observations??0)
   +Object.entries(sts).map(([name,v])=>kv(name, v.observations??0)).join('');
 const tr=d.simulation_training||{}, tro=tr.forecast_oos||{}, tre=tr.execution_overall||{};
 document.getElementById('training').innerHTML =
   kv('forecast challenger', tr.forecast_status||'—', tr.forecast_status==='SHADOW_EXPERIMENT_ELIGIBLE'?'ok':'warn')
   +kv('execution challenger', tr.execution_status||'—', tr.execution_status==='SHADOW_EXPERIMENT_ELIGIBLE'?'ok':'warn')
   +kv('OOS trades', tro.trades??0)+kv('OOS ROI', pct(tro.roi_on_entry_cost))
   +kv('settled execution fills', tre.settled_fills??0)
   +kv('stress-safe fraction', tr.highest_stress_safe_fraction==null?'none':pct(tr.highest_stress_safe_fraction))
   +kv('execution authority', tr.execution_authority?'<b class="bad">YES</b>':'none');
 const el=tr.evolution_lab||{}, ee=el.evidence||{}, ep=el.population||{};
 const ea=el.active_research_candidate||{}, ef=el.forward_ratchet||{};
 const efs=ef.candidate||{}, exr=tr.execution_trace_replay||{};
 const iq=tr.improvement_queue||{}, iqi=iq.items||[];
 document.getElementById('evolution').innerHTML =
   kv('status', el.status||'—', el.status==='READY_FOR_EXPLICIT_SHADOW_REVIEW'?'ok':'warn')
   +kv('generation', el.generation??0)+kv('new settled evidence', ee.new_settled_markets??0)
   +kv('candidate population', ep.candidates_generated??0)
   +kv('causal folds', ep.folds_completed??0)
   +kv('active genome', ea.genome_id||'—')
   +kv('forward trades', efs.trades??0)+kv('forward clusters', efs.event_clusters??0)
   +kv('forward net P&L¢', efs.net_pnl_cents??0, (efs.net_pnl_cents||0)>0?'ok':'bad')
   +kv('trace-settled fills', exr.settled_fills??0)
   +kv('weaknesses queued', iqi.length)
   +kv('top priority', (iqi[0]||{}).component||'none')
   +kv('capital authority', ((el.authority||{}).capital_authority)?'<b class="bad">YES</b>':'none');
 const pt=d.crypto_paper_twin||{}, ptc=pt.cohorts||{}, ptl=ptc.CRYPTO||pt.lanes||{};
 const ptm=ptc.COMMODITIES||{};
 const p15i=(ptl['15m']||{}).incumbent||{}, p15e=(ptl['15m']||{}).exploratory||{};
 const p1i=(ptl['1h']||{}).incumbent||{}, p1e=(ptl['1h']||{}).exploratory||{};
 const pdi=(ptl['1d']||{}).incumbent||{}, pde=(ptl['1d']||{}).exploratory||{};
 const pwi=(ptl['1w']||{}).incumbent||{}, pwe=(ptl['1w']||{}).exploratory||{};
 const mdi=(ptm['1d']||{}).incumbent||{}, mde=(ptm['1d']||{}).exploratory||{};
 const mwi=(ptm['1w']||{}).incumbent||{}, mwe=(ptm['1w']||{}).exploratory||{};
 const pta=pt.authority||{};
 document.getElementById('paper').innerHTML =
   kv('status', pt.status||'—', pt.status==='CYCLE_OK'?'ok':'warn')
   +kv('last cycle', pt.completed_at||'—')+kv('markets observed', pt.markets_seen??0)
   +kv('15m incumbent settled', p15i.settled_trades??0)
   +kv('15m exploratory P&L¢', p15e.net_pnl_cents??0, (p15e.net_pnl_cents||0)>0?'ok':'bad')
   +kv('1h incumbent settled', p1i.settled_trades??0)
   +kv('1h exploratory P&L¢', p1e.net_pnl_cents??0, (p1e.net_pnl_cents||0)>0?'ok':'bad')
   +kv('crypto 1d / 1w settled', (pdi.settled_trades??0)+' / '+(pwi.settled_trades??0))
   +kv('crypto 1d / 1w P&L¢', (pde.net_pnl_cents??0)+' / '+(pwe.net_pnl_cents??0))
   +kv('commodity 1d / 1w settled', (mdi.settled_trades??0)+' / '+(mwi.settled_trades??0))
   +kv('commodity 1d / 1w P&L¢', (mde.net_pnl_cents??0)+' / '+(mwe.net_pnl_cents??0))
   +kv('always beside live', pta.continues_during_authorized_live_operation?'yes':'—')
   +kv('broker contacted', pta.broker_contacted?'<b class="bad">YES</b>':'no')
   +kv('capital authority', pta.capital_authority?'<b class="bad">YES</b>':'none');
 const cx=d.crypto_diagnostics||{}, cg=cx.guard_counterfactual||{}, cf=cx.source_family_overlap||{};
  const cgs=d.crypto_challenger_gates||{};
 document.getElementById('crypto').innerHTML =
   kv('filled/settled', cx.filled_settled_decisions??0)
   +kv('net P&L¢', cx.net_pnl_cents??0, (cx.net_pnl_cents||0)>0?'ok':'bad')
   +kv('ensemble Brier', cx.ensemble_brier??'—')+kv('market Brier', cx.market_brier??'—')
   +kv('model-family correlation', cf.pearson_probability_correlation??'—')
   +kv('guard retained fills', cg.witnessed_fills_retained??'—')
   +kv('guard retained P&L¢', cg.settled_net_pnl_cents??'—')
    +kv('repeat markets blocked', cg.repeated_market_orders_blocked??0)
    +Object.entries(cgs).map(([name,g])=>
      kv(name.replace('crypto_',''), g.ready_for_explicit_fusion_review?'REVIEW READY':'QUARANTINED', g.ready_for_explicit_fusion_review?'ok':'warn')
      +kv(name.replace('crypto_','')+' live settled', (g.evidence||{}).live_settled_markets??0)
    ).join('');
 document.getElementById('board').innerHTML =
   '<table><tr><th>source</th><th>n</th><th>Brier</th><th>ECE</th><th>contested n</th><th>contested beat</th><th>edge CI low</th><th>weight</th></tr>'
   +(d.scoreboard||[]).map(s=>`<tr><td>${s.source}</td><td>${s.n??'—'}</td><td>${s.mean_brier??'—'}</td><td>${s.calibration_error??'—'}</td><td>${s.contested_n??'—'}</td><td>${s.contested_beat_rate??'—'}</td><td>${s.contested_edge_lower??'—'}</td><td>${s.weight??'—'}</td></tr>`).join('')+'</table>';
 document.getElementById('cycles').innerHTML =
   '<table><tr><th>at</th><th>status</th><th>mkts</th><th>signals</th><th>rejected</th><th>orders</th><th>settle</th></tr>'
   +(d.recent_cycles||[]).slice().reverse().map(c=>`<tr><td>${(c.at||'').slice(11,19)}</td><td>${c.status||''}</td><td>${c.markets_scanned??''}</td><td>${c.signals_generated??''}</td><td>${c.signals_rejected??0}</td><td>${c.orders_placed??''}</td><td>${c.settlements??''}</td></tr>`).join('')+'</table>';
 document.getElementById('alerts').innerHTML =
   (d.alerts||[]).slice().reverse().map(a=>`<div class="kv"><span class="${a.severity=='critical'?'bad':a.severity=='warning'?'warn':'ok'}">${a.kind}</span><span>${a.message}</span><b>${(a.at||'').slice(11,19)}</b></div>`).join('') || '<div class="sub">no alerts</div>';
}
tick(); setInterval(tick, 15000);
</script></body></html>"""


def build_app():
    """Construct the evidence dashboard and paper-scheduler control surface."""
    from fastapi import FastAPI, HTTPException
    from fastapi.responses import HTMLResponse, JSONResponse
    from autonomy.paper_dashboard import (
        PAPER_CONTROL_HEADER,
        control_paper_scheduler,
        scheduled_task_status,
    )
    from autonomy.sports.dashboard import SPORTS_TASK_NAME

    app = FastAPI(title="Dummy Autonomy Dashboard")
    # The report includes a 1,000-resample cluster bootstrap over a large
    # ledger. A 30-second cache keeps 15-second browser polling read-only and
    # responsive without repeatedly burning CPU between ten-minute cycles.
    state_cache: dict[str, Any] = {"at": 0.0, "value": None, "epoch": 0}

    @app.get("/api/autonomy")
    def api_state() -> JSONResponse:
        now = time.monotonic()
        if state_cache["value"] is None or now - float(state_cache["at"]) >= 30.0:
            epoch = int(state_cache["epoch"])
            assembled = assemble_dashboard_state()
            # A control action can invalidate the cache while this expensive
            # report is assembling. Never let that stale request overwrite
            # the post-control scheduler state.
            if epoch == int(state_cache["epoch"]):
                state_cache["value"] = assembled
                state_cache["at"] = now
            return JSONResponse(assembled)
        return JSONResponse(state_cache["value"])

    def _scheduler_control(
        action: str, request: Request, task_name: str | None = None
    ) -> JSONResponse:
        """Shared paper-scheduler control: CSRF header + loopback origin, fixed task.

        ``task_name=None`` targets the default crypto paper task and keeps the
        one-argument call contract the paper endpoint has always had.
        """
        if request.headers.get("x-dummy-paper-control") != PAPER_CONTROL_HEADER:
            raise HTTPException(status_code=403, detail="paper control header required")
        origin = request.headers.get("origin")
        if origin and urlparse(origin).hostname not in {"127.0.0.1", "localhost", "::1"}:
            raise HTTPException(status_code=403, detail="loopback origin required")
        try:
            if task_name is None:
                result = control_paper_scheduler(action)
            else:
                result = control_paper_scheduler(action, task_name=task_name)
        except ValueError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from exc
        state_cache["epoch"] = int(state_cache["epoch"]) + 1
        state_cache["at"] = 0.0
        state_cache["value"] = None
        result["scheduler"] = (
            scheduled_task_status() if task_name is None else scheduled_task_status(task_name)
        )
        return JSONResponse(result, status_code=200 if result.get("ok") else 503)

    @app.post("/api/paper-scheduler/{action}")
    def paper_scheduler_control(action: str, request: Request) -> JSONResponse:
        return _scheduler_control(action, request)

    @app.post("/api/sports-paper-scheduler/{action}")
    def sports_paper_scheduler_control(action: str, request: Request) -> JSONResponse:
        return _scheduler_control(action, request, SPORTS_TASK_NAME)

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(_HTML)

    return app
