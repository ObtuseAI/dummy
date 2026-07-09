from __future__ import annotations

from tests.v34_test_helpers import assert_current_test_report


def test_no_missing_ack_probe_run_v34_report_passes() -> None:
    report = assert_current_test_report(__file__)

    assert report["status"] == "PASS"
    assert report["missing_ack_probe_run"] is False
    assert report["probe_run_count"] == 0
    assert report["live_submit_enabled"] is False
