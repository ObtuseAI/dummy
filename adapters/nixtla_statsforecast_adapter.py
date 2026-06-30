from adapters.base import DumbyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class NixtlaStatsforecastAdapter(DumbyAdapter):
    """Reference adapter for Nixtla StatsForecast model outputs."""

    name = "nixtla_statsforecast"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market"),
            raw.get("contract"),
            raw.get("event"),
            raw.get("title"),
            raw.get("book"),
        )
