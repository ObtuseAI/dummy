from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_no_missing_ack_probe_run_v40() -> None:
    report = assert_current_test_report(__file__)
    assert report["ack_decision"] == "FAIL_MISSING_ACK"
    assert report["missing_ack_probe_run"] is False
    assert report["v40_new_real_probe_count"] == 0
