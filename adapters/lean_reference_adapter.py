from adapters.base import DumbyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class LeanReferenceAdapter(DumbyAdapter):
    """Reference adapter for QuantConnect Lean algorithm output shapes."""

    name = "lean_reference"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market"),
            raw.get("contract"),
            raw.get("event"),
            raw.get("title"),
            raw.get("book"),
        )
