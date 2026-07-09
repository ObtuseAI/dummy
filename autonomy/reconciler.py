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


def default_fetch_settled_page(series_ticker: str, min_close_ts: int,
                               cursor: str | None = None) -> dict[str, Any]:
    """One page of recently settled markets for a series (public GET)."""
    import httpx

    params: dict[str, Any] = {
        "series_ticker": series_ticker, "status": "settled",
        "min_close_ts": min_close_ts, "limit": 200,
    }
    if cursor:
        params["cursor"] = cursor
    response = httpx.get(f"{_public_base()}/markets", params=params, timeout=20)
    response.raise_for_status()
    data = response.json()
    return data if isinstance(data, dict) else {}


class Reconciler:
    def __init__(
        self,
        ledger: AutonomyLedger,
        fetch_market_result: Callable[[str], dict[str, Any]] | None = None,
        order_status_fn: Callable[[str], dict[str, Any]] | None = None,
        cancel_fn: Callable[[str], dict[str, Any]] | None = None,
        fetch_settled_page: Callable[..., dict[str, Any]] | None = None,
    ) -> None:
        self.ledger = ledger
        self.fetch_market_result = fetch_market_result or default_fetch_market_result
        self.order_status_fn = order_status_fn
        self.cancel_fn = cancel_fn
        # Opt-in (None = disabled) so hermetic tests never hit the network.
        self.fetch_settled_page = fetch_settled_page

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

    def reconcile_forecast_settlements(
        self,
        series_list: list[str],
        lookback_hours: float = 48.0,
        max_pages_per_series: int = 3,
    ) -> list[tuple[str, bool]]:
        """Phantom grading: settle every FORECASTED market, not just traded ones.

        The machine opines on ~1000 markets a cycle; every one that settles is
        free calibration evidence. Batch sweep: one settled-markets listing per
        watchlist series (cursor-paged), matched against tickers we recently
        signaled on. No per-ticker calls, no positions touched — settlements
        recorded here feed the learner only.
        """
        if self.fetch_settled_page is None or not series_list:
            return []
        unsettled = set(self.ledger.unsettled_forecast_markets())
        if not unsettled:
            return []
        min_close_ts = int(datetime.now(timezone.utc).timestamp() - lookback_hours * 3600)
        settled: list[tuple[str, bool]] = []
        for series in series_list:
            cursor: str | None = None
            for _page in range(max_pages_per_series):
                try:
                    data = self.fetch_settled_page(series, min_close_ts, cursor)
                except Exception:
                    break  # one dead series never stalls the sweep
                for market in data.get("markets", []):
                    ticker = str(market.get("ticker", ""))
                    if ticker not in unsettled:
                        continue
                    result = str(market.get("result", "")).lower()
                    if result in ("yes", "no"):
                        result_yes = result == "yes"
                        self.ledger.record_settlement(ticker, result_yes)
                        settled.append((ticker, result_yes))
                        unsettled.discard(ticker)
                cursor = data.get("cursor") or None
                if not cursor:
                    break
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
