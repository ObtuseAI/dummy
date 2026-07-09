from __future__ import annotations

from tests.v31_test_helpers import assert_current_test_report


def test_no_public_probe_failure_scored_live_v31_report_passes() -> None:
    report = assert_current_test_report(__file__)

    assert report["status"] == "PASS"
    assert report["public_probe_failure_scored_live"] is False
    assert report["source_unavailable_forecast_scored"] is False
    assert report["ambiguous_settlement_scored"] is False
    assert report["not_due_forecast_scored"] is False
