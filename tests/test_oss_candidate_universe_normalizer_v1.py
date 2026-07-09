from tests.v29_test_helpers import assert_v29_report_named


def test_oss_candidate_universe_normalizer_v1_preserves_current_v28_expansion() -> None:
    report = assert_v29_report_named(
        "oss_candidate_universe_normalizer_v1_report.json",
        "raw_candidate_count",
        "canonical_candidate_count",
        "unique_repository_count",
        "category_counts",
        "keyword_provenance_status",
        "candidate_count_reconciliation_status",
    )

    assert report["attachment_declared_candidate_count"] == 182
    assert report["raw_candidate_count"] >= 246
    assert report["canonical_candidate_count"] == report["unique_repository_count"]
    assert report["canonical_candidate_count"] <= report["raw_candidate_count"]
    assert report["duplicate_cluster_count"] >= 2
    assert report["candidate_count_reconciliation_status"] == "RECONCILED_TO_CURRENT_V28_ARTIFACT"

    counts = report["category_counts"]
    assert counts["sports"] >= 55
    assert counts["weather"] >= 43
    assert counts["crypto"] >= 27
    assert counts["trading"] >= 51
    assert counts["bloomberg"] >= 12
    assert counts["betting"] >= 18
    assert counts["fantasy"] >= 18

    coverage = set(report["keyword_coverage"])
    assert {
        "soccer",
        "football",
        "baseball",
        "betting",
        "wagering",
        "sportsbook",
        "gambling",
        "fantasy sports",
        "daily fantasy",
        "sports drafting",
        "weather prediction",
        "open-meteo",
        "bitcoin",
        "bloomberg alternative",
    } <= coverage
    assert report["github_mining_mode"] == "metadata_only_no_clone_no_import_no_execute"
    assert report["raw_metadata_preserved"] is True
    assert report["multi_category_supported"] is True
    assert report["mined_repo_cloned"] is False
    assert report["mined_repo_imported"] is False
    assert report["mined_repo_executed"] is False
