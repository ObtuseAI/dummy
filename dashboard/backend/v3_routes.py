from __future__ import annotations

import json, os
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException

from core.config_loader import load_caps
from core.ontology import AccountMode, ComplianceVerdict, EdgeEstimate, OrderBook, OrderBookLevel
from core.secret_guard import redact
from core.state import STATE
from forecasting.engine import ForecastEngine
from kalshi.live_data import KalshiLiveData
from live_firewall.exposure_tracker import ExposureTracker
from services.sqlite_store import get_orders, get_positions
from strategies.registry import STRATEGIES

router = APIRouter(prefix="/v3", tags=["v3"])

ARTIFACTS = Path("C:/src/engine/dummy/artifacts/repo_harvester")
DUMMY_ARTIFACTS = Path("C:/src/engine/dummy/artifacts/dummy")
LOG_FILE = Path("C:/src/engine/dummy/logs/dummy.jsonl")


def _load_artifact(filename: str) -> dict[str, Any]:
    path = ARTIFACTS / filename
    if path.exists():
        try:
            return json.loads(path.read_text())
        except Exception:
            pass
    return {}


def _safe_markets_fallback() -> dict[str, Any]:
    """Demo markets payload when live credentials are absent."""
    return {
        "events": [
            {
                "event_ticker": "WEATHER-NYC-RAIN",
                "title": "NYC Rain Forecast",
                "markets": [
                    {
                        "ticker": "WEATHER-NYC-RAIN-YES",
                        "title": "Will it rain in NYC?",
                        "status": "active",
                    }
                ],
            }
        ],
        "source": "mock",
    }


def _safe_orderbook_fallback(ticker: str) -> OrderBook:
    return OrderBook(
        market_ticker=ticker,
        contract_ticker=ticker,
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=datetime.now(timezone.utc),
    )


async def _kalshi_live_data() -> KalshiLiveData | None:
    if not os.environ.get("KALSHI_API_KEY_ID"):
        return None
    return KalshiLiveData()


@router.get("/adapters")
async def adapters() -> dict[str, Any]:
    """Accepted, pending, and rejected adapter summary."""
    plan = _load_artifact("adapter_plan_v3.json")
    rejected = _load_artifact("rejected_repo_report_v3.json")
    registry = _load_artifact("incorporation_registry.json")
    return {
        "accepted": [
            {
                "repo": p["repo"],
                "category": p.get("category"),
                "verdict": p["verdict"],
                "adapter": pl["adapter_name"],
                "emits_native_types": pl.get("emits_native_types", True),
            }
            for p in plan.get("plans", [])
            for pl in p.get("plans", [])
        ],
        "pending": registry.get("pending_tests", []),
        "rejected": [
            {
                "repo": r["repo"],
                "category": r.get("category"),
                "verdict": r["verdict"],
                "reasons": r.get("verdict_reasons", []),
            }
            for r in rejected.get("rejected", [])
        ],
        "counts": {
            "accepted": plan.get("accepted_count", 0),
            "direct_dependency": plan.get("direct_dependency_count", 0),
            "adapter_target": plan.get("adapter_target_count", 0),
            "reference_mine": plan.get("reference_mine_count", 0),
            "rejected": rejected.get("rejected_count", 0),
        },
    }


@router.get("/adapters/pending")
async def adapters_pending() -> dict[str, Any]:
    registry = _load_artifact("incorporation_registry.json")
    return {"pending": registry.get("pending_tests", [])}


@router.get("/adapters/rejected")
async def adapters_rejected() -> dict[str, Any]:
    rejected = _load_artifact("rejected_repo_report_v3.json")
    return {
        "rejected": [
            {
                "repo": r["repo"],
                "category": r.get("category"),
                "verdict": r["verdict"],
                "reasons": r.get("verdict_reasons", []),
            }
            for r in rejected.get("rejected", [])
        ],
        "count": rejected.get("rejected_count", 0),
    }


@router.get("/kalshi/status")
async def kalshi_status() -> dict[str, Any]:
    """Live Kalshi connection status, balance, positions, resting orders, fills."""
    live = await _kalshi_live_data()
    if live is None:
        return redact(
            {
                "connected": False,
                "mode": STATE.mode.value,
                "api_key_id_present": False,
                "balance_cents": 0,
                "positions": [],
                "resting_orders": [],
                "fills": [],
                "source": "mock",
            }
        )
    try:
        balance = await live.get_account_balance()
        positions = await live.get_positions()
        resting = await live.get_resting_orders()
        fills = await live.get_fills()
        await live.close()
        return redact(
            {
                "connected": True,
                "mode": STATE.mode.value,
                "api_key_id_present": True,
                "balance_cents": balance.get("balance_cents", 0),
                "positions": positions,
                "resting_orders": resting,
                "fills": fills,
                "source": "live",
            }
        )
    except Exception as exc:
        return redact(
            {
                "connected": False,
                "mode": STATE.mode.value,
                "api_key_id_present": True,
                "error": str(exc),
                "balance_cents": 0,
                "positions": [],
                "resting_orders": [],
                "fills": [],
                "source": "live_error",
            }
        )


@router.get("/kalshi/markets")
async def kalshi_markets() -> dict[str, Any]:
    """Live markets/events, cached or mocked if no credentials."""
    live = await _kalshi_live_data()
    if live is None:
        return redact(_safe_markets_fallback())
    try:
        events = await live.get_events()
        await live.close()
        return redact({"events": events, "source": "live"})
    except Exception as exc:
        return redact({"events": _safe_markets_fallback()["events"], "source": "live_error", "error": str(exc)})


@router.get("/kalshi/orderbook/{ticker}")
async def kalshi_orderbook(ticker: str) -> dict[str, Any]:
    """Live orderbook for a Kalshi contract ticker."""
    live = await _kalshi_live_data()
    if live is None:
        book = _safe_orderbook_fallback(ticker)
        return redact({"orderbook": book.model_dump(), "source": "mock"})
    try:
        book = await live.get_orderbook(ticker)
        await live.close()
        return redact({"orderbook": book.model_dump(), "source": "live"})
    except Exception as exc:
        return redact(
            {
                "orderbook": _safe_orderbook_fallback(ticker).model_dump(),
                "source": "live_error",
                "error": str(exc),
            }
        )


@router.get("/strategies/candidates")
async def strategies_candidates() -> dict[str, Any]:
    """Repo-derived strategy candidates from the extraction report."""
    report = _load_artifact("strategy_extraction_report_v1.json")
    registered = [s.__class__.__name__ for s in STRATEGIES]
    return {
        "registered_strategies": registered,
        "candidates": report.get("candidates", []),
        "candidate_count": report.get("candidate_count", 0),
    }


@router.get("/proposed-trades")
async def proposed_trades(
    market_ticker: str = "WEATHER-NYC-RAIN",
    contract_ticker: str = "WEATHER-NYC-RAIN-YES",
) -> dict[str, Any]:
    """Current proposed trades generated by repo-derived strategies."""
    engine = ForecastEngine()
    book = OrderBook(
        market_ticker=market_ticker,
        contract_ticker=contract_ticker,
        bids=[OrderBookLevel(price=48, size=100)],
        asks=[OrderBookLevel(price=52, size=100)],
        timestamp=datetime.now(timezone.utc),
    )
    forecast = engine.forecast(
        market_ticker,
        contract_ticker,
        "Demo Event",
        "Yes",
        book,
    )
    proposals: list[dict[str, Any]] = []
    for strategy in STRATEGIES:
        try:
            proposal = strategy.evaluate(forecast, book)
            if proposal is not None:
                proposals.append(proposal.model_dump())
        except Exception:
            continue
    return {"market_ticker": market_ticker, "contract_ticker": contract_ticker, "proposals": proposals}


@router.get("/blocked-orders")
async def blocked_orders() -> dict[str, Any]:
    """Blocked order reasons from repo-harvester findings and recent firewall rejections."""
    bypass = _load_artifact("firewall_bypass_scan_report_v1.json")
    reasons: list[dict[str, Any]] = []
    for hit in bypass.get("direct_order_repos", []):
        reasons.append({"repo": hit["repo"], "category": "direct_order_bypass", "details": hit.get("files", [])})
    for hit in bypass.get("secret_risk_repos", []):
        reasons.append({"repo": hit["repo"], "category": "secret_risk", "details": hit.get("files", [])})

    recent_log_reasons: list[dict[str, Any]] = []
    if LOG_FILE.exists():
        with LOG_FILE.open() as f:
            lines = f.readlines()[-200:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            msg = entry.get("message", "")
            if entry.get("component") == "firewall" and ("rejection" in msg.lower() or "rejected" in msg.lower()):
                recent_log_reasons.append(
                    {
                        "timestamp": entry.get("timestamp"),
                        "category": entry.get("extra", {}).get("rejected_by", "firewall"),
                        "reason": msg,
                        "proposal_id": entry.get("extra", {}).get("proposal_id"),
                    }
                )

    return {
        "static_reasons": reasons,
        "recent_firewall_rejections": recent_log_reasons,
        "count": len(reasons) + len(recent_log_reasons),
    }


@router.get("/firewall/verdicts")
async def firewall_verdicts(limit: int = 100) -> dict[str, Any]:
    """Recent firewall verdicts parsed from logs."""
    verdicts: list[dict[str, Any]] = []
    if LOG_FILE.exists():
        with LOG_FILE.open() as f:
            lines = f.readlines()[-limit:]
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                entry = json.loads(line)
            except Exception:
                continue
            msg = entry.get("message", "")
            if entry.get("component") == "firewall":
                verdicts.append(
                    {
                        "timestamp": entry.get("timestamp"),
                        "level": entry.get("level"),
                        "message": msg,
                        "rejected_by": entry.get("extra", {}).get("rejected_by"),
                        "proposal_id": entry.get("extra", {}).get("proposal_id"),
                        "allow": "rejection" not in msg.lower() and "rejected" not in msg.lower(),
                    }
                )
    return {"verdicts": verdicts, "count": len(verdicts)}


@router.get("/caps")
async def caps() -> dict[str, Any]:
    """Current caps; read-only from configs/caps.json."""
    return {"caps": load_caps().model_dump(), "source": "configs/caps.json"}


@router.get("/exposure")
async def exposure() -> dict[str, Any]:
    """Current positions and exposure computed from the SQLite store."""
    positions = await get_positions()
    tracker = ExposureTracker()
    for p in positions:
        from core.ontology import Position

        tracker.update_position(
            Position(
                market_ticker=p["market_ticker"],
                contract_ticker=p.get("contract_ticker", ""),
                side=p.get("side", ""),
                quantity=int(p.get("quantity", 0)),
                avg_price_cents=int(p.get("avg_price_cents", 0)),
                unrealized_pnl_cents=int(p.get("unrealized_pnl_cents", 0)),
            )
        )
    orders = await get_orders()
    return {
        "positions": positions,
        "orders": orders,
        "total_exposure_cents": tracker.total_exposure_cents(),
        "open_markets": tracker.open_markets(),
        "open_order_count": tracker.open_order_count(),
        "mode": STATE.mode.value,
    }
