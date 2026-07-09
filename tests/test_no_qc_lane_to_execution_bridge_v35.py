from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_no_qc_lane_to_execution_bridge_v35() -> None:
    report = assert_current_test_report(__file__)
    assert report["safety_status"] == "PASS"
    assert report["lane_to_execution_bridge_present"] is False
    assert report["execution_bridge_present"] is False
