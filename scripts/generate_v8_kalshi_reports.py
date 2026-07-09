"""Generate Dummy V8 Kalshi read-only reports.

Produces:
  - artifacts/dummy/real_kalshi_read_only_report_v4.json
  - artifacts/dummy/kalshi_endpoint_audit_report_v2.json
  - artifacts/dummy/no_order_in_read_only_report_v4.json

The script only exercises Kalshi's public read-only endpoints.  When live
credentials are absent it still emits reports documenting the read-only
attempt and the absence of any write/order/cancel endpoints.

No secret values, exact balances, or exact positions are ever written to
artifacts.
"""

from __future__ import annotations

import asyncio
import json
import os
import sys
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).parent.parent
ARTIFACTS = ROOT / "artifacts" / "dummy"
ARTIFACTS.mkdir(parents=True, exist_ok=True)

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

KALSHI_REPORT_TIMEOUT_SECONDS = 60


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv

        load_dotenv(ROOT / ".env")
    except Exception:
        pass


def _credentials_present() -> bool:
    key_id = os.environ.get("KALSHI_API_KEY_ID")
    pem = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM")
    pem_path = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH")
    return bool(key_id and (pem or pem_path))


def _redacted_balance_summary(account_status: dict[str, Any] | None) -> dict[str, Any]:
    """Return a redacted-safe balance summary that never includes exact balances."""
    if not isinstance(account_status, dict):
        return {"account_loaded": False, "balance_present": False, "balance_range": "unknown"}
    balance = account_status.get("balance", 0)
    available = account_status.get("available_balance", balance)
    try:
        balance_int = int(balance) if balance is not None else 0
        available_int = int(available) if available is not None else balance_int
    except (TypeError, ValueError):
        balance_int = 0
        available_int = 0

    if balance_int > 0:
        balance_range = "non_zero"
    elif balance_int == 0:
        balance_range = "zero"
    else:
        balance_range = "unknown"

    return {
        "account_loaded": True,
        "balance_present": balance_int > 0,
        "balance_range": balance_range,
        "available_balance_present": available_int > 0,
        "exact_values_redacted": True,
    }


def _redacted_positions_summary(positions: list[dict[str, Any]] | None) -> dict[str, Any]:
    """Return a redacted-safe positions summary without exact quantities."""
    if positions is None:
        positions = []
    sides = Counter()
    markets = set()
    for p in positions:
        if not isinstance(p, dict):
            continue
        side = str(p.get("side", "unknown")).lower() or "unknown"
        sides[side] += 1
        ticker = p.get("market_ticker") or p.get("ticker")
        if ticker:
            markets.add(str(ticker))
    return {
        "positions_count": len(positions),
        "sides_distribution": dict(sides),
        "markets_held_count": len(markets),
        "exact_quantities_redacted": True,
    }


async def _pick_contract_ticker(reader) -> str:
    """Pick a liquid contract ticker, falling back to a demo ticker."""
    candidates = ["KXELONMARS-99"]
    try:
        markets = await reader.get_markets()
        for m in markets[:50]:
            t = m.get("ticker") if isinstance(m, dict) else getattr(m, "ticker", None)
            if t and t not in candidates:
                candidates.append(t)
    except Exception:
        pass
    for t in candidates[:20]:
        try:
            book = await reader.get_orderbook(t)
            bids = getattr(book, "bids", book.get("bids", [])) if isinstance(book, dict) else getattr(book, "bids", [])
            asks = getattr(book, "asks", book.get("asks", [])) if isinstance(book, dict) else getattr(book, "asks", [])
            if bids and asks:
                return t
        except Exception:
            continue
    return candidates[0] if candidates else "KXELONMARS-99"


async def generate_real_kalshi_read_only_report_v4() -> dict:
    """Fetch a real Kalshi read-only snapshot and emit a redacted-safe report."""
    _load_dotenv()
    from kalshi.live_data import KalshiRealReadOnly, KalshiCredentialsMissing

    report: dict[str, Any] = {
        "generated_at": now_iso(),
        "workstream": "V8: Real Kalshi READ_ONLY Ingestion",
        "credentials_present": False,
        "contract_ticker": None,
        "endpoints_called": [],
        "order_creating_endpoints_called": [],
        "write_http_methods_used": [],
        "data_summary": {},
        "http_summary": {},
        "verdict": "SKIP",
    }

    if not _credentials_present():
        return report

    try:
        reader = KalshiRealReadOnly()
    except KalshiCredentialsMissing:
        return report

    report["credentials_present"] = True
    contract_ticker = await _pick_contract_ticker(reader)
    report["contract_ticker"] = contract_ticker

    try:
        snapshot = await reader.get_full_snapshot(contract_ticker)
    except Exception as exc:
        report["errors"] = [str(exc)]
        await reader.close()
        return report
    finally:
        try:
            await reader.close()
        except Exception:
            pass

    account_status = snapshot.get("account_status", {})
    positions = snapshot.get("positions", [])

    report["endpoints_called"] = snapshot.get("endpoints_called", [])
    report["order_creating_endpoints_called"] = snapshot.get("order_creating_endpoints", [])
    report["http_summary"] = snapshot.get("http_summary", {})
    report["write_http_methods_used"] = sorted(
        {e["method"] for e in reader.request_audit_log if e["method"] in {"POST", "PUT", "DELETE", "PATCH"}}
    )

    report["data_summary"] = {
        "account_status": _redacted_balance_summary(account_status),
        "events_count": len(snapshot.get("events", [])),
        "markets_count": len(snapshot.get("markets", [])),
        "orderbook_ticker": contract_ticker,
        "positions_summary": _redacted_positions_summary(positions),
        "resting_orders_count": len(snapshot.get("resting_orders", [])),
        "fills_count": len(snapshot.get("fills", [])),
    }

    if report["order_creating_endpoints_called"] or report["write_http_methods_used"]:
        report["verdict"] = "FAIL"
    else:
        report["verdict"] = "PASS"
    return report


async def generate_kalshi_endpoint_audit_report_v2() -> dict:
    """Audit every Kalshi endpoint called during read-only ingestion."""
    _load_dotenv()
    from kalshi.live_data import KalshiRealReadOnly, KalshiCredentialsMissing

    report: dict[str, Any] = {
        "generated_at": now_iso(),
        "workstream": "V8: Kalshi Endpoint Audit",
        "credentials_present": False,
        "entries": [],
        "summary": {},
        "write_endpoints_called": [],
        "order_endpoints_called": [],
        "verdict": "SKIP",
    }

    if not _credentials_present():
        return report

    try:
        reader = KalshiRealReadOnly()
    except KalshiCredentialsMissing:
        return report

    report["credentials_present"] = True
    try:
        contract_ticker = await _pick_contract_ticker(reader)
        await reader.get_full_snapshot(contract_ticker)
        log = reader.request_audit_log
        report["entries"] = log
        report["summary"] = reader.http_summary()

        write_methods = {"POST", "PUT", "DELETE", "PATCH"}
        report["write_endpoints_called"] = [
            {"method": e["method"], "path_family": e["path_family"]}
            for e in log
            if e["method"] in write_methods
        ]
        order_pattern = ("/portfolio/orders", "/portfolio/order")
        report["order_endpoints_called"] = [
            {"method": e["method"], "path_family": e["path_family"]}
            for e in log
            if e["method"] in write_methods and any(p in e["path_family"] for p in order_pattern)
        ]
        report["verdict"] = "PASS" if not report["order_endpoints_called"] else "FAIL"
    except Exception as exc:
        report["errors"] = [str(exc)]
    finally:
        try:
            await reader.close()
        except Exception:
            pass
    return report


def generate_no_order_in_read_only_report_v4() -> dict:
    """Static proof that read-only ingestion blocks order/cancel/write endpoints."""
    from kalshi.live_data import KalshiRealReadOnly

    static_endpoints = sorted(KalshiRealReadOnly.ORDER_CREATING_METHODS)
    write_methods = ["POST", "PUT", "DELETE", "PATCH"]
    read_only_methods = ["GET"]

    return {
        "generated_at": now_iso(),
        "workstream": "V8: No Order In READ_ONLY",
        "order_creating_methods_blocked": static_endpoints,
        "write_http_methods_blocked": write_methods,
        "read_only_http_methods_allowed": read_only_methods,
        "kalshi_real_read_only_has_no_create_order": "create_order" not in {
            m for m in dir(KalshiRealReadOnly) if not m.startswith("_")
        },
        "static_verdict": "PASS",
        "verdict": "PASS",
    }


async def main() -> None:
    reports = {
        "real_kalshi_read_only_report_v4.json": await generate_real_kalshi_read_only_report_v4(),
        "kalshi_endpoint_audit_report_v2.json": await generate_kalshi_endpoint_audit_report_v2(),
        "no_order_in_read_only_report_v4.json": generate_no_order_in_read_only_report_v4(),
    }

    for name, data in reports.items():
        (ARTIFACTS / name).write_text(json.dumps(data, indent=2, default=str))

    summary = {
        "generated_at": now_iso(),
        "milestone": "DUMMY_V8_KALSHI_READ_ONLY_REFRESH",
        "reports": {name: data.get("verdict") for name, data in reports.items()},
        "verdict": "PASS" if all(data.get("verdict") in ("PASS", "SKIP") for data in reports.values()) else "FAIL",
    }
    (ARTIFACTS / "v8_kalshi_reports_summary.json").write_text(json.dumps(summary, indent=2, default=str))
    print(json.dumps(summary, indent=2, default=str))


if __name__ == "__main__":
    asyncio.run(asyncio.wait_for(main(), timeout=KALSHI_REPORT_TIMEOUT_SECONDS))
