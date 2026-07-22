from __future__ import annotations

from adapters.base import DummyAdapter
from core.ontology import Forecast


class WeatherMcpAdapter(DummyAdapter):
    """Non-authoritative research scaffold for weather_mcp_adapter.

    No source-specific upstream integration is implemented here. Structural
    import tests cannot turn this shell into a tested model or production
    capability, so it always abstains until replaced by a verified adapter.
    """

    name = 'weather_mcp_adapter'
    CATEGORY = 'weather_prediction_market'
    FORBIDDEN_PATHS = ['create_order', 'portfolio/orders', 'orders/{order_id}', 'cancel_order', 'market_order', 'submit_order', 'polymarket']
    INTEGRATION_STATUS = "scaffold_only"
    TEST_STATUS = "pending_adapter_specific_tests"
    UPSTREAM_INTEGRATION_VERIFIED = False
    PRODUCTION_CAPABILITY = False
    PREDICTION_AUTHORITY = False
    EXECUTION_AUTHORITY = False
    DATA_ONLY = True
    PASSTHROUGH_MODEL_ZOO = False

    def to_native_forecast(self, raw) -> Forecast | None:
        del raw
        return None
