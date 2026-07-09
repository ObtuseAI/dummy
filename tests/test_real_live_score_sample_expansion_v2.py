from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report, v41_enabled_reports


def test_real_live_score_sample_expansion_v2_scores_observed_real_live_public_only() -> None:
    report = assert_current_test_report(__file__)
    assert report["scores_only_observed_real_live_public"] is True
    assert report["v41_new_real_scored_count"] == 0
    enabled = v41_enabled_reports()["real_live_score_sample_expansion_v2_report.json"]
    assert enabled["v41_new_real_scored_count"] >= 6
    assert enabled["score_mode"] == "OBSERVED_REAL_LIVE_PUBLIC"
    assert enabled["no_score_to_execution_bridge"] is True
