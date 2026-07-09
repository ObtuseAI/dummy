from tests.v26_test_helpers import assert_current_test_report


def test_live_scoring_closure_v1_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["scores_only_resolved_live_outcomes"] is True
    assert report["unresolved_forecasts_scored"] is False
    assert report["execution_bridge_present"] is False
