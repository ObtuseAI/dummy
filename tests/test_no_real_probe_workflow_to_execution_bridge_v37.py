from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_no_real_probe_workflow_to_execution_bridge_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["safety_status"] == "PASS"
    assert report["lane_to_execution_bridge_present"] is False
    assert report["private_endpoints_used"] is False
