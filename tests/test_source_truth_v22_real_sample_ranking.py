from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_source_truth_v22_real_sample_ranking_stays_read_only() -> None:
    report = assert_current_test_report(__file__)
    assert report["source_truth_v22_status"] == "PASS"
    assert report["score_truth_from_real_scores_only"] is True
    assert report["source_truth_can_recommend_live_trading"] is False
    assert report["source_truth_to_execution_bridge_present"] is False
