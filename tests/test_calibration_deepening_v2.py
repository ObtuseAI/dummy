from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report, v41_enabled_reports


def test_calibration_deepening_v2_uses_real_scores_only() -> None:
    report = assert_current_test_report(__file__)
    assert report["calibration_tier"] == "LOW_SAMPLE"
    assert report["calibration_updates_only_from_real_score"] is True
    enabled = v41_enabled_reports()["calibration_deepening_v2_report.json"]
    assert enabled["calibration_tier"] == "EARLY_SAMPLE"
    assert "not statistically validated" in enabled["calibration_warning"].lower()
