from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from fastapi import APIRouter

from autonomy.target_policy import is_data_only_target
from core.config_loader import load_caps
from core.ontology import OrderBook, OrderBookLevel
from core.secret_guard import redact
from core.state import STATE
from forecasting.engine import ForecastEngine
from kalshi.live_data import KalshiLiveData
from live_firewall.exposure_tracker import get_persistent_exposure_tracker
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


def _extract_list(payload: Any, key: str) -> list[dict[str, Any]] | None:
    value = payload.get(key) if isinstance(payload, dict) else payload
    return value if isinstance(value, list) else None


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


def _annotate_events(events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    annotated: list[dict[str, Any]] = []
    for raw_event in events:
        if not isinstance(raw_event, dict):
            continue
        event = dict(raw_event)
        event_ticker = str(event.get("event_ticker") or event.get("ticker") or "")
        raw_markets = event.get("markets")
        if isinstance(raw_markets, list):
            event["markets"] = [
                {**market, "target_policy": _target_policy(market, fallback_ticker=event_ticker)}
                for market in raw_markets
                if isinstance(market, dict)
            ]
        event["target_policy"] = _target_policy(event)
        annotated.append(event)
    return annotated


async def _kalshi_live_data() -> KalshiLiveData | None:
    if not _credentials_present():
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
            _unavailable_payload(
                reason="credentials_missing",
                connected=False,
                mode=STATE.mode.value,
                api_key_id_present=False,
                credentials_present=False,
                balance_cents=None,
                positions=None,
                resting_orders=None,
                fills=None,
            )
        )
    try:
        balance = await live.get_account_balance()
        positions = _extract_list(await live.get_positions(), "positions")
        resting = _extract_list(await live.get_resting_orders(), "orders")
        fills = _extract_list(await live.get_fills(), "fills")
        complete = (
            isinstance(balance, dict)
            and balance.get("account_loaded") is True
            and positions is not None
            and resting is not None
            and fills is not None
        )
        return redact(
            {
                "connected": True,
                "mode": STATE.mode.value,
                "api_key_id_present": True,
                "credentials_present": True,
                "balance_cents": balance.get("balance_cents") if complete else None,
                "positions": positions,
                "resting_orders": resting,
                "fills": fills,
                "source": "live" if complete else "live_incomplete",
                "data_status": "live_read_only" if complete else "live_read_only_incomplete",
                "live_snapshot_available": complete,
            }
        )
    except Exception as exc:
        return redact(
            {
                "connected": False,
                "mode": STATE.mode.value,
                "api_key_id_present": True,
                "credentials_present": True,
                "error": str(exc),
                "balance_cents": None,
                "positions": None,
                "resting_orders": None,
                "fills": None,
                "source": "live_error",
                "data_status": "unavailable",
                "live_snapshot_available": False,
            }
        )
    finally:
        try:
            await live.close()
        except Exception:
            pass


@router.get("/kalshi/markets")
async def kalshi_markets() -> dict[str, Any]:
    """Live read-only markets/events; unavailable is never replaced by demo rows."""
    live = await _kalshi_live_data()
    if live is None:
        return redact(_unavailable_payload(reason="credentials_missing", events=None))
    try:
        events = _extract_list(await live.get_events(), "events")
        if events is None:
            return redact({
                "events": None,
                "source": "live_incomplete",
                "data_status": "live_read_only_incomplete",
                "live_snapshot_available": False,
            })
        return redact({
            "events": _annotate_events(events),
            "source": "live",
            "data_status": "live_read_only",
            "live_snapshot_available": True,
        })
    except Exception as exc:
        return redact({
            "events": None,
            "source": "live_error",
            "data_status": "unavailable",
            "live_snapshot_available": False,
            "error": str(exc),
        })
    finally:
        try:
            await live.close()
        except Exception:
            pass


@router.get("/kalshi/orderbook/{ticker}")
async def kalshi_orderbook(ticker: str) -> dict[str, Any]:
    """Live orderbook for a Kalshi contract ticker."""
    live = await _kalshi_live_data()
    if live is None:
        return redact(_unavailable_payload(
            reason="credentials_missing",
            orderbook=None,
            target_policy=_target_policy({}, fallback_ticker=ticker),
        ))
    try:
        book = await live.get_orderbook(ticker)
        return redact({
            "orderbook": book.model_dump(),
            "source": "live",
            "data_status": "live_read_only",
            "live_snapshot_available": True,
            "target_policy": _target_policy({}, fallback_ticker=ticker),
        })
    except Exception as exc:
        return redact(
            {
                "orderbook": None,
                "source": "live_error",
                "data_status": "unavailable",
                "live_snapshot_available": False,
                "target_policy": _target_policy({}, fallback_ticker=ticker),
                "error": str(exc),
            }
        )
    finally:
        try:
            await live.close()
        except Exception:
            pass


@router.get("/strategies/candidates")
async def strategies_candidates() -> dict[str, Any]:
    """Repo-derived strategy candidates from the extraction report."""
    report = _load_artifact("strategy_extraction_report_v1.json")
    registered = [s.__class__.__name__ for s in STRATEGIES]
    candidates = []
    for candidate in report.get("candidates", []):
        if not isinstance(candidate, dict):
            continue
        sample_size = candidate.get("sample_size")
        try:
            thin_data = sample_size is None or int(sample_size) < 30
        except (TypeError, ValueError):
            thin_data = True
        candidates.append({
            **candidate,
            "validation_status": candidate.get("validation_status", "UNKNOWN"),
            "sample_size": sample_size,
            "thin_data": thin_data,
            "forecast_quality": candidate.get("forecast_quality"),
        })
    return {
        "registered_strategies": registered,
        "candidates": candidates,
        "candidate_count": len(candidates),
    }


@router.get("/proposed-trades")
async def proposed_trades(
    market_ticker: str = "DEMO-SPORTS-MATCHUP",
    contract_ticker: str = "DEMO-SPORTS-MATCHUP-HOME",
) -> dict[str, Any]:
    """Demo proposed trades generated against an explicitly synthetic book."""
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
    return {
        "market_ticker": market_ticker,
        "contract_ticker": contract_ticker,
        "proposals": proposals,
        "source": "demo",
        "data_status": "synthetic_orderbook",
    }


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
    """Canonical durable live-risk exposure, including the rolling-hour count."""
    tracker = get_persistent_exposure_tracker()
    healthy = tracker.state_healthy
    return {
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
        "state_status": "ready" if healthy else "unavailable",
        "source": "runtime/live_exposure_state.json",
        "mode": STATE.mode.value,
    }
