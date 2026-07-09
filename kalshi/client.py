import asyncio
import os, httpx, json as _json
from datetime import datetime, timezone
from typing import Any
from core.ontology import OrderBook, OrderBookLevel
from kalshi.signer import sign_request
from kalshi.error_classifier import classify
from kalshi.rate_limiter import KalshiRateLimiter
from core.logger import logger

_REQUEST_TIMEOUT_SECONDS = 10
_REQUEST_OUTER_TIMEOUT_SECONDS = 10


# Defaults must stay aligned with kalshi.signer so the signed path prefix and
# the request URL agree. The legacy v1 host (trading-api.kalshi.com) is dead.
def _kalshi_base() -> str:
    return os.environ.get("KALSHI_API_BASE", "https://api.elections.kalshi.com").rstrip("/")


def _kalshi_version() -> str:
    return os.environ.get("KALSHI_API_VERSION", "trade-api/v2").strip("/")


# Backward-compatible module-level aliases for code that reads them at import time.
BASE = _kalshi_base()
VERSION = _kalshi_version()


class KalshiClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=f"{_kalshi_base()}/{_kalshi_version()}", timeout=_REQUEST_TIMEOUT_SECONDS)
        self.limiter = KalshiRateLimiter()
        self.request_audit_log: list[dict[str, Any]] = []

    def _family_path(self, path: str) -> str:
        """Collapse ticker-specific segments so `/markets/FOO/orderbook` becomes `/markets/{ticker}/orderbook`."""
        parts = path.strip("/").split("/")
        if len(parts) >= 3 and parts[0] == "markets":
            parts[1] = "{ticker}"
        if len(parts) >= 3 and parts[0] == "portfolio" and parts[1] == "orders":
            if not parts[2].startswith("{"):
                parts[2] = "{order_id}"
        return "/" + "/".join(parts)

    def _redacted_summary(self, response: httpx.Response) -> dict[str, Any]:
        summary: dict[str, Any] = {"status_code": response.status_code}
        if response.status_code < 400:
            try:
                data = response.json()
                if isinstance(data, list):
                    summary["count"] = len(data)
                elif isinstance(data, dict):
                    summary["keys"] = sorted(data.keys())[:10]
                    summary["count"] = len(data) if isinstance(list(data.values())[0], list) else None
            except Exception:
                summary["body_preview"] = response.text[:120]
        else:
            summary["error_preview"] = response.text[:120]
        return summary

    async def _request(self, method: str, path: str, **kwargs):
        json_body = kwargs.pop("json", "")
        if isinstance(json_body, dict):
            body_str = _json.dumps(json_body, separators=(",", ":"), sort_keys=True)
            body_bytes = body_str.encode("utf-8")
        elif isinstance(json_body, str):
            body_str = json_body
            body_bytes = body_str.encode("utf-8")
        else:
            body_str = ""
            body_bytes = b""
        headers = sign_request(method, path, body_str)
        headers["Content-Type"] = "application/json"
        async def call():
            response = await self.client.request(method, path, headers=headers, content=body_bytes, **kwargs)
            self.request_audit_log.append({
                "method": method.upper(),
                "path": path,
                "path_family": self._family_path(path),
                "status_code": response.status_code,
                "status_class": f"{response.status_code // 100}xx",
                "redacted_summary": self._redacted_summary(response),
            })
            if response.status_code >= 400:
                cat = classify(response.status_code, response.text)
                logger.error("Kalshi API error", extra={"component": "kalshi_client", "status": response.status_code, "category": cat.value})
            response.raise_for_status()
            return response.json()
        # Hard outer bound so no Kalshi request can block the caller indefinitely.
        return await asyncio.wait_for(self.limiter.execute(call), timeout=_REQUEST_OUTER_TIMEOUT_SECONDS)

    async def get_events(self):
        return await self._request("GET", "/events")

    async def get_markets(self):
        return await self._request("GET", "/markets")

    async def get_market(self, ticker: str):
        return await self._request("GET", f"/markets/{ticker}")

    async def get_orderbook(self, ticker: str, depth: int = 10) -> OrderBook:
        data = await self._request("GET", f"/markets/{ticker}/orderbook", params={"depth": depth})
        ob = data.get("orderbook_fp") or data.get("orderbook", {})

        if "yes_dollars" in ob or "no_dollars" in ob:
            # Kalshi v2 orderbook: yes_dollars are yes-side bids,
            # no_dollars are no-side bids; derive yes-side asks as 1 - no_bid.
            bids = [
                OrderBookLevel(price=int(round(float(price_str) * 100)), size=int(float(count_str)))
                for price_str, count_str in ob.get("yes_dollars", [])
            ]
            asks = [
                OrderBookLevel(price=int(round((1.0 - float(price_str)) * 100)), size=int(float(count_str)))
                for price_str, count_str in ob.get("no_dollars", [])
            ]
            asks.sort(key=lambda level: level.price)
        else:
            # Legacy / fallback shape.
            bids = [OrderBookLevel(price=int(b["price"]), size=int(b.get("count", 0))) for b in ob.get("bids", [])]
            asks = [OrderBookLevel(price=int(a["price"]), size=int(a.get("count", 0))) for a in ob.get("asks", [])]

        return OrderBook(
            market_ticker=ticker,
            contract_ticker=ticker,
            bids=bids,
            asks=asks,
            timestamp=datetime.now(timezone.utc),
        )

    async def get_account(self):
        return await self._request("GET", "/portfolio/balance")

    async def get_positions(self):
        return await self._request("GET", "/portfolio/positions")

    async def get_fills(self):
        return await self._request("GET", "/portfolio/fills")

    async def get_orders(self):
        return await self._request("GET", "/portfolio/orders")

    async def create_order(self, order: dict):
        return await self._request("POST", "/portfolio/orders", json=order)

    async def cancel_order(self, order_id: str):
        return await self._request("DELETE", f"/portfolio/orders/{order_id}")

    async def close(self):
        await self.client.aclose()
