"""Operator dashboard for the autonomy predator.

A query-only evidence view plus narrowly scoped local controls for the public
paper scheduler. The control path cannot reach the broker, live executor,
weights, risk settings, or capital authority.
"""
from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

from starlette.requests import Request

from autonomy.dashboard_ui import DASHBOARD_HTML

RUNTIME_DIR = Path("runtime/autonomy")
# Indirection so tests can drive the cache clock without patching the global
# time module (which the test event loop also uses).
_monotonic = time.monotonic
SHADOW_TASK_NAME = "DummyShadowPredator"
TRAINER_TASK_NAME = "DummySimulationTrainer"
DASHBOARD_TASK_NAME = "DummyDashboard"
MISPRICING_TASK_NAME = "DummyMispricingMonitor"


def _load_json(path: Path) -> Any:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _to_epoch(value: Any) -> float | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    try:
        text = str(value).strip()
        if not text:
            return None
        parsed = datetime.fromisoformat(text.replace("Z", "+00:00"))
        if parsed.tzinfo is None:
            parsed = parsed.replace(tzinfo=timezone.utc)
        return parsed.timestamp()
    except (TypeError, ValueError):
        return None


def _age_seconds(value: Any, now_epoch: float) -> float | None:
    """Age in seconds of an ISO/epoch timestamp, or None if unparseable."""
    epoch = _to_epoch(value)
    return None if epoch is None else round(now_epoch - epoch, 1)


def _first_timestamp(data: Any, fields: tuple[str, ...]) -> Any:
    if isinstance(data, dict):
        for name in fields:
            if data.get(name) is not None:
                return data.get(name)
    return None


# Panel artifact -> the timestamp field that stamps its freshness. Used to
# annotate every data panel with an explicit age so stale data reads as stale.
_FRESHNESS_FIELDS: dict[str, tuple[str, ...]] = {
    "heartbeat": ("last_cycle_at",),
    "mispricing_monitor": ("generated_at",),
    "crypto_paper_twin": ("completed_at", "started_at"),
    "sports_simulation": ("completed_at", "started_at"),
    "simulation_training": ("created_at",),
    "readiness_report": ("generated_at",),
    "council_snapshot": ("generated_at",),
    "clv_report": ("generated_at",),
    "execution_tournament": ("generated_at",),
}

# Cadence-derived staleness threshold (seconds) per panel, mirroring
# autonomy/watchdog.py (2x the task cadence). A panel older than this is stale.
_FRESHNESS_THRESHOLDS: dict[str, float] = {
    "heartbeat": 1200,
    "mispricing_monitor": 240,
    "crypto_paper_twin": 600,
    "sports_simulation": 1200,
    "simulation_training": 7200,
    "readiness_report": 172800,
    "council_snapshot": 240,
    "clv_report": 172800,
    # Tournament refreshes with the backtest cycle; 2x a generous daily cadence.
    "execution_tournament": 172800,
}


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


def _bleeding_by_specialist(loss_attribution: dict[str, Any]) -> dict[str, dict[str, Any]]:
    """WS-B: the single worst bleeding grading scope per specialist, from
    ``runtime/autonomy/loss_attribution.json``. Fail-closed: absent/malformed
    artifact or no bleeding scopes -> {} (the council panel then shows no
    "where we bleed" line for anyone, never a fabricated one)."""
    worst: dict[str, dict[str, Any]] = {}
    for entry in (loss_attribution or {}).get("scopes") or []:
        if not isinstance(entry, dict) or entry.get("verdict") != "bleeding":
            continue
        scope = str(entry.get("scope") or "")
        specialist = scope.split("|", 1)[0]
        if not specialist:
            continue
        edge = entry.get("cluster_edge")
        if edge is None:
            continue
        current = worst.get(specialist)
        if current is None or float(edge) < float(current.get("cluster_edge") or 0.0):
            worst[specialist] = entry
    return worst


def _council_panel(
    council_snapshot: dict[str, Any],
    season_state: dict[str, Any],
    backtest: dict[str, Any],
    clv_report: dict[str, Any],
    loss_attribution: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    """Roll up one dashboard row per specialist (WS-13, read-only view).

    ``council_snapshot`` (runtime/autonomy/council_snapshot.json) supplies
    the live-registry fields the dashboard process can't compute itself
    (status, in_season from a team-league specialist's own health(), games
    seen, open opportunities this pass) -- see autonomy/council_snapshot.py
    for the writer contract. Everything else comes from artifacts the
    dashboard already loads: ``season_state`` (runtime/autonomy/
    season_state.json, the SAME persisted file SeasonMonitor.snapshot()
    would return, read directly since this process holds no live monitor)
    fills in in_season for specialists whose health() doesn't stamp it
    (e.g. MLB); ``backtest["trust_surface_by_specialist"]`` (WS-8's
    taxonomy-keyed contested-Brier surface, already computed in
    assemble_dashboard_state) is summed across its market_type/phase buckets
    per specialist; ``clv_report["scopes"]`` (WS-8 CLV, already loaded) is
    entries-weighted across market types per specialist.

    Fail-closed: no council_snapshot -> no rows (empty panel, never a
    crash); any datum this function can't resolve for a row is left None,
    rendered as "-" by the UI, never fabricated.
    """
    specialists = (council_snapshot or {}).get("specialists") or []
    if not specialists:
        return []

    trust_by_specialist: dict[str, dict[str, Any]] = {}
    for bucket in (backtest.get("trust_surface_by_specialist") or {}).values():
        name = (bucket or {}).get("specialist")
        if not name:
            continue
        agg = trust_by_specialist.setdefault(name, {"n": 0, "contested_n": 0, "brier_weighted": 0.0})
        n = int(bucket.get("n") or 0)
        contested_n = int(bucket.get("contested_n") or 0)
        agg["n"] += n
        agg["contested_n"] += contested_n
        if bucket.get("mean_brier") is not None and contested_n:
            agg["brier_weighted"] += contested_n * float(bucket["mean_brier"])

    clv_by_specialist: dict[str, dict[str, Any]] = {}
    for scope in (clv_report.get("scopes") or {}).values():
        name = (scope or {}).get("specialist")
        if not name or scope.get("clv_bps_mean") is None:
            continue
        agg = clv_by_specialist.setdefault(name, {"n_entries": 0, "bps_weighted": 0.0})
        n_entries = int(scope.get("n_entries") or 0)
        agg["n_entries"] += n_entries
        agg["bps_weighted"] += n_entries * float(scope["clv_bps_mean"])

    # WS-B: worst bleeding grading scope per specialist, from the loss
    # engine's read-only artifact. Fail-closed to {} -> no line for anyone.
    bleeding = _bleeding_by_specialist(loss_attribution or {})

    rows: list[dict[str, Any]] = []
    for entry in specialists:
        name = entry.get("name")
        details = entry.get("details") or {}
        in_season = details.get("in_season")
        if in_season is None:
            season_entry = season_state.get(name) if isinstance(season_state, dict) else None
            if isinstance(season_entry, dict):
                in_season = season_entry.get("active")
        games_seen = details.get("games_seen")
        if games_seen is None:
            games_seen = details.get("score_games_seen")
        trust = trust_by_specialist.get(name) or {}
        contested_n = int(trust.get("contested_n") or 0)
        contested_brier = (
            round(trust["brier_weighted"] / contested_n, 4)
            if contested_n and trust.get("brier_weighted") is not None else None
        )
        clv = clv_by_specialist.get(name) or {}
        clv_entries = int(clv.get("n_entries") or 0)
        clv_bps = round(clv["bps_weighted"] / clv_entries, 1) if clv_entries else None
        bleed = bleeding.get(name)
        where_we_bleed = (
            f"{bleed['scope']} edge {bleed['cluster_edge']} ({bleed['n_clusters']} clusters)"
            if bleed else None
        )
        rows.append({
            "name": name,
            "status": entry.get("status"),
            "in_season": in_season,
            "games_seen": games_seen,
            "settled_n": trust.get("n") or 0,
            "contested_n": contested_n,
            "contested_brier": contested_brier,
            "clv_bps": clv_bps,
            "where_we_bleed": where_we_bleed,
            "open_opportunities": entry.get("open_opportunities", 0),
        })
    return rows


def _sports_clv_summary(clv_report: dict[str, Any]) -> dict[str, Any]:
    """Compact sports-CLV rollup for the status payload (Wave-2 D1).

    Surfaces, per sports specialist, the graded ``market_type`` scopes and
    their CI-lower sign -- the exact evidence that lowers a sports scope's
    auto-promotion cluster bar from 450 (no CLV) to 300 (CLV present) and
    that the ladder's ``clv_ci95_lower > 0`` criterion consumes. Read-only,
    fail-closed to an empty rollup when the report has no sports scopes.
    """
    from autonomy.sports_clv import SPORTS_SPECIALISTS

    by_specialist: dict[str, list[dict[str, Any]]] = {}
    positive = 0
    for key, scope in (clv_report.get("scopes") or {}).items():
        if not isinstance(scope, dict):
            continue
        name = scope.get("specialist")
        if name not in SPORTS_SPECIALISTS:
            continue
        lower = scope.get("clv_bps_ci95_lower")
        if lower is not None and float(lower) > 0.0:
            positive += 1
        by_specialist.setdefault(name, []).append({
            "scope": key,
            "market_type": scope.get("market_type"),
            "clv_bps_mean": scope.get("clv_bps_mean"),
            "clv_bps_ci95_lower": lower,
            "n_entries": scope.get("n_entries"),
            "n_event_clusters": scope.get("n_event_clusters"),
        })
    scope_count = sum(len(v) for v in by_specialist.values())
    return {
        "instrumented": scope_count > 0,
        "n_scopes": scope_count,
        "n_scopes_ci_lower_positive": positive,
        "specialists": sorted(by_specialist),
        "by_specialist": by_specialist,
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
    mispricing_monitor = _load_json(rd / "mispricing_monitor_latest.json") or {}
    clv_report = _load_json(rd / "clv_report.json") or {}
    # WS-13: council panel inputs. council_snapshot.json is written by the
    # mispricing monitor's live SpecialistRegistry each pass (autonomy/
    # council_snapshot.py); season_state.json is the SAME file
    # SeasonMonitor.snapshot() would return, read directly since this
    # process holds no live monitor. Both fail-closed to {} when absent.
    council_snapshot = _load_json(rd / "council_snapshot.json") or {}
    season_state = _load_json(rd / "season_state.json") or {}
    # WS-B: loss-deconstruction evolution engine artifact (read-only,
    # fail-closed to {} when absent -- see autonomy/loss_engine.py).
    loss_attribution = _load_json(rd / "loss_attribution.json") or {}
    # Autonomous thresholded promotion (owner directive 2026-07-16): the daily
    # engine's state artifact -- promotions/escalations/demotions/aborts with
    # hash-chain refs. Read-only, fail-closed to {} when absent.
    auto_promotion = _load_json(rd / "auto_promotion_state.json") or {}
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
        {"role": "mispricing monitor", **_task_status(MISPRICING_TASK_NAME)},
        {"role": "dashboard", **_task_status(DASHBOARD_TASK_NAME)},
    ]
    session = session_authorization_state(rd)

    ledger_summary: dict[str, Any] = {}
    statistics_intake: dict[str, Any] = {}
    canary: dict[str, Any] = {}
    backtest: dict[str, Any] = {}
    if os.environ.get("DUMMY_DASHBOARD_LIVE_LEDGER", "0") == "1":
        # Opt-in only. The full backtest holds a SHARED lock over ~10M rows for
        # minutes, which blocks the shadow brain's commit ("database is locked").
        # Default reads the persisted snapshot instead — see dashboard_snapshot.py.
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
    else:
        from autonomy.dashboard_snapshot import read_dashboard_snapshot

        snap = read_dashboard_snapshot(rd / "latest_dashboard_snapshot.json")
        if snap:
            ledger_summary = snap.get("ledger_summary") or {}
            statistics_intake = snap.get("statistics_intake") or {}
            backtest = snap.get("backtest") or {}
            canary = snap.get("canary") or {}
        else:
            ledger_summary = {"note": "dashboard snapshot pending (written by daemon recalibration)"}

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

    try:
        council = _council_panel(
            council_snapshot, season_state, backtest, clv_report, loss_attribution,
        )
    except Exception:
        council = []  # fail-closed: a malformed snapshot must never break the dashboard

    now_epoch = datetime.now(timezone.utc).timestamp()
    sports_simulation = _load_json(rd / "sports_simulation_latest.json") or {}
    watchdog_status = _load_json(rd / "watchdog_status.json") or {}
    panel_sources = {
        "heartbeat": heartbeat,
        "mispricing_monitor": mispricing_monitor,
        "crypto_paper_twin": crypto_paper_twin,
        "sports_simulation": sports_simulation,
        "simulation_training": simulation_training,
        "readiness_report": _load_json(rd / "readiness_report.json") or {},
        "council_snapshot": council_snapshot,
        "clv_report": clv_report,
    }
    data_ages: dict[str, Any] = {}
    for name, payload in panel_sources.items():
        stamp = _first_timestamp(payload, _FRESHNESS_FIELDS.get(name, ()))
        age = _age_seconds(stamp, now_epoch)
        threshold = _FRESHNESS_THRESHOLDS.get(name)
        data_ages[name] = {
            "at": stamp,
            "age_seconds": age,
            "threshold_seconds": threshold,
            # Fail-closed: no parseable timestamp reads as stale, not fresh.
            "stale": (age is None) or (threshold is not None and age > threshold),
        }

    return {
        "generated_at": datetime.fromtimestamp(now_epoch, tz=timezone.utc).isoformat(),
        "data_ages": data_ages,
        "watchdog": watchdog_status,
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
        "mispricing_monitor": mispricing_monitor,
        "clv_report": clv_report,
        "sports_clv": _sports_clv_summary(clv_report),
        "loss_attribution": loss_attribution,
        "auto_promotion": auto_promotion,
        "council": council,
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
        # Wave-16: the mounted live-game poller's session summary.
        "live_poller": _load_json(rd / "live_poller_status.json") or {},
        # Wave-20: the machine's own ranked improvement plan.
        "self_improvement": _load_json(rd / "self_improvement_plan.json") or {},
        # Wave-22: the Universal Sports Engine sidecar's artifact summary.
        "use_sidecar": _use_sidecar_summary(rd),
        # Wave-26: the vNext sovereign-forecasting shadow runtime.
        "vnext_shadow": _load_json(rd / "vnext_shadow_status.json") or {},
        # Wave-35: operator control switches (main/crypto/sports-by-league/llm).
        "switches": _switches_summary(),
    }


def _switches_summary() -> dict[str, Any]:
    try:
        from autonomy.switches import Switches

        return Switches.load().summary()
    except Exception:
        return {}


def _use_sidecar_summary(rd: Path) -> dict[str, Any]:
    predictions = _load_json(rd / "use_predictions.json") or {}
    provenance: dict[str, int] = {}
    for row in predictions.get("rows") or []:
        if isinstance(row, dict) and "error" not in row:
            key = str(row.get("provenance"))
            provenance[key] = provenance.get(key, 0) + 1
    try:
        with (rd / "use_outcomes.jsonl").open(encoding="utf-8") as fh:
            outcomes = sum(1 for _ in fh)
    except OSError:
        outcomes = 0
    return {
        "status": predictions.get("status"),
        "generated_at": predictions.get("generated_at"),
        "predictions": sum(provenance.values()),
        "provenance": provenance,
        "outcomes_on_tape": outcomes,
    }


def assemble_status_snapshot(runtime_dir: Path | None = None) -> dict[str, Any]:
    """Fast, precomputed operator snapshot -- reads fresh runtime JSON only.

    This NEVER touches ledger.db (no backtest, no bootstrap, no canary): it is
    the responsive endpoint the dashboard falls back to while the heavy
    /api/autonomy report is (re)computing. Every panel carries an explicit age
    and stale flag so stale data is visibly stale rather than shown as healthy.
    """
    rd = runtime_dir or RUNTIME_DIR
    now_epoch = datetime.now(timezone.utc).timestamp()

    heartbeat = _load_json(rd / "heartbeat.json") or {"alive": False}
    panels_raw = {
        "heartbeat": heartbeat,
        "mispricing_monitor": _load_json(rd / "mispricing_monitor_latest.json") or {},
        "crypto_paper_twin": _load_json(rd / "crypto_paper_twin_latest.json") or {},
        "sports_simulation": _load_json(rd / "sports_simulation_latest.json") or {},
        "simulation_training": _load_json(rd / "simulation_training_latest.json") or {},
        "readiness_report": _load_json(rd / "readiness_report.json") or {},
        "council_snapshot": _load_json(rd / "council_snapshot.json") or {},
        "clv_report": _load_json(rd / "clv_report.json") or {},
        "execution_tournament": _load_json(rd / "execution_tournament.json") or {},
    }
    data_ages: dict[str, Any] = {}
    for name, payload in panels_raw.items():
        stamp = _first_timestamp(payload, _FRESHNESS_FIELDS.get(name, ()))
        age = _age_seconds(stamp, now_epoch)
        threshold = _FRESHNESS_THRESHOLDS.get(name)
        data_ages[name] = {
            "at": stamp,
            "age_seconds": age,
            "threshold_seconds": threshold,
            "stale": (age is None) or (threshold is not None and age > threshold),
        }

    watchdog_status = _load_json(rd / "watchdog_status.json") or {}
    return {
        "generated_at": datetime.fromtimestamp(now_epoch, tz=timezone.utc).isoformat(),
        "source": "status_snapshot",
        "ledger_touched": False,
        "heartbeat": heartbeat,
        "session": session_authorization_state(rd),
        "risk_state": _load_json(rd / "risk_state.json"),
        "watchdog": watchdog_status,
        "data_ages": data_ages,
        "mispricing_monitor": panels_raw["mispricing_monitor"],
        "crypto_paper_twin": panels_raw["crypto_paper_twin"],
        "sports_simulation": panels_raw["sports_simulation"],
        "simulation_training": panels_raw["simulation_training"],
        "readiness_report": panels_raw["readiness_report"],
        "clv_report": panels_raw["clv_report"],
        "sports_clv": _sports_clv_summary(panels_raw["clv_report"]),
        "execution_tournament": _tournament_status_panel(panels_raw["execution_tournament"]),
        "alerts": _tail_jsonl(rd / "alerts.jsonl", 20),
        "recent_cycles": _tail_jsonl(rd / "cycles.jsonl", 10),
        # Both are cheap runtime-file reads (no ledger), so they belong in the
        # fast snapshot too: /api/autonomy 503s under a busy ledger, and without
        # these the vNext and USE cards would render blank on that fallback.
        "vnext_shadow": _load_json(rd / "vnext_shadow_status.json") or {},
        "use_sidecar": _use_sidecar_summary(rd),
        "switches": _switches_summary(),
    }


def _tournament_status_panel(report: dict[str, Any]) -> dict[str, Any]:
    """Compact execution-tournament view for the /api/status payload."""
    if not report or not report.get("report_name"):
        return {}
    try:
        from autonomy.execution_tournament import summarize_tournament

        return summarize_tournament(report)
    except Exception:
        return {
            "report_name": report.get("report_name"),
            "ranking": report.get("ranking", []),
            "headline": report.get("headline", {}),
            "generated_at": report.get("generated_at"),
        }


_HTML = DASHBOARD_HTML


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

    import os
    import threading
    from concurrent.futures import Future, ThreadPoolExecutor, TimeoutError as FutureTimeout

    app = FastAPI(title="Dummy Autonomy Dashboard")
    # The /api/autonomy report includes a 1,000-resample cluster bootstrap over
    # a multi-gigabyte ledger and can exceed a browser/proxy timeout on a cold
    # cache. Guard it: a 30-second cache serves warm polls; a cold poll kicks
    # the heavy assembly onto a background worker and waits only up to a bounded
    # deadline. If the deadline passes it returns 503 pointing at /api/status
    # (which never touches ledger.db) instead of blocking the event loop, while
    # the background job keeps running to populate the cache for the next poll.
    state_cache: dict[str, Any] = {"at": 0.0, "value": None, "epoch": 0}
    compute_lock = threading.Lock()
    pending: dict[str, Future | None] = {"future": None}
    worker = ThreadPoolExecutor(max_workers=1, thread_name_prefix="dashboard-state")
    deadline_seconds = float(os.environ.get("DUMMY_DASHBOARD_STATE_DEADLINE_SECONDS", "20"))
    # The heavy /api/autonomy report runs a backtest that holds the (large,
    # non-WAL) ledger; each assembly is a lock window the brain's write can
    # collide with. A longer cache TTL means fewer such reads. Env-tunable;
    # raised 30 -> 120s to cut ledger contention (the report is evidence, not
    # a hot control surface, so a couple minutes of staleness is fine).
    state_ttl_seconds = float(os.environ.get("DUMMY_DASHBOARD_STATE_TTL_SECONDS", "120"))

    def _store(epoch_at_submit: int, assembled: dict[str, Any]) -> None:
        # A control action can invalidate the cache while this expensive report
        # assembles. Never let that stale request overwrite post-control state.
        with compute_lock:
            if epoch_at_submit == int(state_cache["epoch"]):
                state_cache["value"] = assembled
                state_cache["at"] = _monotonic()

    def _ensure_compute() -> tuple[Future, int]:
        with compute_lock:
            fut = pending["future"]
            epoch_at_submit = int(state_cache["epoch"])
            if fut is not None and not fut.done():
                return fut, epoch_at_submit
            new_fut = worker.submit(assemble_dashboard_state)
            pending["future"] = new_fut
        # Populate the cache even when the requester times out below. Attached
        # OUTSIDE compute_lock: a future that finished already runs its callback
        # synchronously here, and _store re-acquires the (non-reentrant) lock.
        new_fut.add_done_callback(
            lambda f: _store(epoch_at_submit, f.result()) if not f.cancelled() and f.exception() is None else None
        )
        return new_fut, epoch_at_submit

    @app.get("/api/autonomy")
    def api_state() -> JSONResponse:
        now = _monotonic()
        if state_cache["value"] is not None and now - float(state_cache["at"]) < state_ttl_seconds:
            return JSONResponse(state_cache["value"])
        fut, epoch_at_submit = _ensure_compute()
        try:
            assembled = fut.result(timeout=deadline_seconds)
            _store(epoch_at_submit, assembled)  # inline: no callback-ordering race
            return JSONResponse(assembled)
        except FutureTimeout:
            # Serve a stale cached value rather than nothing, if we have one.
            if state_cache["value"] is not None:
                payload = dict(state_cache["value"])
                payload["stale_cache"] = True
                return JSONResponse(payload)
            return JSONResponse(
                {
                    "status": "COMPUTING",
                    "detail": (
                        "The full evidence report is still assembling "
                        "(cluster bootstrap over the ledger). Poll /api/status "
                        "for the fast precomputed snapshot in the meantime."
                    ),
                    "hint": "/api/status",
                },
                status_code=503,
            )

    @app.get("/api/status")
    def api_status() -> JSONResponse:
        # Fast, precomputed snapshot: fresh runtime JSON + watchdog only, never
        # ledger.db. Always responsive, even while /api/autonomy recomputes.
        return JSONResponse(assemble_status_snapshot())

    @app.get("/api/bet_board")
    def api_bet_board() -> JSONResponse:
        # Wave-15: every market the brain currently prices, ranked. A bounded
        # single-source read (latest fused_forecast per open market) -- cheap
        # enough to serve uncached, and isolated so a board error is a JSON
        # error field, never a 500 that breaks the page.
        from autonomy.bet_board import assemble_bet_board

        try:
            return JSONResponse(assemble_bet_board())
        except Exception as exc:
            return JSONResponse({"error": f"{type(exc).__name__}: {exc}"[:200],
                                 "rows": 0, "groups": {}})

    def _snapshot_block(key: str) -> dict[str, Any]:
        # Wave-51: serve the redesigned dashboard's overview / per-scope blocks
        # straight from the persisted snapshot artifact -- never opens the ledger,
        # always fast, and a missing block is an empty dict, never a 500.
        from autonomy.dashboard_snapshot import read_dashboard_snapshot

        snap = read_dashboard_snapshot(RUNTIME_DIR / "latest_dashboard_snapshot.json") or {}
        block = snap.get(key) or {}
        block["generated_at"] = snap.get("generated_at")
        block["backtest_generated_at"] = snap.get("backtest_generated_at")
        return block

    @app.get("/api/overview")
    def api_overview() -> JSONResponse:
        try:
            return JSONResponse(_snapshot_block("overview"))
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": f"{type(exc).__name__}: {exc}"[:200]})

    @app.get("/api/scopes")
    def api_scopes() -> JSONResponse:
        try:
            return JSONResponse(_snapshot_block("scopes"))
        except Exception as exc:  # noqa: BLE001
            return JSONResponse({"error": f"{type(exc).__name__}: {exc}"[:200], "verticals": {}})

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
