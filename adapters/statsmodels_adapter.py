from adapters.base import DummyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class StatsmodelsAdapter(DummyAdapter):
    """Reference adapter for statsmodels forecasting results."""

    name = "statsmodels"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market"),
            raw.get("contract"),
            raw.get("event"),
            raw.get("title"),
            raw.get("book"),
        )
