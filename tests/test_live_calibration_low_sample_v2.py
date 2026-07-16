from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_live_calibration_low_sample_v2() -> None:
    report = assert_current_test_report(__file__)
    assert report["live_calibration_low_sample_status"] == "PARTIAL_NO_REAL_SCORE"
    assert report["live_trading_readiness_claim"] is False


def test_live_calibration_low_sample_enabled_path_warns() -> None:
    report = v39_enabled_reports()["live_calibration_low_sample_v2_report.json"]
    assert report["live_calibration_low_sample_status"] == "PASS_LOW_SAMPLE_CALIBRATION"
    assert report["low_sample_warning"] is True
    assert report["real_scored_count"] > 0
