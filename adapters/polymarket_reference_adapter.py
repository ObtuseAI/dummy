from adapters.base import DumbyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class PolymarketReferenceAdapter(DumbyAdapter):
    """Reference adapter for Polymarket-style prediction market data."""

    name = "polymarket_reference"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        payload = raw.get("data", raw)
        return engine.forecast(
            payload.get("market"),
            payload.get("contract"),
            payload.get("event"),
            payload.get("title"),
            payload.get("book"),
        )
