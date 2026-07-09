from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_no_sports_source_activation_v41() -> None:
    report = assert_current_test_report(__file__)
    assert report["sports_source_activated"] is False
    assert report["sports_excluded"] is True
