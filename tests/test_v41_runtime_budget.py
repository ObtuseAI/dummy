from __future__ import annotations

from tests.v41_test_helpers import assert_current_test_report


def test_v41_runtime_budget_is_bounded() -> None:
    report = assert_current_test_report(__file__)
    assert report["v41_runtime_budget_status"] == "PASS"
    assert report["max_cycles"] == 3
    assert report["max_probe_requests"] == 12
    assert report["per_request_timeout_seconds"] <= 12
    assert report["recursive_pytest_inside_unit_tests"] is False
