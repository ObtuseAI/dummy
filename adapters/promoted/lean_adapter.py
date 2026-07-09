from __future__ import annotations

from adapters.base import DummyAdapter
from core.ontology import Forecast, OrderBook, OrderBookLevel
from datetime import datetime, timezone
from forecasting.engine import ForecastEngine


class LeanAdapter(DummyAdapter):
    """Lightweight Dummy-native adapter wrapper for Lean_adapter.

    This module only transforms raw data into Dummy-native Forecast objects.
    It does not import or call any live order endpoint.
    """

    name = "Lean_adapter"
    FORBIDDEN_PATHS = ['create_order', 'portfolio/orders', 'orders/{order_id}', 'cancel_order', 'market_order', 'submit_order', 'polymarket']

    def to_native_forecast(self, raw) -> Forecast:
        book = raw.get("book") or raw.get("orderbook")
        if book is None:
            market = raw.get("market", raw.get("market_ticker", ""))
            contract = raw.get("contract", raw.get("contract_ticker", ""))
            book = OrderBook(
                market_ticker=market,
                contract_ticker=contract,
                bids=[OrderBookLevel(price=45, size=10)],
                asks=[OrderBookLevel(price=55, size=10)],
                timestamp=datetime.now(timezone.utc),
            )
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market", raw.get("market_ticker", "")),
            raw.get("contract", raw.get("contract_ticker", "")),
            raw.get("event", raw.get("event_title", "")),
            raw.get("title", raw.get("contract_title", "")),
            book,
        )
