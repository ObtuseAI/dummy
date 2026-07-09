"""Resilient shadow-cycle runner.

One cycle per invocation (crash-isolated, scheduler-friendly) or an internal
loop. Never dies on a single bad cycle, honors the kill file, and writes a
heartbeat + an append-only JSONL cycle log so a supervisor or dashboard can
see liveness and history without touching the ledger.
"""
from __future__ import annotations

import asyncio
import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from autonomy.executor import kill_switch_active
from autonomy.ontology import SessionMode

RUNTIME_DIR = Path("runtime/autonomy")
HEARTBEAT_PATH = RUNTIME_DIR / "heartbeat.json"
CYCLE_LOG_PATH = RUNTIME_DIR / "cycles.jsonl"


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
        record = {"status": "HALTED_KILL_SWITCH", "at": now_iso}
        _write_heartbeat({**record, "alive": True})
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

    _append_cycle_log(record)
    _write_heartbeat({
        "alive": True,
        "last_cycle_at": now_iso,
        "last_status": record.get("status"),
        "last_orders_placed": record.get("orders_placed"),
        "last_signals": record.get("signals_generated"),
        "last_settlements": record.get("settlements"),
        "mode": mode.value,
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
            from autonomy.session import canary_readiness

            gate_ready = bool(canary_readiness(check_balance=False).get("ready"))
        except Exception:
            gate_ready = False
        evaluate_alerts(record, risk_state, gate_ready, now_iso)
    except Exception:
        pass  # alerting must never wedge the cycle

    return record
