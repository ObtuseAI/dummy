from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_timeout_guards_still_intact_v20_reports_pass() -> None:
    assert_v20_report("source_universe_runtime_budget_report_v1.json", "pytest_timeout_seconds")
    assert_v20_report("github_mining_runtime_guard_report_v1.json", "max_queries")
    assert_v20_report("official_adapter_runtime_guard_report_v1.json", "timeout_seconds")
