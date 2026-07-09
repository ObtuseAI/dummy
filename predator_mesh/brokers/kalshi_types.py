"""Kalshi-specific order payload helpers and status normalization."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from predator_mesh.brokers.livebrokerfirewall_adapter import (
    LimitOrderRequest,
    OrderState,
)


@dataclass(frozen=True)
class KalshiCreateOrderPayload:
    """Typed view of the dict sent to Kalshi's create-order endpoint.

    Matches the trade-api/v2 CreateOrder body: the limit price is expressed
    as ``yes_price`` or ``no_price`` (integer cents, 1-99) depending on the
    order side — there is no flat ``price`` field — and ``client_order_id``
    is required.
    """

    ticker: str
    side: str  # "yes" | "no"
    action: str  # "buy" | "sell"
    type: str  # "limit"
    count: int
    client_order_id: str
    yes_price: int | None = None
    no_price: int | None = None
    expiration_ts: int | None = None

    def to_dict(self) -> dict[str, Any]:
        payload: dict[str, Any] = {
            "ticker": self.ticker,
            "side": self.side,
            "action": self.action,
            "type": self.type,
            "count": self.count,
            "client_order_id": self.client_order_id,
        }
        if self.yes_price is not None:
            payload["yes_price"] = self.yes_price
        if self.no_price is not None:
            payload["no_price"] = self.no_price
        if self.expiration_ts is not None:
            payload["expiration_ts"] = self.expiration_ts
        return payload


def kalshi_create_order_payload(req: LimitOrderRequest) -> dict[str, Any]:
    """Map a normalized LimitOrderRequest to Kalshi's create-order body."""
    payload = KalshiCreateOrderPayload(
        ticker=req.market_ticker,
        side=req.side,
        action=req.action,
        type="limit",
        count=req.quantity,
        client_order_id=req.idempotency_key or req.client_order_id or "",
        yes_price=req.price if req.side == "yes" else None,
        no_price=req.price if req.side == "no" else None,
        expiration_ts=getattr(req, "expiration_ts", None),
    )
    return payload.to_dict()


def normalize_kalshi_status(status: str | None) -> str:
    """Map a Kalshi order status string to a normalized OrderState value."""
    if not status:
        return OrderState.UNKNOWN
    s = status.lower().strip()
    if s in {"filled", "complete", "completed"}:
        return OrderState.FILLED
    if s in {"rejected", "reject"}:
        return OrderState.REJECTED
    if s in {"canceled", "cancelled"}:
        return OrderState.CANCELED
    if s == "expired":
        return OrderState.EXPIRED
    if s in {"partial_fill", "partially_filled", "partial"}:
        return OrderState.PARTIAL_FILL
    if s in {"resting", "open", "active", "pending", "unmatched", "live"}:
        return OrderState.OPEN
    return OrderState.UNKNOWN
