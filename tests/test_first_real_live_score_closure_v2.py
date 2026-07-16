from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_first_real_live_score_closure_v2() -> None:
    report = assert_current_test_report(__file__)
    assert report["first_real_live_score_closure_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["score_mode"] == "OBSERVED_REAL_LIVE_PUBLIC"
    assert report["pnl_claim_made"] is False


def test_first_real_live_score_closure_enabled_path() -> None:
    report = v39_enabled_reports()["first_real_live_score_closure_v2_report.json"]
    assert report["first_real_live_score_closure_status"] == "PASS_FIRST_REAL_LIVE_SCORE"
    assert report["real_scored_count"] > 0
    assert report["low_sample_warning"] is True
