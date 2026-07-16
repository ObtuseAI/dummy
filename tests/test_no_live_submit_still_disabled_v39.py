from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report


def test_no_live_submit_still_disabled_v39() -> None:
    report = assert_current_test_report(__file__)
    assert report["live_submit_disabled"] is True
    assert report["live_submit_enabled"] is False
    assert report["configs_live_submit_modified"] is False
