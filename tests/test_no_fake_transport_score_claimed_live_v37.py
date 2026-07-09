from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_no_fake_transport_score_claimed_live_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["safety_status"] == "PASS"
    assert report["fake_transport_score_claimed_live"] is False
    assert report["fake_pipeline_score_count"] >= 0
    assert report["live_scored_count"] == 0
