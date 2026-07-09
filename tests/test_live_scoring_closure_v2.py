from tests.v27_test_helpers import assert_current_test_report


def test_live_scoring_closure_v2_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
    assert report["scores_only_resolved_live_outcomes"] is True
    assert report["ambiguous_settlement_scored"] is False
    assert report["source_unavailable_forecast_scored"] is False
    assert report["not_due_forecast_scored"] is False
    assert report["execution_bridge_present"] is False
