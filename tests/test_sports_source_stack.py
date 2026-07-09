from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_sports_source_stack_blocks_questionable_or_unapproved_sources() -> None:
    report = assert_v20_report("sports_source_stack_report_v1.json", "sources")
    ids = {source["source_id"] for source in report["sources"]}
    assert {"SPORTSRADAR_LICENSED", "MLB_STATS_API_TERMS_REVIEW", "KAGGLE_HISTORICAL_SPORTS_FIXTURE"} <= ids
    assert report["github_adapter_candidates_only"] is True

