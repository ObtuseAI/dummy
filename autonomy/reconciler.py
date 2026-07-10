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

from autonomy.fees import kalshi_maker_fee_cents, kalshi_taker_fee_cents
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import MarketView, OutcomeKind, TradeOutcome

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


def default_fetch_trades(ticker: str, min_ts: int, max_ts: int) -> list[dict[str, Any]]:
    """Fetch standard-book public prints for an exact market/time window."""
    import httpx

    collected: list[dict[str, Any]] = []
    cursor: str | None = None
    for _page in range(5):
        params: dict[str, Any] = {
            "ticker": ticker, "min_ts": min_ts, "max_ts": max_ts,
            "is_block_trade": "false", "limit": 1000,
        }
        if cursor:
            params["cursor"] = cursor
        response = httpx.get(f"{_public_base()}/markets/trades", params=params, timeout=20)
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("trades") or []
        if isinstance(rows, list):
            collected.extend(row for row in rows if isinstance(row, dict))
        cursor = payload.get("cursor") or None
        if not cursor:
            break
    return collected


class Reconciler:
    def __init__(
        self,
        ledger: AutonomyLedger,
        fetch_market_result: Callable[[str], dict[str, Any]] | None = None,
        order_status_fn: Callable[[str], dict[str, Any]] | None = None,
        cancel_fn: Callable[[str], dict[str, Any]] | None = None,
        fetch_settled_page: Callable[..., dict[str, Any]] | None = None,
        fetch_shadow_candles: Callable[..., list[dict[str, Any]]] | None = None,
        fetch_shadow_trades: Callable[[str, int, int], list[dict[str, Any]]] | None = None,
    ) -> None:
        self.ledger = ledger
        self.fetch_market_result = fetch_market_result or default_fetch_market_result
        self.order_status_fn = order_status_fn
        self.cancel_fn = cancel_fn
        # Opt-in (None = disabled) so hermetic tests never hit the network.
        self.fetch_settled_page = fetch_settled_page
        self.fetch_shadow_candles = fetch_shadow_candles
        self.fetch_shadow_trades = fetch_shadow_trades

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
            if not open_decision.get("order_active"):
                continue
            order_id = open_decision.get("order_id") or ""
            if not order_id or order_id.startswith("shadow-"):
                continue
            try:
                status = self.order_status_fn(order_id)
            except Exception:
                continue
            state = str(status.get("status", "")).lower()
            try:
                filled = int(float(status.get("fill_count_fp") or status.get("fill_count")
                                   or status.get("filled_count") or 0))
            except (TypeError, ValueError):
                filled = 0
            prior_filled = int(open_decision.get("filled_count") or 0)
            created = str(status.get("created_time", ""))
            if state in ("executed", "filled") or filled >= int(open_decision["count"]):
                outcomes.append(self._outcome(open_decision, OutcomeKind.FILLED, order_id, filled))
            elif state in ("canceled", "cancelled"):
                outcomes.append(self._outcome(open_decision, OutcomeKind.CANCELED, order_id, filled))
            elif filled > prior_filled:
                outcomes.append(self._outcome(
                    open_decision, OutcomeKind.PARTIALLY_FILLED, order_id, filled,
                    {"state": state or "resting", "new_cumulative_fill_count": filled},
                ))
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

    def reconcile_shadow_orders(
        self,
        markets: list[MarketView],
        *,
        now: datetime | None = None,
    ) -> list[TradeOutcome]:
        """Conservatively fill shadow maker orders only after an observed cross.

        A pending BUY YES at 40c is considered filled only when a later market
        snapshot offers YES at 40c or better. The simulator books the original
        limit price (not the potentially better observed ask), avoiding
        optimistic price improvement. Uncrossed quotes expire on the same TTL
        as live orders and never become fictional positions or P&L.
        """
        from autonomy.executor import MAX_QUEUE_AHEAD_CONTRACTS, order_ttl_seconds

        now = now or datetime.now(timezone.utc)
        by_ticker = {market.ticker: market for market in markets}
        outcomes: list[TradeOutcome] = []
        for pending in self.ledger.open_decisions("shadow"):
            if not pending.get("order_active") or int(pending.get("filled_count") or 0) > 0:
                continue
            try:
                created = datetime.fromisoformat(str(pending["created_at"]).replace("Z", "+00:00"))
            except Exception:
                created = now
            age_seconds = (now - created).total_seconds()
            ttl_seconds = order_ttl_seconds(str(pending["market_ticker"]))
            expires = created.timestamp() + ttl_seconds
            submission = pending.get("submission_detail") or {}
            if (
                submission.get("queue_snapshot_available")
                and float(submission.get("queue_ahead_contracts") or 0)
                    > MAX_QUEUE_AHEAD_CONTRACTS
            ):
                outcomes.append(TradeOutcome(
                    decision_id=str(pending["decision_id"]),
                    market_ticker=str(pending["market_ticker"]),
                    kind=OutcomeKind.EXPIRED,
                    order_id=str(pending.get("order_id") or ""),
                    fill_count=0,
                    fill_price_cents=None,
                    pnl_cents=None,
                    broker_contacted=False,
                    detail={
                        "reason": "shadow_queue_policy_invalidated",
                        "queue_ahead_contracts": submission["queue_ahead_contracts"],
                        "maximum_queue_ahead_contracts": MAX_QUEUE_AHEAD_CONTRACTS,
                    },
                ))
                continue
            detail: dict[str, Any] | None = None
            if now.timestamp() < expires:
                detail = self._shadow_trade_fill(
                    pending, int(created.timestamp()), int(min(now.timestamp(), expires)),
                )
                market = by_ticker.get(str(pending["market_ticker"]))
                ask = None
                if market is not None:
                    ask = market.yes_ask if pending["side"] == "yes" else market.no_ask
                if detail is None and ask is not None and int(ask) <= int(pending["price_cents"]):
                    detail = {
                        "reason": "shadow_maker_observed_cross",
                        "observed_ask_cents": int(ask),
                        "fill_witness_at": now.isoformat(),
                        "conservative_fill_price_cents": int(pending["price_cents"]),
                    }
            if detail is None:
                detail = self._shadow_candle_cross(
                    pending, int(created.timestamp()), int(min(now.timestamp(), expires))
                )
            if detail is not None:
                kind = OutcomeKind.FILLED
            elif age_seconds >= ttl_seconds:
                kind = OutcomeKind.EXPIRED
                detail = {"reason": "shadow_maker_ttl_expired_unfilled"}
            else:
                continue
            outcomes.append(TradeOutcome(
                decision_id=str(pending["decision_id"]),
                market_ticker=str(pending["market_ticker"]),
                kind=kind,
                order_id=str(pending.get("order_id") or ""),
                fill_count=int(pending["count"]) if kind is OutcomeKind.FILLED else 0,
                fill_price_cents=int(pending["price_cents"]) if kind is OutcomeKind.FILLED else None,
                pnl_cents=None,
                broker_contacted=False,
                detail=detail,
            ))
        for outcome in outcomes:
            self.ledger.record_outcome(outcome)
        return outcomes

    def _shadow_trade_fill(
        self, pending: dict[str, Any], start_ts: int, end_ts: int,
    ) -> dict[str, Any] | None:
        """Witness maker execution from public prints and captured queue depth.

        A print strictly through the limit proves the full resting order was
        consumed first. At the exact limit, cumulative matching taker volume
        must clear the queue captured immediately before submission plus the
        simulated order size. Block trades are excluded by the fetcher and
        again here defensively.
        """
        if self.fetch_shadow_trades is None or end_ts <= start_ts:
            return None
        try:
            trades = self.fetch_shadow_trades(
                str(pending["market_ticker"]), start_ts, end_ts,
            )
        except Exception:
            return None
        side = str(pending["side"])
        expected_taker_book_side = "ask" if side == "yes" else "bid"
        limit = int(pending["price_cents"])
        exact_volume = 0.0
        matching_ids: list[str] = []
        last_matching_at: str | None = None
        for trade in sorted(trades, key=lambda item: str(item.get("created_time") or "")):
            if trade.get("is_block_trade") is True:
                continue
            if str(trade.get("taker_book_side") or "").lower() != expected_taker_book_side:
                continue
            try:
                price = int(round(float(
                    trade.get("yes_price_dollars") if side == "yes"
                    else trade.get("no_price_dollars")
                ) * 100))
                count = float(trade.get("count_fp") or 0)
                created = datetime.fromisoformat(
                    str(trade.get("created_time") or "").replace("Z", "+00:00")
                )
            except (TypeError, ValueError):
                continue
            if not (start_ts <= created.timestamp() <= end_ts) or count <= 0:
                continue
            trade_id = str(trade.get("trade_id") or "")
            if price < limit:
                return {
                    "reason": "shadow_maker_public_trade_through",
                    "trade_id": trade_id,
                    "trade_price_cents": price,
                    "trade_count": count,
                    "trade_created_time": created.isoformat(),
                    "fill_witness_at": created.isoformat(),
                    "conservative_fill_price_cents": limit,
                }
            if price == limit:
                exact_volume += count
                if trade_id:
                    matching_ids.append(trade_id)
                last_matching_at = created.isoformat()
        submission = pending.get("submission_detail") or {}
        if not submission.get("queue_snapshot_available"):
            return None
        queue_ahead = max(0.0, float(submission.get("queue_ahead_contracts") or 0))
        required = queue_ahead + int(pending["count"])
        if exact_volume + 1e-9 < required:
            return None
        return {
            "reason": "shadow_maker_public_trade_queue_consumed",
            "queue_ahead_contracts": queue_ahead,
            "order_contracts": int(pending["count"]),
            "matching_trade_volume": round(exact_volume, 4),
            "matching_trade_ids": matching_ids[:20],
            "fill_witness_at": last_matching_at,
            "conservative_fill_price_cents": limit,
        }

    def _shadow_candle_cross(
        self,
        pending: dict[str, Any],
        start_ts: int,
        end_ts: int,
    ) -> dict[str, Any] | None:
        """Find an intracycle 1-minute quote cross before order expiration."""
        if self.fetch_shadow_candles is None or end_ts <= start_ts:
            return None
        ticker = str(pending["market_ticker"])
        series = ticker.split("-", 1)[0]
        try:
            candles = self.fetch_shadow_candles(series, ticker, start_ts, end_ts, 1)
        except Exception:
            return None
        limit_dollars = int(pending["price_cents"]) / 100.0
        for candle in sorted(candles, key=lambda item: int(item.get("end_period_ts", 0))):
            try:
                candle_end = int(candle.get("end_period_ts", 0))
            except (TypeError, ValueError):
                continue
            if not (start_ts <= candle_end <= end_ts):
                continue
            if pending["side"] == "yes":
                quote = candle.get("yes_ask") or {}
                raw = quote.get("low_dollars", quote.get("low"))
                crossed = raw is not None and float(raw) <= limit_dollars
                observed = float(raw) if raw is not None else None
            else:
                # NO ask = 1 - YES bid. A high YES bid trades through our NO bid.
                quote = candle.get("yes_bid") or {}
                raw = quote.get("high_dollars", quote.get("high"))
                observed = (1.0 - float(raw)) if raw is not None else None
                crossed = observed is not None and observed <= limit_dollars
            if crossed:
                return {
                    "reason": "shadow_maker_intracycle_candle_cross",
                    "candle_end_ts": candle_end,
                    "fill_witness_at": datetime.fromtimestamp(
                        candle_end, timezone.utc,
                    ).isoformat(),
                    "observed_ask_dollars": round(float(observed), 4),
                    "conservative_fill_price_cents": int(pending["price_cents"]),
                }
        return None

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


def settlement_pnl_cents(
    side: str,
    price_cents: int,
    count: int,
    result_yes: bool,
    market_ticker: str | None = None,
    liquidity_role: str = "taker",
) -> int:
    """Realized P&L for confirmed fills, net of the applicable trading fee."""
    won = (side == "yes" and result_yes) or (side == "no" and not result_yes)
    gross = (100 - price_cents) * count if won else -price_cents * count
    if liquidity_role == "maker":
        fee = kalshi_maker_fee_cents(price_cents, count, market_ticker)
    else:
        fee = kalshi_taker_fee_cents(price_cents, count, market_ticker)
    return gross - fee
