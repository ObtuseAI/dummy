"""Operator alerts: surface the few events that change what the operator does.

An unattended predator needs to shout only when it matters — it self-stopped,
it de-risked on drawdown, the evidence gate finally went green, or cycles are
erroring in a streak. Alerts are appended to a JSONL log and the latest is
mirrored to a small JSON file a dashboard or notifier can poll. De-duplicated
so the same standing condition does not spam every cycle.
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

RUNTIME_DIR = Path("runtime/autonomy")
ALERTS_LOG = RUNTIME_DIR / "alerts.jsonl"
ALERTS_LATEST = RUNTIME_DIR / "alerts_latest.json"
ALERT_STATE = RUNTIME_DIR / "alert_state.json"

SEVERITY = {
    "SELF_STOP": "critical",
    "DRAWDOWN_LADDER": "warning",
    "GATE_GREEN": "info",
    "GATE_REGRESSION": "warning",
    "CYCLE_ERROR_STREAK": "warning",
    "SIGNAL_QUALITY_REJECTION": "warning",
    # A recalibration produced a degenerate trust vector and was rejected.
    "RECAL_REJECTED": "critical",
    # The authoritative backtest summary is older than the freshness bound;
    # downstream evaluation is fail-closed until it refreshes.
    "BACKTEST_STALE": "warning",
    # The ledger database is bloated or a read-only health probe failed.
    "LEDGER_HEALTH": "warning",
}


def _load_state() -> dict[str, Any]:
    if ALERT_STATE.exists():
        try:
            return json.loads(ALERT_STATE.read_text(encoding="utf-8"))
        except Exception:
            return {}
    return {}


def _save_state(state: dict[str, Any]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    ALERT_STATE.write_text(json.dumps(state, indent=2, sort_keys=True), encoding="utf-8")


def emit_alert(kind: str, message: str, detail: dict[str, Any] | None = None, now_iso: str | None = None) -> dict[str, Any]:
    """Append + mirror one alert. Returns the alert record."""
    record = {
        "kind": kind,
        "severity": SEVERITY.get(kind, "info"),
        "message": message,
        "detail": detail or {},
        "at": now_iso or datetime.now(timezone.utc).isoformat(),
    }
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    with ALERTS_LOG.open("a", encoding="utf-8") as fh:
        fh.write(json.dumps(record, sort_keys=True) + "\n")
    ALERTS_LATEST.write_text(json.dumps(record, indent=2, sort_keys=True), encoding="utf-8")
    return record


def evaluate_alerts(cycle_record: dict[str, Any], risk_state: dict[str, Any] | None,
                    gate_ready: bool, now_iso: str | None = None,
                    *, ledger_health: dict[str, Any] | None = None,
                    backtest_freshness: dict[str, Any] | None = None) -> list[dict[str, Any]]:
    """Decide which alerts to emit this cycle, de-duplicated against prior state."""
    state = _load_state()
    fired: list[dict[str, Any]] = []

    status = str(cycle_record.get("status", ""))

    # Self-stop: fire once per stop episode.
    if status.startswith("HALTED_SELF_STOP"):
        if not state.get("self_stopped"):
            fired.append(emit_alert("SELF_STOP", status, {"cycle": cycle_record}, now_iso))
            state["self_stopped"] = True
    else:
        state["self_stopped"] = False

    # Drawdown ladder: fire when the ladder rung deepens.
    if risk_state:
        peak = risk_state.get("equity_peak_cents") or 0
        bankroll = risk_state.get("bankroll_cents") or 0
        dd = (1.0 - bankroll / peak) if peak else 0.0
        rung = 0
        for threshold in (0.10, 0.20, 0.30):
            if dd >= threshold - 1e-9:
                rung += 1
        if rung > int(state.get("drawdown_rung", 0)):
            fired.append(emit_alert("DRAWDOWN_LADDER", f"drawdown {dd:.1%} reached rung {rung}",
                                    {"drawdown": round(dd, 4), "rung": rung}, now_iso))
        state["drawdown_rung"] = rung

    # Evidence gate edges: green is actionable; regression after green is a
    # warning because new operating evidence invalidated prior readiness.
    if gate_ready and not state.get("gate_green"):
        fired.append(emit_alert("GATE_GREEN", "live canary evidence gate is READY", {}, now_iso))
    elif not gate_ready and state.get("gate_green"):
        fired.append(emit_alert(
            "GATE_REGRESSION",
            "live canary evidence gate returned to BLOCKED after new evidence",
            {}, now_iso,
        ))
    state["gate_green"] = bool(gate_ready)

    # Cycle-error streak.
    if status.startswith("CYCLE_ERROR"):
        streak = int(state.get("error_streak", 0)) + 1
        state["error_streak"] = streak
        if streak >= 3 and streak != int(state.get("last_error_alert_streak", 0)):
            fired.append(emit_alert("CYCLE_ERROR_STREAK", f"{streak} consecutive cycle errors",
                                    {"status": status}, now_iso))
            state["last_error_alert_streak"] = streak
    else:
        state["error_streak"] = 0

    # Malformed model statistics are quarantined by the ledger. Alert on the
    # start of an episode so silent source/schema drift is still operator-visible.
    rejected = int(cycle_record.get("signals_rejected") or 0)
    if rejected > 0 and not state.get("signal_rejection_active"):
        fired.append(emit_alert(
            "SIGNAL_QUALITY_REJECTION",
            f"{rejected} signal observations failed intake validation",
            {"signals_rejected": rejected},
            now_iso,
        ))
    state["signal_rejection_active"] = rejected > 0

    # Ledger health: bloat or a failed read-only probe. Fire once per episode
    # so a persistent condition does not spam every cycle.
    if ledger_health:
        unhealthy = bool(ledger_health.get("bloat_warn")) or bool(
            ledger_health.get("probe_error")
        )
        if unhealthy and not state.get("ledger_health_alert_active"):
            fired.append(emit_alert(
                "LEDGER_HEALTH",
                "ledger health degraded: "
                + ("bloat " if ledger_health.get("bloat_warn") else "")
                + (f"probe_error={ledger_health.get('probe_error')}"
                   if ledger_health.get("probe_error") else "")
                + f"size={ledger_health.get('size_gib')}GiB",
                ledger_health, now_iso,
            ))
        state["ledger_health_alert_active"] = unhealthy

    # Backtest evidence staleness: the authoritative summary went 6 days stale
    # once with no alarm. Fire on the rising edge of the stale episode.
    if backtest_freshness is not None:
        stale = bool(backtest_freshness.get("is_stale"))
        if stale and not state.get("backtest_stale_alert_active"):
            fired.append(emit_alert(
                "BACKTEST_STALE",
                "authoritative backtest summary is stale "
                f"(age_hours={backtest_freshness.get('age_hours')}, "
                f"reason={backtest_freshness.get('reason')}); "
                "downstream evaluation is fail-closed",
                backtest_freshness, now_iso,
            ))
        state["backtest_stale_alert_active"] = stale

    _save_state(state)
    return fired


def recent_alerts(limit: int = 20) -> list[dict[str, Any]]:
    if not ALERTS_LOG.exists():
        return []
    try:
        lines = ALERTS_LOG.read_text(encoding="utf-8").strip().splitlines()
    except Exception:
        return []
    out = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except Exception:
            continue
    return out
