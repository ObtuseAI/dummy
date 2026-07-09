from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_ccxt_public_crypto_adapter_plan_has_no_execution_authority() -> None:
    report = assert_v20_report("ccxt_public_crypto_adapter_plan_report_v1.json", "adapter_status")
    assert report["adapter_status"] == "ADAPTER_PLAN_ONLY"
    assert report["order_endpoints_called"] == []

