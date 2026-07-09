from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_v36_still_passes_or_partial_expected_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["v36_still_passes_or_partial_expected_v37_status"] == "PASS"
    assert report["v36_final_verdict"] in {"PASS", "PARTIAL"}
    assert report["v35_fail_escalation_preserved"] is True
