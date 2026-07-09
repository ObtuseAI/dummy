"""Reconciler: order status, stale-order cancellation, settlement detection.

Reads broker state (authenticated GETs) and market results (public GETs),
turns them into ledger facts. Cancels resting orders that have gone stale —
a maker quote left behind by a moved market is adverse selection waiting to
happen.
"""
from __future__ import annotations

import os
from datetime import datetime, timezone
from typing import Any, Callable

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import OutcomeKind, TradeOutcome
from autonomy.risk_brain import kalshi_taker_fee_cents

STALE_ORDER_MINUTES = 45


def _public_base() -> str:
    base = os.environ.get("KALSHI_API_BASE", "https://api.elections.kalshi.com").rstrip("/")
    version = os.environ.get("KALSHI_API_VERSION", "trade-api/v2").strip("/")
    return f"{base}/{version}"


def default_fetch_market_result(ticker: str) -> dict[str, Any]:
    import httpx

    response = httpx.get(f"{_public_base()}/markets/{ticker}", timeout=15)
    response.raise_for_status()
    market = response.json().get("market", {})
    return market if isinstance(market, dict) else {}


class Reconciler:
    def __init__(
        self,
        ledger: AutonomyLedger,
        fetch_market_result: Callable[[str], dict[str, Any]] | None = None,
        order_status_fn: Callable[[str], dict[str, Any]] | None = None,
        cancel_fn: Callable[[str], dict[str, Any]] | None = None,
    ) -> None:
        self.ledger = ledger
        self.fetch_market_result = fetch_market_result or default_fetch_market_result
        self.order_status_fn = order_status_fn
        self.cancel_fn = cancel_fn

    # ------------------------------------------------------------------
    # Settlements (public data; drives the whole learning loop)
    # ------------------------------------------------------------------

    def reconcile_settlements(self) -> list[tuple[str, bool]]:
        settled: list[tuple[str, bool]] = []
        for ticker in self.ledger.unsettled_traded_markets():
            try:
                market = self.fetch_market_result(ticker)
            except Exception:
                continue
            result = str(market.get("result", "")).lower()
            if result in ("yes", "no"):
                result_yes = result == "yes"
                self.ledger.record_settlement(ticker, result_yes)
                settled.append((ticker, result_yes))
        return settled

    # ------------------------------------------------------------------
    # Open orders (authenticated; only in live mode)
    # ------------------------------------------------------------------

    def reconcile_open_orders(self) -> list[TradeOutcome]:
        if self.order_status_fn is None:
            return []
        outcomes: list[TradeOutcome] = []
        for open_decision in self.ledger.open_decisions():
            order_id = open_decision.get("order_id") or ""
            if not order_id or order_id.startswith("shadow-"):
                continue
            try:
                status = self.order_status_fn(order_id)
            except Exception:
                continue
            state = str(status.get("status", "")).lower()
            filled = int(status.get("fill_count") or status.get("filled_count") or 0)
            created = str(status.get("created_time", ""))
            if state in ("executed", "filled") or filled >= int(open_decision["count"]):
                outcomes.append(self._outcome(open_decision, OutcomeKind.FILLED, order_id, filled))
            elif state in ("canceled", "cancelled"):
                outcomes.append(self._outcome(open_decision, OutcomeKind.CANCELED, order_id, filled))
            elif state == "resting" and self._is_stale(created) and self.cancel_fn is not None:
                try:
                    self.cancel_fn(order_id)
                    outcomes.append(self._outcome(open_decision, OutcomeKind.CANCELED, order_id, filled,
                                                  {"reason": "stale_maker_quote_auto_cancel"}))
                except Exception:
                    pass
        for outcome in outcomes:
            self.ledger.record_outcome(outcome)
        return outcomes

    def _is_stale(self, created_iso: str) -> bool:
        try:
            created = datetime.fromisoformat(created_iso.replace("Z", "+00:00"))
            age_min = (datetime.now(timezone.utc) - created).total_seconds() / 60.0
            return age_min > STALE_ORDER_MINUTES
        except Exception:
            return False

    def _outcome(self, open_decision: dict[str, Any], kind: OutcomeKind, order_id: str,
                 fill_count: int, detail: dict[str, Any] | None = None) -> TradeOutcome:
        return TradeOutcome(
            decision_id=str(open_decision["decision_id"]),
            market_ticker=str(open_decision["market_ticker"]),
            kind=kind,
            order_id=order_id,
            fill_count=fill_count,
            fill_price_cents=int(open_decision["price_cents"]),
            pnl_cents=None,
            broker_contacted=True,
            detail=detail or {},
        )


def settlement_pnl_cents(side: str, price_cents: int, count: int, result_yes: bool) -> int:
    """Realized P&L for a filled position at settlement, net of taker fee."""
    won = (side == "yes" and result_yes) or (side == "no" and not result_yes)
    gross = (100 - price_cents) * count if won else -price_cents * count
    return gross - kalshi_taker_fee_cents(price_cents, count)
