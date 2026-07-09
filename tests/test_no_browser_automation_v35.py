from __future__ import annotations

from tests.v35_test_helpers import assert_current_test_report


def test_no_browser_automation_v35() -> None:
    report = assert_current_test_report(__file__)
    assert report["safety_status"] == "PASS"
    assert report["browser_automation_added"] is False
    assert report["pageagent_added"] is False
    assert report["dom_extraction_added"] is False
    assert report["browser_research_lane_added"] is False
    assert report["mined_repo_cloned"] is False
    assert report["mined_repo_imported"] is False
    assert report["mined_repo_executed"] is False
    assert report["execution_bridge_present"] is False
