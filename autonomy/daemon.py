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

# The scheduled launcher (scripts/tasks/launch_shadow_predator.vbs) HARD-KILLS
# the whole Python process tree 13 minutes after start. A cycle that runs past
# that is terminated mid-write, so it never reaches the heartbeat write below --
# freezing last_cycle_at at the last un-killed cycle and leaving a permanent
# CYCLE_ERROR + staleness that aborts the promotion runner forever. To stay
# watchdog-safe, the cycle honors a COOPERATIVE soft deadline well under 13 min:
# it aborts cleanly at the next await boundary, records a real status, and WRITES
# the heartbeat -- so liveness stays visible and promotion is never held hostage
# to a silent kill. Budget: 13min watchdog - one max ledger lock-wait - margin.
def _cycle_soft_deadline_s() -> float:
    import os

    try:
        value = float(os.environ.get("DUMMY_CYCLE_SOFT_DEADLINE_S", "540"))
        return value if value > 0 else 540.0
    except (TypeError, ValueError):
        return 540.0


class _CycleDeadlineExceeded(Exception):
    """The cycle passed its watchdog-safe soft deadline and was aborted."""


async def _run_cycle_with_deadline(brain: Any, deadline_s: float) -> Any:
    try:
        return await asyncio.wait_for(brain.run_cycle(), timeout=deadline_s)
    except asyncio.TimeoutError as exc:  # noqa: UP041 - asyncio.TimeoutError pre-3.11 alias
        raise _CycleDeadlineExceeded(
            f"cycle exceeded {deadline_s:g}s soft deadline (watchdog-safe abort)"
        ) from exc


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _read_heartbeat() -> dict[str, Any]:
    try:
        return json.loads(HEARTBEAT_PATH.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}


def _is_healthy_status(status: str | None) -> bool:
    """A cycle that priced + wrote normally (not an error, kill, or halt)."""
    s = str(status or "")
    return bool(s) and not s.startswith(("CYCLE_ERROR", "HALTED", "ERROR"))


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
    # The recal is DUE. A full backtest bootstrap on a large ledger cannot finish
    # inside the cycle's watchdog window (pricing alone is ~8 min; the launcher
    # hard-kills at 13 min), so on a big ledger it only ever gets killed mid-run
    # -- never refreshing weights and leaving a hot journal. Above the threshold,
    # defer to the dedicated out-of-band DummyWeightsRecal task (no watchdog);
    # below it, keep the fast in-cycle recal. Env-tunable; 0 disables the guard.
    try:
        max_gib = float(os.environ.get("DUMMY_RECAL_MAX_LEDGER_GIB", "6"))
    except (TypeError, ValueError):
        max_gib = 6.0
    if max_gib > 0:
        try:
            size_gib = (RUNTIME_DIR / "ledger.db").stat().st_size / 1024 ** 3
            if size_gib > max_gib:
                return {"deferred": "ledger_too_large_for_in_cycle_recal",
                        "size_gib": round(size_gib, 2)}
        except OSError:
            pass
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
        report = asyncio.run(_run_cycle_with_deadline(brain, _cycle_soft_deadline_s()))
        record = report.to_dict()
        record["at"] = now_iso
    except _CycleDeadlineExceeded as exc:
        # Clean, watchdog-safe abort: record it and fall through to WRITE the
        # heartbeat (below) so last_cycle_at advances and the promotion runner
        # sees a live -- if erroring -- system rather than a frozen one.
        record = {"status": "CYCLE_ERROR:CycleDeadline", "error": str(exc)[:300], "at": now_iso}
    except Exception as exc:  # a bad cycle must never wedge the daemon
        record = {"status": f"CYCLE_ERROR:{type(exc).__name__}", "error": str(exc)[:300], "at": now_iso}
    finally:
        try:
            brain.ledger.close()  # type: ignore[name-defined]
        except Exception:
            pass

    recal = _maybe_recalibrate(now_iso)
    if isinstance(recal, dict) and recal.get("deferred"):
        record["recal_deferred"] = recal.get("deferred")
    elif recal is not None:
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
    # Track the last HEALTHY cycle separately from the last completion. The
    # promotion runner uses it to tell a transient infra hiccup (a recent
    # success, latest cycle errored on a DB lock) apart from a genuine sustained
    # outage (no success in hours) -- so a single locked cycle no longer
    # permanently vetoes promotion while a real failure still does.
    prior = _read_heartbeat()
    last_success_at = (
        completed_at if _is_healthy_status(record.get("status"))
        else prior.get("last_success_at")
    )
    _write_heartbeat({
        "alive": True,
        "last_cycle_at": completed_at,
        "last_cycle_started_at": now_iso,
        "last_success_at": last_success_at,
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
