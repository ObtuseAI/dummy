from __future__ import annotations

from datetime import datetime, timedelta, timezone
from decimal import Decimal
from typing import Any

from core.ontology import (
    Contract,
    Event,
    Fill,
    ForecastInput,
    KalshiAccount,
    Market,
    OrderBook,
    OrderBookLevel,
    Position,
    RestingOrder,
)

_STALE_SECONDS = 60


class DataNormalizationError(Exception):
    """Raised when live Kalshi data cannot be normalized."""
    pass


class KalshiNormalizer:
    """Convert live Kalshi payloads into Dummy-native Pydantic models."""

    def __init__(self, stale_seconds: int = _STALE_SECONDS):
        self.stale_seconds = stale_seconds

    @staticmethod
    def _now_utc() -> datetime:
        return datetime.now(timezone.utc)

    @staticmethod
    def _parse_ts(ts: Any) -> datetime:
        if isinstance(ts, datetime):
            if ts.tzinfo is None:
                return ts.replace(tzinfo=timezone.utc)
            return ts
        if not isinstance(ts, str):
            raise DataNormalizationError(f"Invalid timestamp type: {type(ts)}")
        return datetime.fromisoformat(ts.replace("Z", "+00:00"))

    def _is_stale(self, ts: Any) -> bool:
        try:
            parsed = self._parse_ts(ts)
            age = (self._now_utc() - parsed).total_seconds()
            return age > self.stale_seconds
        except Exception:
            return True

    def _freshness_score(self, ts: Any) -> Decimal:
        try:
            parsed = self._parse_ts(ts)
            age = max(0.0, (self._now_utc() - parsed).total_seconds())
            score = max(0.0, 1.0 - age / self.stale_seconds)
        except Exception:
            score = 0.0
        return Decimal(str(round(score, 4)))

    def _source_ts(self, raw: dict[str, Any], fallback: datetime | None = None) -> datetime:
        for key in ("updated_ts", "updated_time", "created_time", "created_at", "timestamp", "ts"):
            if key in raw and raw[key]:
                try:
                    return self._parse_ts(raw[key])
                except Exception:
                    continue
        return fallback or self._now_utc()

    def normalize_account(self, raw: dict[str, Any]) -> KalshiAccount:
        if not isinstance(raw, dict):
            raise DataNormalizationError("Account raw data must be a dict")
        ts = self._source_ts(raw)
        return KalshiAccount(
            user_id=str(raw.get("user_id", "unknown")),
            email=str(raw.get("email", "")),
            balance_cents=int(raw.get("balance", 0)),
            available_cents=int(raw.get("available_balance", raw.get("balance", 0))),
            source_ts=ts,
            freshness_score=self._freshness_score(ts),
        )

    def normalize_events(self, raw: Any) -> list[Event]:
        events = raw.get("events", raw) if isinstance(raw, dict) else raw
        if not isinstance(events, list):
            raise DataNormalizationError("Events raw data must be a list or dict with 'events'")
        return [self._normalize_event(e) for e in events]

    def _normalize_event(self, raw: dict[str, Any]) -> Event:
        ts = self._source_ts(raw)
        markets = [self._normalize_market(m) for m in raw.get("markets", [])]
        return Event(
            ticker=str(raw.get("event_ticker", raw.get("ticker", ""))),
            title=str(raw.get("title", "")),
            category=str(raw.get("category", "")),
            status=str(raw.get("status", "")),
            markets=markets,
            source_ts=ts,
            freshness_score=self._freshness_score(ts),
        )

    def normalize_markets(self, raw: Any) -> list[Market]:
        markets = raw.get("markets", raw) if isinstance(raw, dict) else raw
        if not isinstance(markets, list):
            raise DataNormalizationError("Markets raw data must be a list or dict with 'markets'")
        return [self._normalize_market(m) for m in markets]

    def _normalize_market(self, raw: dict[str, Any]) -> Market:
        ts = self._source_ts(raw)
        contracts = raw.get("contracts", [raw])
        if not isinstance(contracts, list):
            contracts = [raw]
        return Market(
            ticker=str(raw.get("ticker", "")),
            title=str(raw.get("title", "")),
            status=str(raw.get("status", "")),
            category=str(raw.get("category", "")),
            event_ticker=str(raw.get("event_ticker", "")),
            contracts=[self._normalize_contract(c, ts) for c in contracts],
            source_ts=ts,
            freshness_score=self._freshness_score(ts),
        )

    def _normalize_contract(self, raw: dict[str, Any], source_ts: datetime | None = None) -> Contract:
        if not raw.get("ticker"):
            raise DataNormalizationError("Contract missing ticker")
        ts = self._source_ts(raw, fallback=source_ts)
        return Contract(
            ticker=str(raw["ticker"]),
            title=str(raw.get("title", "")),
            status=str(raw.get("status", "")),
            yes_bid=self._to_int_optional(raw.get("yes_bid")),
            yes_ask=self._to_int_optional(raw.get("yes_ask")),
            last_price=self._to_int_optional(raw.get("last_price")),
            source_ts=ts,
        )

    @staticmethod
    def _to_int_optional(value: Any) -> int | None:
        if value is None:
            return None
        try:
            return int(value)
        except (TypeError, ValueError):
            return None

    def _depth_summary(self, orderbook: OrderBook) -> dict[str, Any]:
        best_bid = orderbook.bids[-1].price if orderbook.bids else None
        best_ask = orderbook.asks[0].price if orderbook.asks else None
        spread = (best_ask - best_bid) if best_bid is not None and best_ask is not None else None
        return {
            "bid_levels": len(orderbook.bids),
            "ask_levels": len(orderbook.asks),
            "best_bid_cents": best_bid,
            "best_ask_cents": best_ask,
            "spread_cents": spread,
            "total_bid_size": sum(level.size for level in orderbook.bids),
            "total_ask_size": sum(level.size for level in orderbook.asks),
        }

    def normalize_orderbook(self, ticker: str, raw: Any) -> OrderBook:
        if isinstance(raw, OrderBook):
            return raw
        if not isinstance(raw, dict):
            raise DataNormalizationError("Orderbook raw data must be a dict or OrderBook")

        ts = raw.get("timestamp", raw.get("updated_at", self._now_utc().isoformat()))
        if self._is_stale(ts):
            raise DataNormalizationError(f"Orderbook for {ticker} is stale (timestamp {ts})")

        market_ticker = str(raw.get("market_ticker", ticker))
        contract_ticker = str(raw.get("contract_ticker", ticker))

        bids = self._parse_levels(raw.get("bids", []))
        asks = self._parse_levels(raw.get("asks", []))
        if not bids or not asks:
            raise DataNormalizationError(f"Orderbook for {ticker} missing bids or asks")

        parsed_ts = self._parse_ts(ts)
        book = OrderBook(
            market_ticker=market_ticker,
            contract_ticker=contract_ticker,
            bids=bids,
            asks=asks,
            timestamp=parsed_ts,
            source_ts=parsed_ts,
            freshness_score=self._freshness_score(parsed_ts),
        )
        book.depth_summary = self._depth_summary(book)
        return book

    def _parse_levels(self, raw: Any) -> list[OrderBookLevel]:
        if not isinstance(raw, list):
            return []
        levels: list[OrderBookLevel] = []
        for item in raw:
            if isinstance(item, OrderBookLevel):
                levels.append(item)
            elif isinstance(item, dict):
                price = self._to_int_optional(item.get("price"))
                size = self._to_int_optional(item.get("size", item.get("count", 0)))
                if price is not None and size is not None:
                    levels.append(OrderBookLevel(price=price, size=size))
            elif isinstance(item, (list, tuple)) and len(item) >= 2:
                price = self._to_int_optional(item[0])
                size = self._to_int_optional(item[1])
                if price is not None and size is not None:
                    levels.append(OrderBookLevel(price=price, size=size))
        return levels

    def normalize_positions(self, raw: Any) -> list[Position]:
        positions = raw.get("positions", raw) if isinstance(raw, dict) else raw
        if not isinstance(positions, list):
            raise DataNormalizationError("Positions raw data must be a list or dict with 'positions'")
        return [self._normalize_position(p) for p in positions]

    def _normalize_position(self, raw: dict[str, Any]) -> Position:
        ts = self._source_ts(raw)
        return Position(
            market_ticker=str(raw.get("market_ticker", raw.get("ticker", ""))),
            contract_ticker=str(raw.get("ticker", "")),
            side=str(raw.get("side", "")),
            quantity=int(raw.get("position", raw.get("quantity", 0))),
            avg_price_cents=int(raw.get("avg_price", raw.get("avg_price_cents", 0))),
            unrealized_pnl_cents=int(raw.get("unrealized_pnl", 0)),
            source_ts=ts,
            freshness_score=self._freshness_score(ts),
        )

    def normalize_resting_orders(self, raw: Any) -> list[RestingOrder]:
        orders = raw.get("orders", raw) if isinstance(raw, dict) else raw
        if not isinstance(orders, list):
            raise DataNormalizationError("Resting orders raw data must be a list or dict with 'orders'")
        return [self._normalize_resting_order(o) for o in orders]

    def _normalize_resting_order(self, raw: dict[str, Any]) -> RestingOrder:
        created = raw.get("created_time", raw.get("created_at", self._now_utc().isoformat()))
        ts = self._source_ts(raw, fallback=self._parse_ts(created))
        return RestingOrder(
            order_id=str(raw.get("order_id", raw.get("id", ""))),
            market_ticker=str(raw.get("market_ticker", "")),
            contract_ticker=str(raw.get("ticker", "")),
            side=str(raw.get("side", "")),
            action=str(raw.get("action", "")),
            type=str(raw.get("type", "")),
            count=int(raw.get("count", 0)),
            price_cents=int(raw.get("price", 0)),
            status=str(raw.get("status", "")),
            created_at=self._parse_ts(created),
            source_ts=ts,
            freshness_score=self._freshness_score(ts),
        )

    def normalize_fills(self, raw: Any) -> list[Fill]:
        fills = raw.get("fills", raw) if isinstance(raw, dict) else raw
        if not isinstance(fills, list):
            raise DataNormalizationError("Fills raw data must be a list or dict with 'fills'")
        return [self._normalize_fill(f) for f in fills]

    def _normalize_fill(self, raw: dict[str, Any]) -> Fill:
        ts_raw = raw.get("created_time", raw.get("timestamp", self._now_utc().isoformat()))
        ts = self._source_ts(raw, fallback=self._parse_ts(ts_raw))
        return Fill(
            fill_id=str(raw.get("fill_id", raw.get("id", ""))),
            market_ticker=str(raw.get("market_ticker", "")),
            contract_ticker=str(raw.get("ticker", "")),
            side=str(raw.get("side", "")),
            count=int(raw.get("count", 0)),
            price_cents=int(raw.get("price", 0)),
            timestamp=self._parse_ts(ts_raw),
            source_ts=ts,
            freshness_score=self._freshness_score(ts),
        )

    def to_forecast_input(self, market: Market, orderbook: OrderBook) -> ForecastInput:
        contract = market.contracts[0] if market.contracts else Contract(
            ticker=market.ticker, title=market.title, status=market.status
        )
        best_bid = orderbook.bids[-1].price if orderbook.bids else (contract.yes_bid or 0)
        best_ask = orderbook.asks[0].price if orderbook.asks else (contract.yes_ask or 0)
        return ForecastInput(
            market_ticker=market.ticker,
            contract_ticker=contract.ticker,
            yes_bid=best_bid,
            yes_ask=best_ask,
            timestamp=orderbook.timestamp,
            freshness_score=orderbook.freshness_score or Decimal("1.0"),
        )

    def normalize_full_snapshot(
        self,
        snapshot: dict[str, Any],
        contract_ticker: str,
    ) -> dict[str, Any]:
        """Normalize a full snapshot produced by KalshiRealReadOnly."""
        account = self.normalize_account(snapshot["account_status"])
        events = self.normalize_events(snapshot["events"])
        markets = self.normalize_markets(snapshot["markets"])
        orderbook = self.normalize_orderbook(contract_ticker, snapshot["orderbook"])
        positions = self.normalize_positions(snapshot["positions"])
        resting_orders = self.normalize_resting_orders(snapshot["resting_orders"])
        fills = self.normalize_fills(snapshot["fills"])
        market = next((m for m in markets if m.ticker == orderbook.market_ticker), None)
        if market is None:
            market = Market(
                ticker=orderbook.market_ticker,
                title=contract_ticker,
                status="active",
                category="unknown",
                event_ticker=orderbook.market_ticker,
            )
        forecast_input = self.to_forecast_input(market, orderbook)

        now = self._now_utc()
        min_freshness = min(
            (
                account.freshness_score or Decimal("1"),
                orderbook.freshness_score or Decimal("1"),
                *(e.freshness_score or Decimal("1") for e in events[:50]),
                *(m.freshness_score or Decimal("1") for m in markets[:50]),
            ),
            default=Decimal("1"),
        )

        return {
            "account": account,
            "events": events,
            "markets": markets,
            "orderbook": orderbook,
            "positions": positions,
            "resting_orders": resting_orders,
            "fills": fills,
            "forecast_input": forecast_input,
            "metadata": {
                "snapshot_ts": now.isoformat(),
                "contract_ticker": contract_ticker,
                "min_freshness_score": float(min_freshness),
                "orderbook_depth_summary": orderbook.depth_summary,
            },
        }
