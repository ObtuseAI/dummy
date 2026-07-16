from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_first_live_score_milestone_completion_v2() -> None:
    report = assert_current_test_report(__file__)
    assert report["first_live_score_milestone_status"] in {"PARTIAL_NO_OBSERVED_REAL_LIVE_PUBLIC_OUTCOME", "PARTIAL_BLOCKED_MISSING_EXACT_GATE"}


def test_first_live_score_milestone_enabled_path_passes() -> None:
    report = v39_enabled_reports()["first_live_score_milestone_completion_v2_report.json"]
    assert report["first_live_score_milestone_status"] == "PASS_FIRST_REAL_LIVE_PUBLIC_SCORE"
    assert report["real_scored_count"] > 0
    assert report["low_sample_warning"] is True
