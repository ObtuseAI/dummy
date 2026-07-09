from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report, v40_enabled_reports


def test_real_calibration_sample_growth_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["calibration_sample_growth_status"] == "PASS_BASELINE_ONLY_LOW_SAMPLE"
    assert report["calibration_tier"] == "LOW_SAMPLE"
    assert report["live_trading_readiness_claim"] is False


def test_real_calibration_sample_growth_v1_enabled() -> None:
    report = v40_enabled_reports()["real_calibration_sample_growth_v1_report.json"]
    assert report["calibration_sample_growth_status"] == "PASS_REAL_CALIBRATION_SAMPLE_GROWTH"
    assert report["cumulative_real_scored_count"] > report["baseline_real_scored_count"]
    assert report["calibration_tier"] in {"LOW_SAMPLE", "EARLY_SAMPLE", "DEVELOPING_SAMPLE"}
