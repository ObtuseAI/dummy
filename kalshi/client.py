import os, httpx, json as _json
from datetime import datetime, timezone
from core.ontology import OrderBook, OrderBookLevel
from kalshi.signer import sign_request
from kalshi.error_classifier import classify
from kalshi.rate_limiter import KalshiRateLimiter
from core.logger import logger

BASE = os.environ.get("KALSHI_API_BASE", "https://trading-api.kalshi.com").rstrip("/")
VERSION = os.environ.get("KALSHI_API_VERSION", "v1")

class KalshiClient:
    def __init__(self):
        self.client = httpx.AsyncClient(base_url=f"{BASE}/{VERSION}", timeout=30)
        self.limiter = KalshiRateLimiter()

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
            if response.status_code >= 400:
                cat = classify(response.status_code, response.text)
                logger.error("Kalshi API error", extra={"component": "kalshi_client", "status": response.status_code, "category": cat.value})
            response.raise_for_status()
            return response.json()
        return await self.limiter.execute(call)

    async def get_markets(self):
        return await self._request("GET", "/markets")

    async def get_market(self, ticker: str):
        return await self._request("GET", f"/markets/{ticker}")

    async def get_orderbook(self, ticker: str, depth: int = 10) -> OrderBook:
        data = await self._request("GET", f"/markets/{ticker}/orderbook", params={"depth": depth})
        ob = data.get("orderbook", {})
        return OrderBook(
            market_ticker=ticker,
            contract_ticker=ticker,
            bids=[OrderBookLevel(price=int(b["price"]), size=int(b.get("count", 0))) for b in ob.get("bids", [])],
            asks=[OrderBookLevel(price=int(a["price"]), size=int(a.get("count", 0))) for a in ob.get("asks", [])],
            timestamp=datetime.now(timezone.utc),
        )

    async def get_account(self):
        return await self._request("GET", "/account")

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
