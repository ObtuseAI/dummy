from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report


def test_v40_runtime_budget() -> None:
    report = assert_current_test_report(__file__)
    assert report["v40_runtime_budget_status"] == "PASS"
    assert report["max_probe_requests"] <= 5
    assert report["per_request_timeout_seconds"] <= 12
    assert report["total_runtime_bounded"] is True
    assert report["normal_tests_live_network"] is False
    assert report["recursive_pytest_inside_unit_tests"] is False
