import asyncio
import os
import httpx
import json as _json
from collections import deque
from datetime import datetime, timezone
from decimal import Decimal
from typing import Any
from urllib.parse import unquote, urlsplit
from core.ontology import OrderBook, OrderBookLevel
from kalshi.signer import sign_request
from kalshi.error_classifier import classify
from kalshi.rate_limiter import KalshiRateLimiter
from core.logger import logger

_REQUEST_TIMEOUT_SECONDS = 10
_REQUEST_OUTER_TIMEOUT_SECONDS = 10

# Raw write methods are transport primitives, not public execution surfaces.
# The identity token is deliberately private and is presented only by the
# central LiveBrokerFirewall after all durable gates have passed.
_CENTRAL_FIREWALL_SUBMIT_CAPABILITY = object()

_READ_ONLY_HTTP_METHODS = frozenset({"GET", "HEAD", "OPTIONS"})


def _canonical_path_segments(path: str) -> tuple[str, ...]:
    """Return decoded, dot-normalized URL path segments for safety checks."""
    raw_path = urlsplit(str(path)).path.replace("\\", "/")
    # Decode more than once so a double-encoded slash cannot hide an order
    # endpoint from the transport gate while being decoded downstream.
    for _ in range(3):
        decoded = unquote(raw_path)
        if decoded == raw_path:
            break
        raw_path = decoded

    segments: list[str] = []
    for segment in raw_path.split("/"):
        normalized = segment.strip().casefold()
        if not normalized or normalized == ".":
            continue
        if normalized == "..":
            if segments:
                segments.pop()
            continue
        segments.append(normalized)
    return tuple(segments)


def _is_order_mutation(method: str, path: str) -> bool:
    """Identify any non-read request targeting the Kalshi order collection."""
    if str(method).strip().upper() in _READ_ONLY_HTTP_METHODS:
        return False
    segments = _canonical_path_segments(path)
    return any(
        segments[index : index + 2] == ("portfolio", "orders")
        for index in range(max(0, len(segments) - 1))
    )


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
        self.request_audit_log: deque[dict[str, Any]] = deque(maxlen=1000)

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
        capability = kwargs.pop("_capability", None)
        if (
            _is_order_mutation(method, path)
            and capability is not _CENTRAL_FIREWALL_SUBMIT_CAPABILITY
        ):
            raise PermissionError(
                "DIRECT_ORDER_SUBMIT_RETIRED_USE_CENTRAL_LIVE_FIREWALL"
            )
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
        loop = asyncio.get_running_loop()
        deadline = loop.time() + _REQUEST_OUTER_TIMEOUT_SECONDS - 0.05
        return await asyncio.wait_for(
            self.limiter.execute(call, deadline=deadline),
            timeout=_REQUEST_OUTER_TIMEOUT_SECONDS,
        )

    async def get_events(self):
        return await self._request("GET", "/events")

    async def get_markets(self, max_pages: int = 10):
        combined: list[Any] = []
        cursor: str | None = None
        first_page: dict[str, Any] | None = None
        pages_fetched = 0
        for _ in range(max(1, max_pages)):
            params: dict[str, Any] = {"status": "open"}
            if cursor:
                params["cursor"] = cursor
            page = await self._request("GET", "/markets", params=params)
            pages_fetched += 1
            if not isinstance(page, dict):
                return page
            if first_page is None:
                first_page = page
            markets = page.get("markets", [])
            if isinstance(markets, list):
                combined.extend(markets)
            next_cursor = page.get("cursor")
            if not next_cursor or next_cursor == cursor:
                cursor = None
                break
            cursor = str(next_cursor)
        result = dict(first_page or {})
        result["markets"] = combined
        result["cursor"] = cursor
        result["pages_fetched"] = pages_fetched
        result["pagination_truncated"] = cursor is not None
        return result

    async def get_event(self, ticker: str):
        return await self._request("GET", f"/events/{ticker}")

    async def get_series(self, ticker: str):
        return await self._request("GET", f"/series/{ticker}")

    async def get_market(self, ticker: str):
        return await self._request("GET", f"/markets/{ticker}")

    async def get_orderbook(self, ticker: str, depth: int = 10) -> OrderBook:
        data = await self._request("GET", f"/markets/{ticker}/orderbook", params={"depth": depth})
        received_at = datetime.now(timezone.utc)
        ob = data.get("orderbook_fp") or data.get("orderbook", {})
        if not isinstance(ob, dict) or not ob:
            raise ValueError(f"Kalshi orderbook for {ticker} is missing")

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
        else:
            # Legacy / fallback shape.
            bids = [OrderBookLevel(price=int(b["price"]), size=int(b.get("count", 0))) for b in ob.get("bids", [])]
            asks = [OrderBookLevel(price=int(a["price"]), size=int(a.get("count", 0))) for a in ob.get("asks", [])]

        bids.sort(key=lambda level: level.price)
        asks.sort(key=lambda level: level.price)
        if not bids or not asks:
            raise ValueError(f"Kalshi orderbook for {ticker} is missing bids or asks")
        if bids[-1].price >= asks[0].price:
            raise ValueError(f"Kalshi orderbook for {ticker} is crossed")

        ts_value = (
            ob.get("timestamp")
            or ob.get("updated_at")
            or data.get("timestamp")
            or data.get("updated_at")
        )
        source_ts = None
        if isinstance(ts_value, datetime):
            source_ts = ts_value if ts_value.tzinfo else ts_value.replace(tzinfo=timezone.utc)
        elif isinstance(ts_value, str):
            try:
                source_ts = datetime.fromisoformat(ts_value.replace("Z", "+00:00"))
            except ValueError:
                source_ts = None
        # The REST response itself is a current point-in-time observation. Keep
        # source time separate when Kalshi supplies it; otherwise use the local
        # receipt witness rather than fabricating an exchange timestamp.
        timestamp = source_ts or received_at

        return OrderBook(
            market_ticker=ticker,
            contract_ticker=ticker,
            bids=bids,
            asks=asks,
            timestamp=timestamp,
            received_at=received_at,
            source_ts=source_ts,
            freshness_score=Decimal("1.0"),
            depth_summary={
                "best_bid_cents": bids[-1].price,
                "best_ask_cents": asks[0].price,
                "spread_cents": asks[0].price - bids[-1].price,
                "crossed": False,
            },
        )

    async def get_account(self):
        return await self._request("GET", "/portfolio/balance")

    async def get_positions(self):
        return await self._request("GET", "/portfolio/positions")

    async def get_fills(self):
        return await self._request("GET", "/portfolio/fills")

    async def get_orders(self):
        return await self._request("GET", "/portfolio/orders")

    async def create_order(self, order: dict, *, _capability: object | None = None):
        if _capability is not _CENTRAL_FIREWALL_SUBMIT_CAPABILITY:
            raise PermissionError(
                "DIRECT_ORDER_SUBMIT_RETIRED_USE_CENTRAL_LIVE_FIREWALL"
            )
        return await self._request(
            "POST",
            "/portfolio/orders",
            json=order,
            _capability=_capability,
        )

    async def cancel_order(
        self,
        order_id: str,
        *,
        _capability: object | None = None,
    ):
        return await self._request(
            "DELETE",
            f"/portfolio/orders/{order_id}",
            _capability=_capability,
        )

    async def close(self):
        await self.client.aclose()
