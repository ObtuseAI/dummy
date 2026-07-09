from adapters.base import DummyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class FinRLMetaReferenceAdapter(DummyAdapter):
    """Reference adapter for FinRL-Meta (metaverse of market data) payloads."""

    name = "finrl_meta_reference"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market"),
            raw.get("contract"),
            raw.get("event"),
            raw.get("title"),
            raw.get("book"),
        )
