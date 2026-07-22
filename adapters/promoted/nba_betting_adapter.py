from __future__ import annotations

from adapters.base import DummyAdapter
from core.ontology import Forecast


class NBABettingAdapter(DummyAdapter):
    """Non-authoritative research scaffold for NBA_Betting_adapter.

    No source-specific upstream integration is implemented here. Structural
    import tests cannot turn this shell into a tested model or production
    capability, so it always abstains until replaced by a verified adapter.
    """

    name = 'NBA_Betting_adapter'
    CATEGORY = 'sports_prediction_odds'
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
