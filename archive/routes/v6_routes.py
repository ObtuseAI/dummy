"""Dashboard V6 routes for Dummy identity, real Kalshi data, and live firewall."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter, Depends

from core.config_loader import load_caps
from core.ontology import AccountMode, OrderBook, OrderBookLevel
from core.secret_guard import redact
from core.state import STATE
from dashboard.backend.operator_auth import require_operator
from forecasting.engine import ForecastEngine
from kalshi.live_data import KalshiRealReadOnly
from strategies.scan import StrategyScanner

router = APIRouter(prefix="/v6", tags=["v6"])

PROJECT_ROOT = Path("C:/src/engine/dummy")
ARTIFACTS = PROJECT_ROOT / "artifacts" / "dummy"
REQUIRED_ACKNOWLEDGEMENT = (
    "I approve real live Kalshi order submission through Dummy LiveBrokerFirewall only"
)


def _credentials_present() -> bool:
    key_id = os.environ.get("KALSHI_API_KEY_ID")
    pem = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM")
    pem_path = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH")
    return bool(key_id and (pem or pem_path))


@router.get("/identity")
async def identity() -> dict[str, Any]:
    return {
        "project": "Dummy",
        "previous_name": "Dumby",
        "root": str(PROJECT_ROOT),
        "milestone": "DUMMY_V6_REAL_KALSHI_CREDENTIAL_READONLY_PROOF_AND_LIVE_CAP_ARMING_REHEARSAL_V1",
        "compatibility_aliases": ["DumbyState = DummyState", "DumbyAdapter = DummyAdapter"],
        "historical_artifacts": str(PROJECT_ROOT / "artifacts" / "dumby"),
        "old_root_absent": not Path("C:/src/engine/dumby").exists(),
    }


@router.get("/path-integrity")
async def path_integrity() -> dict[str, Any]:
    return {
        "active_root": str(PROJECT_ROOT),
        "old_root_absent": not Path("C:/src/engine/dumby").exists(),
        "required_paths_present": all((PROJECT_ROOT / d).exists() for d in ["core", "kalshi", "live_firewall", "dashboard", "configs", "artifacts", "tests", "scripts"]),
    }


@router.get("/reports/{name}")
async def report(name: str) -> dict[str, Any]:
    path = ARTIFACTS / f"{name}.json"
    if not path.exists():
        return {"error": "not_found", "name": name}
    return json.loads(path.read_text())


@router.get("/kalshi/status")
async def kalshi_status() -> dict[str, Any]:
    return {
        "connected": _credentials_present() and STATE.mode != AccountMode.OFF,
        "credentials_present": _credentials_present(),
        "mode": STATE.mode.value,
        "kalshi_connected": STATE.kalshi_connected,
        "real_or_mock": "real" if _credentials_present() else "mock",
    }


@router.get("/kalshi/account")
async def kalshi_account() -> dict[str, Any]:
    if not _credentials_present():
        return {"error": "credentials_missing", "source": "mock"}
    try:
        reader = KalshiRealReadOnly()
        account = await reader.get_account_status()
        balance = await reader.get_balance()
        await reader.close()
        return redact({"account": account, "balance": balance, "source": "live"})
    except Exception as exc:
        return redact({"error": str(exc), "source": "live_error"})


@router.get("/kalshi/markets")
async def kalshi_markets() -> dict[str, Any]:
    if not _credentials_present():
        return {"markets": [], "events": [], "source": "mock"}
    try:
        reader = KalshiRealReadOnly()
        events = await reader.get_events()
        markets = await reader.get_markets()
        await reader.close()
        return redact({"events": events, "markets": markets, "source": "live"})
    except Exception as exc:
        return redact({"error": str(exc), "markets": [], "events": [], "source": "live_error"})


@router.get("/kalshi/orderbook/{ticker}")
async def kalshi_orderbook(ticker: str) -> dict[str, Any]:
    if not _credentials_present():
        book = OrderBook(
            market_ticker=ticker,
            contract_ticker=ticker,
            bids=[OrderBookLevel(price=48, size=100)],
            asks=[OrderBookLevel(price=52, size=100)],
            timestamp=datetime.now(timezone.utc),
        )
        return {"orderbook": book.model_dump(), "source": "mock"}
    try:
        reader = KalshiRealReadOnly()
        book = await reader.get_orderbook(ticker)
        await reader.close()
        return redact({"orderbook": book.model_dump(), "source": "live"})
    except Exception as exc:
        return redact({"error": str(exc), "source": "live_error"})


@router.get("/kalshi/positions")
async def kalshi_positions() -> dict[str, Any]:
    if not _credentials_present():
        return {"positions": [], "source": "mock"}
    try:
        reader = KalshiRealReadOnly()
        positions = await reader.get_positions()
        await reader.close()
        return redact({"positions": positions, "source": "live"})
    except Exception as exc:
        return redact({"error": str(exc), "positions": [], "source": "live_error"})


@router.get("/kalshi/orders")
async def kalshi_orders() -> dict[str, Any]:
    if not _credentials_present():
        return {"orders": [], "source": "mock"}
    try:
        reader = KalshiRealReadOnly()
        orders = await reader.get_resting_orders()
        await reader.close()
        return redact({"orders": orders, "source": "live"})
    except Exception as exc:
        return redact({"error": str(exc), "orders": [], "source": "live_error"})


@router.get("/kalshi/fills")
async def kalshi_fills() -> dict[str, Any]:
    if not _credentials_present():
        return {"fills": [], "source": "mock"}
    try:
        reader = KalshiRealReadOnly()
        fills = await reader.get_fills()
        await reader.close()
        return redact({"fills": fills, "source": "live"})
    except Exception as exc:
        return redact({"error": str(exc), "fills": [], "source": "live_error"})


@router.get("/endpoint-audit")
async def endpoint_audit() -> dict[str, Any]:
    if not _credentials_present():
        return {"source": "mock", "entries": [], "summary": {}}
    try:
        reader = KalshiRealReadOnly()
        await reader.get_account_status()
        await reader.get_balance()
        await reader.get_events()
        await reader.get_markets()
        summary = reader.http_summary()
        await reader.close()
        return redact({"source": "live", "entries": reader.request_audit_log, "summary": summary})
    except Exception as exc:
        return redact({"error": str(exc), "source": "live_error"})


@router.get("/strategies/scan")
async def strategies_scan(market_ticker: str = "MKT", contract_ticker: str = "MKT-YES") -> dict[str, Any]:
    engine = ForecastEngine()
    book = OrderBook(
        market_ticker=market_ticker,
        contract_ticker=contract_ticker,
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=datetime.now(timezone.utc),
    )
    forecast = engine.forecast(market_ticker, contract_ticker, "Demo Event", contract_ticker, book)
    scanner = StrategyScanner()
    results = scanner.scan(forecast, book)
    return {
        "market_ticker": market_ticker,
        "contract_ticker": contract_ticker,
        "source": "mock",
        "scan_results": [
            {
                "family": r.family,
                "market_ticker": r.market_ticker,
                "contract_ticker": r.contract_ticker,
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
    return {
        "blocked_reasons": [
            "live_submit_disabled",
            "mode",
            "kill_switch",
            "emergency_stop",
            "secrets",
            "unknown_adapter",
            "repo_bypass",
            "market_allowlist",
            "blocked_category",
            "compliance",
            "stale_data",
            "liquidity",
            "spread",
            "edge",
            "proof",
            "single_order_cap",
            "market_exposure_cap",
            "total_exposure_cap",
            "daily_loss_cap",
            "settlement_risk",
        ],
    }


@router.get("/caps")
async def caps() -> dict[str, Any]:
    return {"caps": load_caps().model_dump(), "source": "configs/caps.json"}


@router.get("/live-submit/status")
async def live_submit_status() -> dict[str, Any]:
    path = PROJECT_ROOT / "configs" / "live_submit.json"
    if not path.exists():
        return {"enabled": False, "file_present": False, "acknowledgement_present": False}
    try:
        data = json.loads(path.read_text())
    except Exception:
        return {"enabled": False, "file_present": True, "acknowledgement_present": False, "error": "invalid_json"}
    enabled = data.get("enabled") is True
    ack = data.get("explicit_acknowledgement") == REQUIRED_ACKNOWLEDGEMENT
    return {
        "enabled": enabled,
        "file_present": True,
        "acknowledgement_present": ack,
        "operator": data.get("operator"),
        "timestamp": data.get("timestamp"),
        "reason": data.get("reason"),
    }
