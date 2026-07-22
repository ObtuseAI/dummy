"""Resilient shadow-cycle runner.

One cycle per invocation (crash-isolated, scheduler-friendly) or an internal
loop. Never dies on a single bad cycle, honors the kill file, and writes a
heartbeat + an append-only JSONL cycle log so a supervisor or dashboard can
see liveness and history without touching the ledger.
"""
from __future__ import annotations

import asyncio
import json
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.executor import kill_switch_active
from autonomy.ontology import SessionMode

RUNTIME_DIR = Path("runtime/autonomy")
HEARTBEAT_PATH = RUNTIME_DIR / "heartbeat.json"
CYCLE_LOG_PATH = RUNTIME_DIR / "cycles.jsonl"
RECAL_STAMP_PATH = RUNTIME_DIR / "last_recalibration.json"
RECAL_INTERVAL_HOURS = 6.0


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _maybe_recalibrate(now_iso: str) -> dict[str, Any] | None:
    """Periodic self-recalibration: the machine re-derives its own trust.

    Every RECAL_INTERVAL_HOURS the daemon re-runs the backtest bootstrap
    (global + vertical + exact grading-scope weights, contested caps included),
    refreshes contraction-only performance quarantines, and refits the
    market-debias curve from the full settlement history. No operator in the
    loop: calibration is a metabolic process, not a maintenance chore.
    Gated off in unit tests via DUMMY_DAEMON_RECAL=0.
    """
    import os

    if os.environ.get("DUMMY_DAEMON_RECAL", "1") != "1":
        return None
    try:
        if RECAL_STAMP_PATH.exists():
            stamp = json.loads(RECAL_STAMP_PATH.read_text(encoding="utf-8"))
            last = datetime.fromisoformat(str(stamp.get("at")))
            age_h = (datetime.fromisoformat(now_iso) - last).total_seconds() / 3600.0
            if age_h < RECAL_INTERVAL_HOURS:
                return None
    except Exception:
        pass  # unreadable stamp -> recalibrate now
    try:
        from autonomy.backtest import run_backtest
        from autonomy.ledger import AutonomyLedger
        from autonomy.signals.market_debias import fit_curve, ledger_samples, write_curve

        ledger = AutonomyLedger()
        try:
            _t0 = time.perf_counter()
            # Weights-only core (Wave-44): skip the ~11 full-ledger-scan
            # diagnostic sub-reports so the 6-hourly weight refresh stays fast and
            # does not block the next cycle. The diagnostics + summary + dashboard
            # snapshot are produced by the lower-frequency DummyBacktestReport
            # task (scripts/run_dummy_backtest_report.py).
            report = run_backtest(ledger, bootstrap_weights=True, include_diagnostics=False)
            write_curve(fit_curve(ledger_samples(ledger)))
        finally:
            ledger.close()
        summary = {
            "at": now_iso,
            "duration_seconds": round(time.perf_counter() - _t0, 1),
            "settled_markets": report.get("settled_markets"),
            "derived_weights": report.get("derived_weights"),
            "exact_scope_weights": len(report.get("sources_by_scope") or {}),
        }
        RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
        RECAL_STAMP_PATH.write_text(json.dumps(summary, indent=2, sort_keys=True), encoding="utf-8")
        return summary
    except Exception:
        return None  # recalibration must never wedge a cycle


def _write_heartbeat(payload: dict[str, Any]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    HEARTBEAT_PATH.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")


def _append_cycle_log(report: dict[str, Any]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with CYCLE_LOG_PATH.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(report, sort_keys=True) + "\n")


def run_one_cycle(now_iso: str, mode: SessionMode = SessionMode.SHADOW) -> dict[str, Any]:
    """Run a single cycle; never raises — errors become a status record."""
    from autonomy.session import build_brain

    if kill_switch_active():
        completed_at = _utc_now_iso()
        record = {
            "status": "HALTED_KILL_SWITCH",
            "at": now_iso,
            "completed_at": completed_at,
        }
        _write_heartbeat({
            "alive": True,
            "last_cycle_at": completed_at,
            "last_cycle_started_at": now_iso,
            "last_status": record["status"],
            "mode": mode.value,
        })
        return record

    try:
        brain = build_brain(mode)
        report = asyncio.run(brain.run_cycle())
        record = report.to_dict()
        record["at"] = now_iso
    except Exception as exc:  # a bad cycle must never wedge the daemon
        record = {"status": f"CYCLE_ERROR:{type(exc).__name__}", "error": str(exc)[:300], "at": now_iso}
    finally:
        try:
            brain.ledger.close()  # type: ignore[name-defined]
        except Exception:
            pass

    recal = _maybe_recalibrate(now_iso)
    if recal is not None:
        record["recalibrated"] = True

    # Read-only ledger health probe: file size, bloat flag, header pragmas.
    # Surfaced on the heartbeat so a growing/locked ledger is operator-visible
    # long before it becomes a CYCLE_ERROR streak. Never wedges the cycle.
    ledger_health: dict[str, Any] | None = None
    try:
        from autonomy.ledger import ledger_health_probe

        ledger_health = ledger_health_probe(RUNTIME_DIR / "ledger.db")
    except Exception:
        ledger_health = None

    # ``now_iso`` is the cycle start. Long production cycles can take several
    # minutes, so publishing it as the heartbeat time makes a just-completed
    # healthy cycle appear stale. Preserve start time for duration forensics and
    # use the actual completion time for liveness/freshness consumers.
    completed_at = _utc_now_iso()
    record["completed_at"] = completed_at
    _append_cycle_log(record)
    _write_heartbeat({
        "alive": True,
        "last_cycle_at": completed_at,
        "last_cycle_started_at": now_iso,
        "last_status": record.get("status"),
        "last_orders_placed": record.get("orders_placed"),
        "last_signals": record.get("signals_generated"),
        "last_settlements": record.get("settlements"),
        "mode": mode.value,
        "ledger_health": ledger_health,
    })

    # Operator alerts (self-stop / drawdown / gate-green / error streak).
    # Disabled under the test suite (conftest sets DUMMY_DAEMON_ALERTS=0) so
    # unit tests never open the real ledger or write real alert files.
    import os

    if os.environ.get("DUMMY_DAEMON_ALERTS", "1") != "1":
        return record
    try:
        from autonomy.alerts import evaluate_alerts

        risk_state = None
        risk_path = RUNTIME_DIR / "risk_state.json"
        if risk_path.exists():
            risk_state = json.loads(risk_path.read_text(encoding="utf-8"))
        gate_ready = False
        try:
            from live_firewall.firewall import live_execution_authority_status

            gate_ready = bool(
                live_execution_authority_status().get("execution_authority")
            )
        except Exception:
            gate_ready = False
        backtest_freshness = None
        try:
            from autonomy.backtest import backtest_summary_freshness

            backtest_freshness = backtest_summary_freshness()
        except Exception:
            backtest_freshness = None
        evaluate_alerts(
            record, risk_state, gate_ready, now_iso,
            ledger_health=ledger_health,
            backtest_freshness=backtest_freshness,
        )
    except Exception:
        pass  # alerting must never wedge the cycle

    return record
