from adapters.base import DumbyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class CrossMarketReferenceAdapter(DumbyAdapter):
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
