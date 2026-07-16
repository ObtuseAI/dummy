from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_github_mining_budget_is_bounded() -> None:
    report = assert_v20_report("github_mining_budget_report_v1.json", "budget")
    assert report["budget"]["max_queries"] <= 24
    assert report["budget"]["clone_allowed"] is False
