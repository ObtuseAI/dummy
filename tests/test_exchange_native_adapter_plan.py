from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_exchange_native_adapter_plan_prioritizes_nasdaq_and_oil_orderbooks() -> None:
    report = assert_v20_report("exchange_native_adapter_plan_report_v1.json", "exchange_native_sources")
    assert "CME_NQ_ES_FUTURES" in report["nasdaq_orderbook_priority"]
    assert "CME_CL_ENERGY_FUTURES" in report["oil_orderbook_priority"]

