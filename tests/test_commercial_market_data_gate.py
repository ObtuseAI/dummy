from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_commercial_market_data_gate_blocks_calls_without_approval() -> None:
    report = assert_v20_report("commercial_market_data_gate_report_v1.json", "commercial_network_calls")
    assert report["commercial_network_calls"] == 0
    assert report["commercial_sources_activated_without_approval"] == []
