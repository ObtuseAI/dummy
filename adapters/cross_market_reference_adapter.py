from adapters.base import DummyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class CrossMarketReferenceAdapter(DummyAdapter):
    """Reference adapter that normalizes cross-market (Kalshi + Polymarket) payloads."""

    name = "cross_market_reference"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        payload = raw.get("normalized", raw)
        return engine.forecast(
            payload.get("market"),
            payload.get("contract"),
            payload.get("event"),
            payload.get("title"),
            payload.get("book"),
        )
