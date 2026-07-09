from __future__ import annotations


def test_github_source_miner_is_bounded_and_adapter_only() -> None:
    from predator_mesh.v20.github_source_miner import GitHubSourceMiner

    result = GitHubSourceMiner().mine()
    report = result.to_report()

    assert report["verdict"] == "PASS"
    assert report["mode"] in {"STATIC_CURATED_GITHUB_CANDIDATE", "BOUNDED_GITHUB_API"}
    assert report["budget"]["max_queries"] <= 24
    assert report["budget"]["max_repos_per_query"] <= 5
    assert report["cloned_repos"] == []
    assert report["executed_repo_code"] is False
    assert all(candidate["truth_source_role"] == "ADAPTER_CANDIDATE_ONLY" for candidate in report["repo_candidates"])

