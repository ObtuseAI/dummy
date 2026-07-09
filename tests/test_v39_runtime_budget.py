from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report


def test_v39_runtime_budget() -> None:
    report = assert_current_test_report(__file__)
    assert report["v39_runtime_budget_status"] == "PASS"
    assert report["max_probe_requests"] <= 4
    assert report["normal_tests_live_network"] is False
    assert report["recursive_pytest_inside_unit_tests"] is False
    assert report["browser_calls_allowed"] is False

