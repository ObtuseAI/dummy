from __future__ import annotations

from tests.v45_test_helpers import v45_enabled_reports


def test_stable_sample_candidate_prep_remains_locked_below_100_scores() -> None:
    report = v45_enabled_reports()["stable_sample_candidate_prep_v1_report.json"]
    assert report["stable_sample_prep_status"] == "LOCKED_INSUFFICIENT_100_REAL_SCORES"
    assert report["stable_sample_candidate_unlocked"] is False
    assert report["stable_sample_threshold_policy"]["STABLE_SAMPLE_CANDIDATE"] == "100+ real scores plus quality, diversity, drift, and stability gates"
    assert report["cumulative_real_scored_count"] < 100
    assert report["live_trading_readiness_claim"] is False
