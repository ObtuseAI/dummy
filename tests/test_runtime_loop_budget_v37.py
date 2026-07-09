from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_runtime_loop_budget_v37() -> None:
    report = assert_current_test_report(__file__)
    assert report["runtime_loop_budget_v37_status"] == "PASS"
    assert report["max_workflow_iterations"] == 1
    assert report["max_repair_attempts"] == 2
    assert report["normal_tests_live_network"] is False
    assert report["browser_calls_allowed"] is False
