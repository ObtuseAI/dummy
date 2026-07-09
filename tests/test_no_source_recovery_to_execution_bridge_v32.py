from __future__ import annotations

from tests.v32_test_helpers import assert_current_test_report


def test_no_source_recovery_to_execution_bridge_v32_report_passes() -> None:
    report = assert_current_test_report(__file__)

    assert report["status"] == "PASS"
    assert report["source_recovery_to_execution_bridge_present"] is False
    assert report["live_submit_enabled"] is False
    assert report["order_endpoints_used"] is False
    assert report["cancel_endpoints_used"] is False
