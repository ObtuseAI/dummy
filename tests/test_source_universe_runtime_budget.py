from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_universe_runtime_budget_keeps_pytest_timeout() -> None:
    report = assert_v20_report("source_universe_runtime_budget_report_v1.json", "pytest_timeout_seconds")
    assert report["pytest_timeout_seconds"] == 60
