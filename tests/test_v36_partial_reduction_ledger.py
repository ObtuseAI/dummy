from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_v36_partial_reduction_ledger() -> None:
    report = assert_current_test_report(__file__)
    assert "partial_causes_before" in report
    assert "partial_causes_after" in report
    assert "pass_delta" in report
    assert report["execution_bridge_present"] is False
