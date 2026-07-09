from tests.v26_test_helpers import assert_current_test_report


def test_report_chain_runtime_profiler_v9_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["read_only_only"] is True
