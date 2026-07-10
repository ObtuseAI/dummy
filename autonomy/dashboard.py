"""Operator dashboard for the autonomy predator.

A read-only view over everything the operator needs to watch an unattended
run: liveness (heartbeat), recent cycles, source calibration (backtest),
live-canary readiness, trust weights, bankroll curve, and alerts. The state
assembler is pure and testable; a tiny FastAPI app serves it plus a
self-contained HTML page that polls it.
"""
from __future__ import annotations

import json
import time
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
    simulation_training = _load_json(rd / "simulation_training_latest.json") or {}

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
 <div class="card"><h2>Forecast validation</h2><div id="validation"></div></div>
 <div class="card"><h2>Online drift</h2><div id="drift"></div></div>
 <div class="card"><h2>Execution / scale</h2><div id="execution"></div></div>
 <div class="card"><h2>Signal intake</h2><div id="quality"></div></div>
 <div class="card"><h2>Statistics intake</h2><div id="statistics"></div></div>
 <div class="card"><h2>Simulation training</h2><div id="training"></div></div>
 <div class="card"><h2>Recursive evolution lab</h2><div id="evolution"></div></div>
 <div class="card"><h2>Crypto execution truth</h2><div id="crypto"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Source scoreboard</h2><div id="board"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Recent cycles</h2><div id="cycles"></div></div>
 <div class="card" style="grid-column:1/-1"><h2>Alerts</h2><div id="alerts"></div></div>
</div>
<script>
const kv=(k,v,c)=>`<div class="kv"><span>${k}</span><b class="${c||''}">${v}</b></div>`;
const pct=v=>v==null?'—':(100*Number(v)).toFixed(1)+'%';
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
    """Construct the read-only FastAPI dashboard app."""
    from fastapi import FastAPI
    from fastapi.responses import HTMLResponse, JSONResponse

    app = FastAPI(title="Dummy Autonomy Dashboard")
    # The report includes a 1,000-resample cluster bootstrap over a large
    # ledger. A 30-second cache keeps 15-second browser polling read-only and
    # responsive without repeatedly burning CPU between ten-minute cycles.
    state_cache: dict[str, Any] = {"at": 0.0, "value": None}

    @app.get("/api/autonomy")
    def api_state() -> JSONResponse:
        now = time.monotonic()
        if state_cache["value"] is None or now - float(state_cache["at"]) >= 30.0:
            state_cache["value"] = assemble_dashboard_state()
            state_cache["at"] = now
        return JSONResponse(state_cache["value"])

    @app.get("/")
    def index() -> HTMLResponse:
        return HTMLResponse(_HTML)

    return app
