from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_licensed_adapter_no_call_guard_blocks_commercial_calls() -> None:
    report = assert_v20_report("licensed_adapter_no_call_guard_report_v1.json", "commercial_network_calls_without_approval")
    assert report["commercial_network_calls_without_approval"] == 0
