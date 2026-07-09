from adapters.base import DummyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class BacktraderReferenceAdapter(DummyAdapter):
    """Reference adapter for Backtrader strategy/data feeds."""

    name = "backtrader_reference"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market"),
            raw.get("contract"),
            raw.get("event"),
            raw.get("title"),
            raw.get("book"),
        )
