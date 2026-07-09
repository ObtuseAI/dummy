from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report, v42_enabled_reports


def test_calibration_tier_governor_v1_blocks_premature_trading_readiness() -> None:
    report = assert_current_test_report(__file__)
    assert report["calibration_tier_governor_status"] == "PASS"
    assert report["calibration_tier"] == "EARLY_SAMPLE"
    enabled = v42_enabled_reports()["calibration_tier_governor_v1_report.json"]
    assert enabled["calibration_tier"] == "EARLY_SAMPLE"
    assert enabled["stable_sample_candidate"] is False
    assert enabled["live_trading_readiness_claim"] is False
