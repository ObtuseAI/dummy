from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_live_calibration_low_sample_qc_v1_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["default_path_blocked"] is True
    assert report["enabled_path_mode"] == "PIPELINE_SCORE_ONLY"
    assert report["execution_bridge_present"] is False


def test_calibration_default_path_blocked_no_sample() -> None:
    from tests.v35_test_helpers import assert_v35_report_named

    report = assert_v35_report_named("calibration_default_path_check_report.json")
    assert report["default_path_blocked"] is True
    assert report["default_sample_count"] == 0
