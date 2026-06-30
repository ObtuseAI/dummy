from adapters.base import DumbyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class RDAgentReferenceAdapter(DumbyAdapter):
    """Reference adapter for RD-Agent (research-and-development agent) outputs."""

    name = "rd_agent_reference"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market"),
            raw.get("contract"),
            raw.get("event"),
            raw.get("title"),
            raw.get("book"),
        )
