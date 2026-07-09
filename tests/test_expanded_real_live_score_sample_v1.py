from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report, v40_enabled_reports


def test_expanded_real_live_score_sample_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["score_mode"] == "OBSERVED_REAL_LIVE_PUBLIC"
    assert report["v40_new_real_scored_count"] == 0
    assert report["fake_transport_score_claimed_live"] is False
    assert report["pnl_claim_made"] is False


def test_expanded_real_live_score_sample_v1_enabled() -> None:
    report = v40_enabled_reports()["expanded_real_live_score_sample_v1_report.json"]
    assert report["expanded_real_live_score_sample_status"] == "PASS_EXPANDED_REAL_LIVE_SCORE_SAMPLE"
    assert report["v40_new_real_scored_count"] > 0
    assert report["cumulative_real_scored_count"] > report["baseline_real_scored_count"]
