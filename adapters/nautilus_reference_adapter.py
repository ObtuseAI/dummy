from adapters.base import DumbyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class NautilusReferenceAdapter(DumbyAdapter):
    """Reference adapter for Nautilus Trader data/event shapes."""

    name = "nautilus_reference"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market"),
            raw.get("contract"),
            raw.get("event"),
            raw.get("title"),
            raw.get("book"),
        )
