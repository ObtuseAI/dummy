from __future__ import annotations

from tests.v42_test_helpers import assert_current_test_report


def test_v42_runtime_budget_is_bounded() -> None:
    report = assert_current_test_report(__file__)
    assert report["v42_runtime_budget_status"] == "PASS"
    assert report["max_optional_cycles"] == 2
    assert report["max_probe_requests"] == 12
    assert report["per_request_timeout_seconds"] <= 12
    assert report["recursive_pytest_inside_unit_tests"] is False
