from __future__ import annotations

from tests.v37_test_helpers import assert_current_test_report


def test_regression_orchestrator_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["regression_orchestrator_status"] == "PASS"
    assert report["no_recursive_pytest_inside_unit_tests"] is True
    assert report["slowest_tests_captured"] == 25
    assert "V34/V35/V36/V37 generator chain" in report["supported_regressions"]
