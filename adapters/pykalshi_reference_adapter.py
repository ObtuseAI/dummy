from adapters.base import DumbyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class PyKalshiReferenceAdapter(DumbyAdapter):
    """Reference adapter for pykalshi-style payloads.

    Normalizes legacy field names into Dumby's native contract/book model.
    """

    name = "pykalshi_reference"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market", raw.get("market_ticker")),
            raw.get("contract", raw.get("contract_ticker")),
            raw.get("event", raw.get("event_ticker")),
            raw.get("title", raw.get("contract_title")),
            raw.get("book", raw.get("orderbook")),
        )
