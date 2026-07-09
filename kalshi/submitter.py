from __future__ import annotations

from typing import Any

from core.config_loader import load_caps
from core.logger import logger
from kalshi.client import KalshiClient


class KalshiSubmitter:
    """Thin limit-order submitter used exclusively by LiveBrokerFirewall."""

    name: str = "kalshi_submitter"

    def __init__(self, client: KalshiClient | None = None):
        self.client = client or KalshiClient()

    async def submit_limit_order(self, order: dict[str, Any]) -> dict[str, Any]:
        order_type = order.get("type")
        if order_type != "limit":
            logger.error("Order type rejected", extra={"component": self.name, "type": order_type})
            raise ValueError(f"Only limit orders are allowed; received {order_type!r}")

        caps = load_caps()
        if caps.allow_market_orders:
            # Caps must never allow market orders for Dummy live trading.
            logger.error("Market order cap misconfiguration rejected", extra={"component": self.name})
            raise ValueError("Market orders are forbidden regardless of cap configuration")

        # Limit price lives in yes_price/no_price on the v2 wire schema; the
        # flat "price" key is accepted for legacy internal callers.
        price = int(order.get("yes_price") or order.get("no_price") or order.get("price") or 0)
        count = int(order.get("count", 0))
        order_value = price * count
        if order_value > caps.max_single_order_cents:
            logger.error("Single order cap exceeded", extra={"component": self.name, "order_value": order_value})
            raise ValueError(f"Order value {order_value}c exceeds max_single_order_cents {caps.max_single_order_cents}c")

        logger.info("Submitting limit order", extra={"component": self.name, "ticker": order.get("ticker"), "price": price, "count": count})
        return await self.client.create_order(order)

    async def close(self):
        await self.client.close()
