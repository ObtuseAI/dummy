from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_no_browser_automation_v41() -> None:
    report = assert_current_test_report(__file__)
    assert report["browser_automation_added"] is False
    assert report["dom_extraction_added"] is False
