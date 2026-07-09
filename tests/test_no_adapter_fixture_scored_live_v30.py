from tests.v30_test_helpers import assert_current_test_report


def test_no_adapter_fixture_scored_live_v30_report_contract() -> None:
    report = assert_current_test_report(__file__)

    assert report["status"] == "PASS"
    assert report["adapter_fixture_scored_live"] is False
    assert report["adapter_dry_run_scored_live"] is False
    assert report["live_scored_count"] == 0
