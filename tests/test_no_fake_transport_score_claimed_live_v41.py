from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_no_fake_transport_score_claimed_live_v41() -> None:
    report = assert_current_test_report(__file__)
    assert report["fake_transport_score_claimed_live"] is False
