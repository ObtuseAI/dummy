from __future__ import annotations

from tests.v20_test_helpers import assert_v20_report


def test_evidence_sufficiency_verdict_marks_insufficient_real_edge_evidence() -> None:
    report = assert_v20_report("evidence_sufficiency_verdict_report_v1.json", "verdicts")
    assert report["insufficient_count"] > 0
    assert report["fixture_evidence_claimed_real"] is False
