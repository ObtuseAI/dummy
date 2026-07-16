from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_evidence_priority_score_prioritizes_nasdaq_and_oil() -> None:
    report = assert_v20_report("evidence_priority_score_report_v1.json", "highest_priority_routes")
    assert report["highest_priority_routes"][:2] == ["nasdaq", "oil"]
