"""Production dashboard observations with no network, provider, write, or subprocess calls.

The historical V3/V4 routes are an explicitly mounted offline archive.  Core
operator screens use this router so an ordinary page load cannot contact a
broker or turn missing state into demo data.
"""

from __future__ import annotations

import json
import os
from collections import deque
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from autonomy.target_policy import target_policy_payload
from core.config_loader import load_caps
from core.secret_guard import redact
from core.state import STATE
from live_firewall.exposure_tracker import get_persistent_exposure_tracker


router = APIRouter(prefix="/api/read-only", tags=["production-read-only"])
ROOT = Path(__file__).resolve().parents[2]
LOG_FILE = ROOT / "logs" / "dummy.jsonl"
LIVE_SUBMIT_PATH = ROOT / "configs" / "live_submit.json"


def _credentials_present() -> bool:
    key_id = os.environ.get("KALSHI_API_KEY_ID")
    private_key = (
        os.environ.get("KALSHI_API_PRIVATE_KEY_PEM")
        or os.environ.get("KALSHI_PRIVATE_KEY")
        or os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH")
        or os.environ.get("KALSHI_PRIVATE_KEY_PATH")
    )
    return bool(key_id and private_key)


def _unavailable(*, reason: str, **fields: Any) -> dict[str, Any]:
    return {
        **fields,
        "source": "unavailable",
        "data_status": "unavailable",
        "unavailable_reason": reason,
        "live_snapshot_available": False,
    }


def _target_policy(ticker: str) -> dict[str, Any]:
    policy = target_policy_payload(ticker)
    if policy["classification"] == "data_only":
        return {
            "role": "data_only",
            "prediction_target": False,
            "execution_target": False,
        }
    if policy["classification"] == "unsupported_target":
        return {
            "role": "excluded",
            "prediction_target": False,
            "execution_target": False,
            "reason": policy["reason"],
        }
    return {
        "role": "eligibility_unverified",
        "prediction_target": None,
        "execution_target": None,
    }


@router.get("/caps")
async def caps() -> dict[str, Any]:
    return {
        "caps": load_caps().model_dump(),
        "source": "configs/caps.json",
        "data_status": "stored_configuration",
    }


@router.get("/exposure")
async def exposure() -> dict[str, Any]:
    tracker = get_persistent_exposure_tracker()
    healthy = tracker.state_healthy
    return redact({
        "positions": (
            [position.model_dump(mode="json") for position in tracker.positions.values()]
            if healthy else None
        ),
        "orders": list(tracker.open_orders) if healthy else None,
        "total_exposure_cents": tracker.total_exposure_cents() if healthy else None,
        "open_markets": tracker.open_markets() if healthy else None,
        "open_order_count": tracker.open_order_count() if healthy else None,
        "orders_last_hour": tracker.orders_last_hour() if healthy else None,
        "orders_last_hour_window": "rolling_60_minutes_utc",
        "mode": STATE.mode.value,
        "state_status": "ready" if healthy else "unavailable",
        "state_error": tracker.persistence_error,
        "source": "runtime/live_exposure_state.json",
        "data_status": "stored_local_risk_state" if healthy else "unavailable",
        "live_broker_snapshot": False,
    })


@router.get("/kalshi/status")
async def kalshi_status() -> dict[str, Any]:
    credentials_present = _credentials_present()
    return {
        # STATE.kalshi_connected has no receipt timestamp, so it is telemetry,
        # not a fresh connection witness.
        "connected": False if not credentials_present else None,
        "runtime_connected_flag": bool(STATE.kalshi_connected),
        "connection_status": (
            "STORED_RUNTIME_FLAG_UNVERIFIED" if credentials_present else "CREDENTIALS_MISSING"
        ),
        "connection_verified": False,
        "connection_witness_at": None,
        "credentials_present": credentials_present,
        "api_key_id_present": bool(os.environ.get("KALSHI_API_KEY_ID")),
        "mode": STATE.mode.value,
        "balance_cents": STATE.balance_cents,
        "balance_status": "stored_runtime_unverified",
        "source": "runtime_state",
        "data_status": "stored_runtime_unverified",
        "live_snapshot_available": False,
        "read_only_surface": True,
    }


@router.get("/kalshi/markets")
async def kalshi_markets() -> dict[str, Any]:
    return _unavailable(
        reason="no_local_current_market_snapshot; dashboard GETs never contact the broker",
        events=None,
        markets=None,
    )


@router.get("/kalshi/orderbook/{ticker}")
async def kalshi_orderbook(ticker: str) -> dict[str, Any]:
    return _unavailable(
        reason="no_local_current_orderbook_snapshot; dashboard GETs never contact the broker",
        orderbook=None,
        ticker=ticker,
        target_policy=_target_policy(ticker),
    )


@router.get("/kalshi/account")
async def kalshi_account() -> dict[str, Any]:
    return {
        "account": None,
        "balance": {
            "balance_cents": STATE.balance_cents,
            "verification_status": "stored_runtime_unverified",
        },
        "source": "runtime_state",
        "data_status": "stored_runtime_unverified",
        "live_snapshot_available": False,
    }


@router.get("/kalshi/positions")
async def kalshi_positions() -> dict[str, Any]:
    data = await exposure()
    return {
        "positions": data["positions"],
        "source": data["source"],
        "data_status": data["data_status"],
        "live_snapshot_available": False,
        "state_status": data["state_status"],
    }


@router.get("/kalshi/orders")
async def kalshi_orders() -> dict[str, Any]:
    data = await exposure()
    return {
        "orders": data["orders"],
        "source": data["source"],
        "data_status": data["data_status"],
        "live_snapshot_available": False,
        "state_status": data["state_status"],
    }


@router.get("/kalshi/fills")
async def kalshi_fills() -> dict[str, Any]:
    return _unavailable(
        reason="no_local_current_broker_fill_snapshot",
        fills=None,
    )


@router.get("/firewall/rejections")
async def firewall_rejections() -> dict[str, Any]:
    counts: dict[str, int] = {}
    scanned = 0
    skipped_malformed = 0
    lines: deque[str] = deque(maxlen=1000)
    if not LOG_FILE.exists():
        return _unavailable(
            reason="local_firewall_log_missing",
            observed_reasons=None,
            observed_rejection_count=None,
            firewall_events_scanned=None,
            skipped_malformed=None,
        )
    try:
        with LOG_FILE.open(encoding="utf-8") as stream:
            lines.extend(stream)
    except (OSError, UnicodeError):
        return _unavailable(
            reason="local_firewall_log_unreadable",
            observed_reasons=None,
            observed_rejection_count=None,
            firewall_events_scanned=None,
            skipped_malformed=None,
        )
    for line in lines:
        try:
            entry = json.loads(line)
        except (json.JSONDecodeError, TypeError, ValueError):
            skipped_malformed += 1
            continue
        if not isinstance(entry, dict) or entry.get("component") != "firewall":
            continue
        scanned += 1
        extra = entry.get("extra") if isinstance(entry.get("extra"), dict) else {}
        reason = extra.get("rejected_by") or extra.get("reason")
        if reason:
            key = str(reason)
            counts[key] = counts.get(key, 0) + 1
    return {
        "observed_reasons": [
            {"reason": reason, "count": count}
            for reason, count in sorted(counts.items(), key=lambda item: (-item[1], item[0]))
        ],
        "observed_rejection_count": sum(counts.values()),
        "firewall_events_scanned": scanned,
        "skipped_malformed": skipped_malformed,
        "source": "local_log_derived",
        "data_status": "stored_observations",
        "window": "last_1000_log_lines",
    }


@router.get("/firewall/rehearsal")
async def firewall_rehearsal() -> dict[str, Any]:
    return {
        "status": "NOT_RUN_READ_ONLY_SURFACE",
        "rehearsal_executed": False,
        "live_submitted": False,
        "credentials_present": _credentials_present(),
        "firewall_rehearsal": None,
        "reason": "dashboard GETs do not execute the firewall or contact a broker",
        "source": "read_only_surface_policy",
        "data_status": "not_executed",
    }


@router.get("/live-submit/status")
async def live_submit_status() -> dict[str, Any]:
    if not LIVE_SUBMIT_PATH.exists():
        return {
            "enabled": False,
            "effective_execution_enabled": False,
            "execution_authority": False,
            "configured_enabled": None,
            "file_present": False,
            "data_status": "missing_fail_closed",
            "validation_status": "MISSING_FAIL_CLOSED",
            "source": "configs/live_submit.json",
        }
    try:
        data = json.loads(LIVE_SUBMIT_PATH.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError):
        return {
            "enabled": False,
            "effective_execution_enabled": False,
            "execution_authority": False,
            "configured_enabled": None,
            "file_present": True,
            "data_status": "malformed_fail_closed",
            "validation_status": "MALFORMED_FAIL_CLOSED",
            "source": "configs/live_submit.json",
        }
    configured = data.get("enabled") if isinstance(data, dict) else None
    valid = isinstance(configured, bool)
    effective = False if valid and configured is False else None
    return {
        # Configuration alone never proves that canary, caps, approvals, risk,
        # and central-firewall gates currently grant effective authority.
        "enabled": effective,
        "effective_execution_enabled": effective,
        "execution_authority": False,
        "configured_enabled": configured if valid else None,
        "file_present": True,
        "data_status": "stored_configuration" if valid else "malformed_fail_closed",
        "validation_status": "VALID_CONFIG_ONLY" if valid else "MALFORMED_FAIL_CLOSED",
        "source": "configs/live_submit.json",
    }
