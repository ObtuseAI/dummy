from tests.v28_test_helpers import assert_current_test_report


def test_partial_to_pass_scoreboard_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
