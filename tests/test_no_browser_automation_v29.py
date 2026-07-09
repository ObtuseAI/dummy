from tests.v29_test_helpers import assert_current_test_report


def test_no_browser_automation_v29_report_contract() -> None:
    report = assert_current_test_report(__file__)

    assert report["status"] == "PASS"
    assert report["browser_automation_added"] is False
    assert report["pageagent_added"] is False
    assert report["dom_extraction_added"] is False
    assert report["browser_research_lane_added"] is False
