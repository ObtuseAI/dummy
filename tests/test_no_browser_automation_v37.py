from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_no_browser_automation_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["safety_status"] == "PASS"
    assert report["browser_automation_added"] is False
    assert report["pageagent_added"] is False
    assert report["dom_extraction_added"] is False
