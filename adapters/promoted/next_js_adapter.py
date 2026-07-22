from __future__ import annotations

from adapters.base import DummyAdapter
from core.ontology import Forecast


class NextJsAdapter(DummyAdapter):
    """Non-authoritative research scaffold for next.js_adapter.

    No source-specific upstream integration is implemented here. Structural
    import tests cannot turn this shell into a tested model or production
    capability, so it always abstains until replaced by a verified adapter.
    """

    name = 'next.js_adapter'
    CATEGORY = 'dashboard_api_observability'
    FORBIDDEN_PATHS = ['create_order', 'portfolio/orders', 'orders/{order_id}', 'cancel_order', 'market_order', 'submit_order', 'polymarket']
    INTEGRATION_STATUS = "scaffold_only"
    TEST_STATUS = "pending_adapter_specific_tests"
    UPSTREAM_INTEGRATION_VERIFIED = False
    PRODUCTION_CAPABILITY = False
    PREDICTION_AUTHORITY = False
    EXECUTION_AUTHORITY = False
    DATA_ONLY = False
    PASSTHROUGH_MODEL_ZOO = False

    def to_native_forecast(self, raw) -> Forecast | None:
        del raw
        return None
