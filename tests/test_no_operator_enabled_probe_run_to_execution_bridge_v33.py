from __future__ import annotations

from tests.v33_test_helpers import assert_current_test_report


def test_no_operator_enabled_probe_run_to_execution_bridge_v33_report_passes() -> None:
    report = assert_current_test_report(__file__)

    assert report["status"] == "PASS"
    assert report["operator_enabled_probe_run_to_execution_bridge_present"] is False
    assert report["order_endpoints_used"] is False
    assert report["cancel_endpoints_used"] is False
