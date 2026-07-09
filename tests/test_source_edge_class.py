from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_source_edge_class_report_marks_high_edge_and_github_adapter_candidates() -> None:
    report = assert_v20_report("source_edge_class_report_v1.json", "edge_class_counts")
    assert report["high_edge_source_count"] > 0
    assert report["github_adapter_candidate_count"] > 0

