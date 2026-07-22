from __future__ import annotations

from adapters.base import DummyAdapter
from core.ontology import Forecast


class MyeiaAdapter(DummyAdapter):
    """Non-authoritative research scaffold for myeia_adapter.

    No source-specific upstream integration is implemented here. Structural
    import tests cannot turn this shell into a tested model or production
    capability, so it always abstains until replaced by a verified adapter.
    """

    name = 'myeia_adapter'
    CATEGORY = 'commodities_energy_agriculture'
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
