from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_github_adapter_plan_never_allows_clone_or_execution() -> None:
    report = assert_v20_report("github_adapter_plan_report_v1.json", "adapter_plans")
    assert report["no_repo_code_execution"] is True
    assert all(plan["clone_allowed"] is False and plan["execute_code_allowed"] is False for plan in report["adapter_plans"])
