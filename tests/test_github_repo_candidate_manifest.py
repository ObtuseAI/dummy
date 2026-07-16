from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_github_repo_candidate_manifest_has_curated_fallback_candidates() -> None:
    report = assert_v20_report("github_repo_candidate_manifest_v1.json", "candidates")
    assert report["candidate_count"] > 0
    assert all(candidate["truth_source_role"] == "ADAPTER_CANDIDATE_ONLY" for candidate in report["candidates"])
