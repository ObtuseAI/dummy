from adapters.base import DumbyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class KalshiOfficialReferenceAdapter(DumbyAdapter):
    """Reference adapter for Kalshi's official API documentation / demo data.

    This adapter consumes public market data shapes (e.g., market tickers,
    contract definitions, orderbook snapshots) and converts them into Dumby
    native forecasts. It deliberately does not import or call any live order
    endpoints.
    """

    name = "kalshi_official_reference"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        return engine.forecast(
            raw.get("market"),
            raw.get("contract"),
            raw.get("event"),
            raw.get("title"),
            raw.get("book"),
        )
