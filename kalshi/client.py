import os, httpx
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
        body = kwargs.get("json", "")
        body_str = "" if body == "" else (body if isinstance(body, str) else str(body))
        headers = sign_request(method, path, body_str)
        headers["Content-Type"] = "application/json"
        async def call():
            response = await self.client.request(method, path, headers=headers, **kwargs)
            if response.status_code >= 400:
                cat = classify(response.status_code, response.text)
                logger.error("Kalshi API error", extra={"component": "kalshi_client", "status": response.status_code, "category": cat.value})
            response.raise_for_status()
            return response.json()
        return await self.limiter.execute(call())

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
