from adapters.base import DumbyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class DartsAdapter(DumbyAdapter):
    """Reference adapter for Darts (time-series forecasting) model outputs."""

    name = "darts"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market"),
            raw.get("contract"),
            raw.get("event"),
            raw.get("title"),
            raw.get("book"),
        )
