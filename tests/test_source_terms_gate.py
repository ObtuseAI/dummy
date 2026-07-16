from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_terms_gate_reports_review_required_sources() -> None:
    report = assert_v20_report("source_terms_gate_report_v1.json", "terms_review_sources")
    assert report["terms_review_required_count"] > 0
    assert report["questionable_scraping_allowed"] is False
