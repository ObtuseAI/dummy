from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_github_source_stack_is_adapter_candidate_only() -> None:
    report = assert_v20_report("github_source_stack_report_v1.json", "sources")
    github_sources = [source for source in report["sources"] if source["source_class"] == "github_adapter_candidate"]
    assert github_sources
    assert all(source["truth_source_role"] == "ADAPTER_CANDIDATE_ONLY" for source in github_sources)
