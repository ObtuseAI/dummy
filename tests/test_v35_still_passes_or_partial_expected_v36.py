from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_v35_still_passes_or_partial_expected_v36() -> None:
    report = assert_current_test_report(__file__)
    assert report["v35_fail_escalation_preserved"] is True
    assert report["v35_final_verdict"] in {"PASS", "PARTIAL"}
    assert report["execution_bridge_present"] is False
