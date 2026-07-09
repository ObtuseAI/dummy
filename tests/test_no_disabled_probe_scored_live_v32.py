from __future__ import annotations

from tests.v32_test_helpers import assert_current_test_report


def test_no_disabled_probe_scored_live_v32_report_passes() -> None:
    report = assert_current_test_report(__file__)

    assert report["status"] == "PASS"
    assert report["disabled_probe_scored_live"] is False
    assert report["public_probe_failure_scored_live"] is False
    assert report["unresolved_forecast_scored"] is False
