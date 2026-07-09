from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_live_score_sample_expansion_readiness_v1_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["sample_mode"] == "PIPELINE_SCORE_ONLY"
    assert report["current_sample_count"] == 3
    assert report["live_public_eligible"] is False
    assert report["next_safe_step"].startswith("run exact-gate")
    assert report["execution_bridge_present"] is False


def test_low_sample_status_honest() -> None:
    from tests.v35_test_helpers import assert_v35_report_named

    report = assert_v35_report_named("live_score_low_sample_status_report.json")
    assert report["low_sample"] is True
