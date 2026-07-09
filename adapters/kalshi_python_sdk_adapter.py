from adapters.base import DummyAdapter
from core.ontology import Forecast
from forecasting.engine import ForecastEngine


class KalshiPythonSdkAdapter(DummyAdapter):
    """Reference adapter for the community Kalshi Python SDK data shapes.

    Strips SDK-specific wrappers and emits a Dummy-native Forecast. No live
    order endpoints are imported or invoked.
    """

    name = "kalshi_python_sdk"

    def to_native_forecast(self, raw) -> Forecast:
        engine = ForecastEngine()
        # Accept either a wrapped SDK response or a flat payload.
        payload = raw.get("data", raw)
        return engine.forecast(
            payload.get("market"),
            payload.get("contract"),
            payload.get("event"),
            payload.get("title"),
            payload.get("book"),
        )
