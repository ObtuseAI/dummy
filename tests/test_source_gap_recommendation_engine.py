from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_gap_recommendation_engine_highlights_nasdaq_and_oil() -> None:
    report = assert_v20_report("source_gap_recommendation_engine_report_v1.json", "highest_priority_missing_source_gaps")
    assert report["nasdaq_and_oil_highlighted"] is True
    assert report["highest_priority_missing_source_gaps"][0]["domain"] == "nasdaq_index_direction"
