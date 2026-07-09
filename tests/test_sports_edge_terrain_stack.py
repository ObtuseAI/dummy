from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_sports_edge_terrain_stack_has_no_odds_scraping() -> None:
    report = assert_v20_report("sports_edge_terrain_stack_report_v1.json", "required_source_needs")
    assert "no odds scraping unless approved" in report["required_source_needs"]
    assert report["live_execution_enabled"] is False

