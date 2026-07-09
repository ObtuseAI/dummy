from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_github_mining_runtime_guard_prevents_clone_and_execution() -> None:
    report = assert_v20_report("github_mining_runtime_guard_report_v1.json", "max_queries")
    assert report["no_unbounded_cloning"] is True
    assert report["no_repo_code_execution"] is True

