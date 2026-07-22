"""Dashboard V4 routes for real Kalshi ingestion and firewall rehearsal."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from autonomy.target_policy import is_data_only_target
from core.config_loader import load_caps
from core.ontology import AccountMode, OrderBook, OrderBookLevel
from core.secret_guard import redact
from core.state import STATE
from dashboard.backend.operator_auth import require_operator
from forecasting.engine import ForecastEngine
from kalshi.live_data import KalshiRealReadOnly
from strategies.scan import StrategyScanner

router = APIRouter(prefix="/v4", tags=["v4"])
LOG_FILE = Path("C:/src/engine/dummy/logs/dummy.jsonl")


def _credentials_present() -> bool:
    key_id = os.environ.get("KALSHI_API_KEY_ID")
    pem = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM") or os.environ.get(
        "KALSHI_PRIVATE_KEY"
    )
    pem_path = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH") or os.environ.get(
        "KALSHI_PRIVATE_KEY_PATH"
    )
    return bool(key_id and (pem or pem_path))


def _unavailable_payload(*, reason: str, **fields: Any) -> dict[str, Any]:
    return {
        **fields,
        "source": "unavailable",
        "data_status": "unavailable",
        "unavailable_reason": reason,
        "live_snapshot_available": False,
    }


def _target_policy(record: dict[str, Any], *, fallback_ticker: str = "") -> dict[str, Any]:
    ticker = str(
        record.get("ticker")
        or record.get("market_ticker")
        or record.get("event_ticker")
        or fallback_ticker
    )
    category = record.get("category") or record.get("series_category") or record.get("event_category")
    if is_data_only_target(ticker, category=category):
        return {
            "role": "data_only",
            "prediction_target": False,
            "execution_target": False,
        }
    return {
        "role": "eligibility_unverified",
        "prediction_target": None,
        "execution_target": None,
    }


def _annotate_records(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {**record, "target_policy": _target_policy(record)}
        for record in records
        if isinstance(record, dict)
    ]


@router.get("/kalshi/status")
async def kalshi_status() -> dict[str, Any]:
    credentials_present = _credentials_present()
    connected = bool(STATE.kalshi_connected) if credentials_present else False
    return {
        "connected": connected,
        "connection_status": (
            "CONNECTED_RUNTIME_WITNESS"
            if connected
            else "NOT_CONNECTED_RUNTIME_STATE"
            if credentials_present
            else "CREDENTIALS_MISSING"
        ),
        "connection_verified": connected,
        "credentials_present": credentials_present,
        "mode": STATE.mode.value,
        "kalshi_connected": STATE.kalshi_connected,
        "source": "runtime_connection_state",
    }


@router.get("/kalshi/account")
async def kalshi_account() -> dict[str, Any]:
    if not _credentials_present():
        return _unavailable_payload(reason="credentials_missing", account=None, balance=None)
    reader = None
    try:
        reader = KalshiRealReadOnly()
        account = await reader.get_account_status()
        balance = await reader.get_balance()
        return redact({
            "account": account,
            "balance": balance,
            "source": "live",
            "data_status": "live_read_only",
            "live_snapshot_available": True,
        })
    except Exception as exc:
        return redact({
            "account": None,
            "balance": None,
            "error": str(exc),
            "source": "live_error",
            "data_status": "unavailable",
            "live_snapshot_available": False,
        })
    finally:
        if reader is not None:
            try:
                await reader.close()
            except Exception:
                pass


@router.get("/kalshi/markets")
async def kalshi_markets() -> dict[str, Any]:
    if not _credentials_present():
        return _unavailable_payload(reason="credentials_missing", markets=None, events=None)
    reader = None
    try:
        reader = KalshiRealReadOnly()
        events = await reader.get_events()
        markets = await reader.get_markets()
        if not isinstance(events, list) or not isinstance(markets, list):
            return {
                "events": None,
                "markets": None,
                "source": "live_incomplete",
                "data_status": "live_read_only_incomplete",
                "live_snapshot_available": False,
            }
        return redact({
            "events": _annotate_records(events),
            "markets": _annotate_records(markets),
            "source": "live",
            "data_status": "live_read_only",
            "live_snapshot_available": True,
        })
    except Exception as exc:
        return redact({
            "error": str(exc),
            "markets": None,
            "events": None,
            "source": "live_error",
            "data_status": "unavailable",
            "live_snapshot_available": False,
        })
    finally:
        if reader is not None:
            try:
                await reader.close()
            except Exception:
                pass


@router.get("/kalshi/orderbook/{ticker}")
async def kalshi_orderbook(ticker: str) -> dict[str, Any]:
    if not _credentials_present():
        return _unavailable_payload(
            reason="credentials_missing",
            orderbook=None,
            target_policy=_target_policy({}, fallback_ticker=ticker),
        )
    reader = None
    try:
        reader = KalshiRealReadOnly()
        book = await reader.get_orderbook(ticker)
        return redact({
            "orderbook": book,
            "source": "live",
            "data_status": "live_read_only",
            "live_snapshot_available": True,
            "target_policy": _target_policy({}, fallback_ticker=ticker),
        })
    except Exception as exc:
        return redact({
            "error": str(exc),
            "orderbook": None,
            "source": "live_error",
            "data_status": "unavailable",
            "live_snapshot_available": False,
            "target_policy": _target_policy({}, fallback_ticker=ticker),
        })
    finally:
        if reader is not None:
            try:
                await reader.close()
            except Exception:
                pass


@router.get("/kalshi/positions")
async def kalshi_positions() -> dict[str, Any]:
    if not _credentials_present():
        return _unavailable_payload(reason="credentials_missing", positions=None)
    reader = None
    try:
        reader = KalshiRealReadOnly()
        positions = await reader.get_positions()
        return redact({
            "positions": positions,
            "source": "live",
            "data_status": "live_read_only",
            "live_snapshot_available": True,
        })
    except Exception as exc:
        return redact({
            "error": str(exc),
            "positions": None,
            "source": "live_error",
            "data_status": "unavailable",
            "live_snapshot_available": False,
        })
    finally:
        if reader is not None:
            try:
                await reader.close()
            except Exception:
                pass


@router.get("/kalshi/orders")
async def kalshi_orders() -> dict[str, Any]:
    if not _credentials_present():
        return _unavailable_payload(reason="credentials_missing", orders=None)
    reader = None
    try:
        reader = KalshiRealReadOnly()
        orders = await reader.get_resting_orders()
        return redact({
            "orders": orders,
            "source": "live",
            "data_status": "live_read_only",
            "live_snapshot_available": True,
        })
    except Exception as exc:
        return redact({
            "error": str(exc),
            "orders": None,
            "source": "live_error",
            "data_status": "unavailable",
            "live_snapshot_available": False,
        })
    finally:
        if reader is not None:
            try:
                await reader.close()
            except Exception:
                pass


@router.get("/kalshi/fills")
async def kalshi_fills() -> dict[str, Any]:
    if not _credentials_present():
        return _unavailable_payload(reason="credentials_missing", fills=None)
    reader = None
    try:
        reader = KalshiRealReadOnly()
        fills = await reader.get_fills()
        return redact({
            "fills": fills,
            "source": "live",
            "data_status": "live_read_only",
            "live_snapshot_available": True,
        })
    except Exception as exc:
        return redact({
            "error": str(exc),
            "fills": None,
            "source": "live_error",
            "data_status": "unavailable",
            "live_snapshot_available": False,
        })
    finally:
        if reader is not None:
            try:
                await reader.close()
            except Exception:
                pass


@router.get("/strategies/scan")
async def strategies_scan(market_ticker: str = "MKT", contract_ticker: str = "MKT-YES") -> dict[str, Any]:
    """Run repo-derived strategies against a demo orderbook."""
    engine = ForecastEngine()
    book = OrderBook(
        market_ticker=market_ticker,
        contract_ticker=contract_ticker,
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=__import__("datetime").datetime.now(__import__("datetime").timezone.utc),
    )
    forecast = engine.forecast(
        market_ticker,
        contract_ticker,
        "Demo Event",
        contract_ticker,
        book,
    )
    scanner = StrategyScanner()
    results = scanner.scan(forecast, book)
    return {
        "market_ticker": market_ticker,
        "contract_ticker": contract_ticker,
        "source": "demo",
        "data_status": "synthetic_orderbook",
        "scan_results": [
            {
                "family": r.family,
                "edge_estimate": r.edge_estimate,
                "confidence": r.confidence,
                "liquidity_score": r.liquidity_score,
                "spread_score": r.spread_score,
                "settlement_risk_score": r.settlement_risk_score,
                "proposal_summary": r.proposal.model_dump() if r.proposal else None,
                "no_trade_reason": r.no_trade_reason,
            }
            for r in results
        ],
    }


@router.get("/firewall/rehearse", dependencies=[Depends(require_operator)])
async def firewall_rehearse(market_ticker: str = "MKT", contract_ticker: str = "MKT-YES") -> dict[str, Any]:
    """Run an autonomous live-cap rehearsal using real data if available."""
    if STATE.mode != AccountMode.AUTONOMOUS_LIVE_CAPPED:
        return {"status": "blocked", "reason": "Mode is not AUTONOMOUS_LIVE_CAPPED", "mode": STATE.mode.value}
    if not _credentials_present():
        return {"status": "blocked", "reason": "Kalshi credentials missing", "credentials_present": False}
    try:
        from execution.autonomous_path import AutonomousExecutionPath
        path = AutonomousExecutionPath()
        result = await path.rehearse_live_cap(market_ticker, contract_ticker)
        return redact(result)
    except Exception as exc:
        return {"status": "error", "reason": str(exc)}


@router.get("/firewall/blocked")
async def firewall_blocked() -> dict[str, Any]:
    """Count observed firewall rejection reasons from the local event log."""
    counts: dict[str, int] = {}
    scanned = 0
    if LOG_FILE.exists():
        with LOG_FILE.open(encoding="utf-8") as f:
            lines = f.readlines()[-1000:]
        for line in lines:
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, ValueError):
                continue
            if entry.get("component") != "firewall":
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
        "source": "local_log_derived",
        "window": "last_1000_log_lines",
    }


@router.get("/caps")
async def caps() -> dict[str, Any]:
    return {"caps": load_caps().model_dump(), "source": "configs/caps.json"}


@router.get("/live-submit/status")
async def live_submit_status() -> dict[str, Any]:
    path = Path("configs/live_submit.json")
    if not path.exists():
        return {"enabled": False, "file_present": False}
    try:
        data = json.loads(path.read_text())
        return {"enabled": data.get("enabled", False), "file_present": True}
    except Exception:
        return {"enabled": False, "file_present": True, "error": "invalid_json"}
