from adapters.base import DummyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class VectorBTReferenceAdapter(DummyAdapter):
    """Reference adapter for vectorbt backtest/indicator outputs."""

    name = "vectorbt_reference"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market"),
            raw.get("contract"),
            raw.get("event"),
            raw.get("title"),
            raw.get("book"),
        )
