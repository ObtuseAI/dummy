from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_no_fake_transport_score_claimed_live_v40() -> None:
    report = assert_current_test_report(__file__)
    assert report["fake_transport_score_claimed_live"] is False
    assert report["fixture_evidence_claimed_real"] is False
    assert report["public_sample_evidence_scored_live"] is False
    assert report["stale_cached_evidence_scored_live"] is False
