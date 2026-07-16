from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_source_truth_real_outcome_update_v20() -> None:
    report = assert_current_test_report(__file__)
    assert report["source_truth_real_outcome_update_v20_status"] == "PASS"
    assert report["source_truth_can_recommend_live_trading"] is False


def test_source_truth_real_outcome_update_enabled_credits_real_counts() -> None:
    report = v39_enabled_reports()["source_truth_real_outcome_update_v20_report.json"]
    assert report["source_health_from_real_probes_only"] is True
    assert report["score_truth_from_real_scores_only"] is True
    assert report["real_scored_count"] > 0
