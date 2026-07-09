"""Read-only pre-submit validation against live Kalshi market metadata.

Catches avoidable broker rejections (closed market, off-tick price, dead
ticker, imminent close, empty book) before any authority is armed. Uses only
public, unauthenticated GET endpoints; never POSTs, never mutates canonical
artifacts, and works with an injected fetcher for tests.
"""
from __future__ import annotations

import json
import os
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Callable

DEFAULT_CLOSE_BUFFER_MINUTES = 60

# A LIMIT order body must carry exactly one side-specific price field.
_REQUIRED_ORDER_FIELDS = ("ticker", "side", "action", "type", "count", "client_order_id")


def _public_base() -> str:
    base = os.environ.get("KALSHI_API_BASE", "https://api.elections.kalshi.com").rstrip("/")
    version = os.environ.get("KALSHI_API_VERSION", "trade-api/v2").strip("/")
    return f"{base}/{version}"


def default_fetch_market(ticker: str) -> dict[str, Any]:
    """Fetch public market metadata (no auth, GET only)."""
    import httpx

    response = httpx.get(f"{_public_base()}/markets/{ticker}", timeout=10)
    response.raise_for_status()
    data = response.json()
    market = data.get("market", data)
    return market if isinstance(market, dict) else {}


def default_fetch_orderbook(ticker: str) -> dict[str, Any]:
    """Fetch public orderbook (no auth, GET only)."""
    import httpx

    response = httpx.get(f"{_public_base()}/markets/{ticker}/orderbook", params={"depth": 5}, timeout=10)
    response.raise_for_status()
    data = response.json()
    ob = data.get("orderbook") or data.get("orderbook_fp") or {}
    return ob if isinstance(ob, dict) else {}


@dataclass
class PresubmitReport:
    ticker: str
    passed: bool
    blockers: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    checks: dict[str, Any] = field(default_factory=dict)
    created_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())

    def to_dict(self) -> dict[str, Any]:
        return {
            "report_name": "KALSHI_PRESUBMIT_VALIDATION_REPORT",
            "ticker": self.ticker,
            "passed": self.passed,
            "blockers": self.blockers,
            "warnings": self.warnings,
            "checks": self.checks,
            "read_only": True,
            "broker_write_calls": 0,
            "created_at": self.created_at,
        }


def _parse_iso(value: Any) -> datetime | None:
    if not isinstance(value, str) or not value.strip():
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def validate_order_body_schema(order: dict[str, Any]) -> list[str]:
    """Static schema check for a trade-api/v2 limit-order body."""
    errors: list[str] = []
    for key in _REQUIRED_ORDER_FIELDS:
        if not order.get(key):
            errors.append(f"missing_field:{key}")
    if order.get("type") != "limit":
        errors.append("type_must_be_limit")
    if order.get("side") not in ("yes", "no"):
        errors.append("side_must_be_yes_or_no")
    if order.get("action") not in ("buy", "sell"):
        errors.append("action_must_be_buy_or_sell")
    has_yes = isinstance(order.get("yes_price"), int)
    has_no = isinstance(order.get("no_price"), int)
    if has_yes == has_no:
        errors.append("exactly_one_of_yes_price_or_no_price_required")
    if "price" in order:
        errors.append("flat_price_field_not_in_v2_schema")
    price = order.get("yes_price") if has_yes else order.get("no_price")
    if isinstance(price, int) and not (1 <= price <= 99):
        errors.append("price_out_of_1_99_cents")
    count = order.get("count")
    if not isinstance(count, int) or count < 1:
        errors.append("count_must_be_positive_int")
    return errors


def presubmit_validate(
    ticker: str,
    price_cents: int,
    count: int,
    side: str = "yes",
    order_body: dict[str, Any] | None = None,
    close_buffer_minutes: int = DEFAULT_CLOSE_BUFFER_MINUTES,
    fetch_market: Callable[[str], dict[str, Any]] | None = None,
    fetch_orderbook: Callable[[str], dict[str, Any]] | None = None,
    now: datetime | None = None,
) -> PresubmitReport:
    """Run every read-only check that can predict a broker rejection."""
    fetch_market = fetch_market or default_fetch_market
    fetch_orderbook = fetch_orderbook or default_fetch_orderbook
    now = now or datetime.now(timezone.utc)
    report = PresubmitReport(ticker=ticker, passed=False)

    try:
        market = fetch_market(ticker)
    except Exception as exc:
        report.blockers.append(f"market_fetch_failed:{type(exc).__name__}")
        report.checks["market_found"] = False
        return report

    if not market:
        report.blockers.append("market_not_found")
        report.checks["market_found"] = False
        return report
    report.checks["market_found"] = True

    status = str(market.get("status", "")).lower()
    report.checks["market_status"] = status
    if status not in ("active", "open"):
        report.blockers.append(f"market_status_not_tradable:{status or 'unknown'}")

    close_time = _parse_iso(market.get("close_time"))
    report.checks["close_time"] = market.get("close_time")
    if close_time is None:
        report.warnings.append("close_time_unparseable")
    elif close_time <= now:
        report.blockers.append("market_already_closed")
    elif close_time <= now + timedelta(minutes=close_buffer_minutes):
        report.blockers.append(f"market_closes_within_{close_buffer_minutes}_minutes")

    tick = market.get("tick_size") or market.get("tick_size_cents") or 1
    try:
        tick = int(tick)
    except Exception:
        tick = 1
    report.checks["tick_size_cents"] = tick
    if not (1 <= price_cents <= 99):
        report.blockers.append("price_out_of_1_99_cents")
    elif tick > 0 and price_cents % tick != 0:
        report.blockers.append(f"price_off_tick:{price_cents}%{tick}")

    if count < 1:
        report.blockers.append("count_must_be_positive")
    report.checks["notional_cents"] = price_cents * count

    try:
        orderbook = fetch_orderbook(ticker)
        yes_levels = orderbook.get("yes") or orderbook.get("yes_dollars") or []
        no_levels = orderbook.get("no") or orderbook.get("no_dollars") or []
        report.checks["orderbook_yes_levels"] = len(yes_levels)
        report.checks["orderbook_no_levels"] = len(no_levels)
        if not yes_levels and not no_levels:
            report.warnings.append("orderbook_empty_zero_liquidity_fill_unlikely")
    except Exception as exc:
        report.warnings.append(f"orderbook_fetch_failed:{type(exc).__name__}")

    if order_body is not None:
        schema_errors = validate_order_body_schema(order_body)
        report.checks["order_body_schema_errors"] = schema_errors
        report.blockers.extend(f"order_body:{e}" for e in schema_errors)

    report.passed = not report.blockers
    return report


def write_presubmit_report(report: PresubmitReport, out_dir: Path | None = None) -> Path:
    """Persist to a new timestamped file under the evidence root."""
    root = Path(os.environ.get("DUMMY_EVIDENCE_ROOT", "artifacts/dummy"))
    out_dir = out_dir or (root / "presubmit_checks")
    out_dir.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%f")
    path = out_dir / f"KALSHI_PRESUBMIT_VALIDATION_REPORT_{timestamp}.json"
    path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path
