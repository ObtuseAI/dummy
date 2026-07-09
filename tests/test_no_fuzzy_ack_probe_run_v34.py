from __future__ import annotations

from tests.v34_test_helpers import assert_current_test_report


def test_no_fuzzy_ack_probe_run_v34_report_passes() -> None:
    report = assert_current_test_report(__file__)

    assert report["status"] == "PASS"
    assert report["fuzzy_ack_probe_run"] is False
    assert report["exact_ack_required"] is True
    assert report["order_endpoints_used"] is False
