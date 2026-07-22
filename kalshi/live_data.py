from __future__ import annotations

import asyncio
import os
from datetime import datetime, timezone
from typing import Any, Optional, Set

from core.logger import logger
from core.secret_guard import redact
from kalshi.client import KalshiClient

KALSHI_READ_ONLY_TIMEOUT_SECONDS = 45


class KalshiCredentialsMissing(Exception):
    """Raised when Kalshi credentials are not configured."""
    pass


class KalshiLiveData:
    """Read-only live Kalshi data wrapper with secret redaction."""

    name: str = "kalshi_live_data"

    def __init__(self, client: KalshiClient | None = None):
        self.client = client or KalshiClient()

    def _log(self, method: str, extra: dict[str, Any] | None = None):
        safe = redact(extra or {})
        logger.info(f"KalshiLiveData.{method}", extra={"component": self.name, "method": method, **safe})

    async def get_events(self) -> dict[str, Any]:
        self._log("get_events")
        return redact(await self.client.get_events())

    async def get_markets(self) -> dict[str, Any]:
        self._log("get_markets")
        return redact(await self.client.get_markets())

    async def get_orderbook(self, ticker: str):
        self._log("get_orderbook", {"ticker": ticker})
        return await self.client.get_orderbook(ticker)

    async def get_account_balance(self) -> dict[str, Any]:
        self._log("get_account_balance")
        account = await self.client.get_account()
        balance = account.get("balance", 0) if isinstance(account, dict) else 0
        return redact({
            "balance_cents": balance,
            "account_loaded": isinstance(account, dict),
            "api_key_id_present": bool(os.environ.get("KALSHI_API_KEY_ID")),
        })

    async def get_positions(self) -> dict[str, Any]:
        self._log("get_positions")
        return redact(await self.client.get_positions())

    async def get_resting_orders(self) -> dict[str, Any]:
        self._log("get_resting_orders")
        return redact(await self.client.get_orders())

    async def get_fills(self) -> dict[str, Any]:
        self._log("get_fills")
        return redact(await self.client.get_fills())

    async def close(self):
        await self.client.close()

    def endpoint_coverage(self) -> list[str]:
        return [
            "get_events",
            "get_markets",
            "get_orderbook",
            "get_account_balance",
            "get_positions",
            "get_resting_orders",
            "get_fills",
        ]


class KalshiRealReadOnly:
    """Explicit real Kalshi READ_ONLY ingestion wrapper.

    Loads credentials from the environment, connects to Kalshi, and exposes
    read-only methods for account, events, markets, orderbook, positions,
    resting orders, and fills.  Tracks every endpoint called so that tests
    can prove no order-creating endpoint is invoked in READ_ONLY mode.
    """

    name: str = "kalshi_real_read_only"
    ORDER_CREATING_METHODS: Set[str] = {"create_order", "cancel_order", "post /orders", "put /orders", "post /order", "put /order"}

    def __init__(self, client: Optional[KalshiClient] = None):
        key_id = os.environ.get("KALSHI_API_KEY_ID")
        pem = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM") or os.environ.get(
            "KALSHI_API_PRIVATE_KEY"
        )
        pem_path = os.environ.get("KALSHI_API_PRIVATE_KEY_PEM_PATH")
        if not key_id or (not pem and not pem_path):
            raise KalshiCredentialsMissing(
                "KALSHI_API_KEY_ID and KALSHI_API_PRIVATE_KEY_PEM/PATH required"
            )
        self.client = client or KalshiClient()
        self._endpoints: Set[str] = set()

    def _track(self, endpoint: str):
        self._endpoints.add(endpoint)

    def endpoints_called(self) -> Set[str]:
        return set(self._endpoints)

    def order_creating_endpoints_called(self) -> Set[str]:
        return {e for e in self._endpoints if any(o in e.lower() for o in self.ORDER_CREATING_METHODS)}

    @property
    def request_audit_log(self) -> list[dict[str, Any]]:
        return list(getattr(self.client, "request_audit_log", []))

    def http_summary(self) -> dict[str, Any]:
        log = self.request_audit_log
        return {
            "total_requests": len(log),
            "methods": sorted({e["method"] for e in log}),
            "path_families": sorted({e["path_family"] for e in log}),
            "status_classes": sorted({e["status_class"] for e in log}),
            "entries": log,
        }

    async def get_account_status(self) -> dict[str, Any]:
        self._track("GET /portfolio/balance")
        raw = await self.client.get_account()
        return redact(raw)

    async def get_balance(self) -> dict[str, Any]:
        self._track("GET /portfolio/balance")
        account = await self.client.get_account()
        if not isinstance(account, dict):
            account = {}
        return redact({
            "balance_cents": account.get("balance", 0),
            "available_cents": account.get("available_balance", 0),
            "account_loaded": True,
        })

    async def get_events(self) -> list[dict[str, Any]]:
        self._track("GET /events")
        raw = await self.client.get_events()
        events = raw.get("events", []) if isinstance(raw, dict) else raw
        return redact(events)

    async def get_markets(self) -> list[dict[str, Any]]:
        self._track("GET /markets")
        raw = await self.client.get_markets()
        markets = raw.get("markets", []) if isinstance(raw, dict) else raw
        return redact(markets)

    async def get_orderbook(self, ticker: str) -> dict[str, Any]:
        self._track("GET /markets/{ticker}/orderbook")
        book = await self.client.get_orderbook(ticker)
        return redact({
            "ticker": ticker,
            "market_ticker": book.market_ticker,
            "contract_ticker": book.contract_ticker,
            "bids": [{"price": b.price, "size": b.size} for b in book.bids],
            "asks": [{"price": a.price, "size": a.size} for a in book.asks],
            "timestamp": book.timestamp.isoformat(),
        })

    async def get_positions(self) -> list[dict[str, Any]]:
        self._track("GET /portfolio/positions")
        raw = await self.client.get_positions()
        positions = raw.get("positions", []) if isinstance(raw, dict) else raw
        return redact(positions)

    async def get_resting_orders(self) -> list[dict[str, Any]]:
        self._track("GET /portfolio/orders")
        raw = await self.client.get_orders()
        orders = raw.get("orders", []) if isinstance(raw, dict) else raw
        return redact(orders)

    async def get_fills(self) -> list[dict[str, Any]]:
        self._track("GET /portfolio/fills")
        raw = await self.client.get_fills()
        fills = raw.get("fills", []) if isinstance(raw, dict) else raw
        return redact(fills)

    async def _full_snapshot_inner(self, contract_ticker: str) -> dict[str, Any]:
        return {
            "account_status": await self.get_account_status(),
            "balance": await self.get_balance(),
            "events": await self.get_events(),
            "markets": await self.get_markets(),
            "orderbook": await self.get_orderbook(contract_ticker),
            "positions": await self.get_positions(),
            "resting_orders": await self.get_resting_orders(),
            "fills": await self.get_fills(),
            "endpoints_called": sorted(self.endpoints_called()),
            "order_creating_endpoints": sorted(self.order_creating_endpoints_called()),
            "request_audit_log": self.request_audit_log,
            "http_summary": self.http_summary(),
            "timestamp": datetime.now(timezone.utc).isoformat(),
        }

    async def get_full_snapshot(self, contract_ticker: str) -> dict[str, Any]:
        try:
            return await asyncio.wait_for(
                self._full_snapshot_inner(contract_ticker),
                timeout=KALSHI_READ_ONLY_TIMEOUT_SECONDS,
            )
        except asyncio.TimeoutError:
            logger.warning(
                "KalshiRealReadOnly.get_full_snapshot timed out",
                extra={"component": self.name, "contract_ticker": contract_ticker},
            )
            return {
                "source": self.name,
                "data_status": "UNAVAILABLE",
                "complete": False,
                "timeout": True,
                "data_authority": False,
                "reason": "real read-only snapshot timed out before completion",
                "contract_ticker": contract_ticker,
                "endpoints_called": sorted(self.endpoints_called()),
                "order_creating_endpoints": [],
                "request_audit_log": self.request_audit_log,
                "http_summary": self.http_summary(),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def full_snapshot(self, contract_ticker: str) -> dict[str, Any]:
        """Alias for ``get_full_snapshot`` with the same timeout protection."""
        return await self.get_full_snapshot(contract_ticker)

    async def close(self):
        await self.client.close()
