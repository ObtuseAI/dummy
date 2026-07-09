from tests.v26_test_helpers import assert_current_test_report


def test_replay_to_live_candidate_selector_v1_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
