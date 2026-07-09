from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_settlement_compatible_evidence_closure_v2() -> None:
    report = assert_current_test_report(__file__)
    assert report["settlement_compatible_evidence_closure_status"] == "PARTIAL_BLOCKED_MISSING_EXACT_GATE"
    assert report["scores_created_here"] is False


def test_settlement_compatible_evidence_enabled_path() -> None:
    report = v39_enabled_reports()["settlement_compatible_evidence_closure_v2_report.json"]
    assert report["settlement_compatible_evidence_closure_status"] == "PASS_SETTLEMENT_COMPATIBLE_EVIDENCE"
    assert report["settlement_compatible_evidence_count"] > 0
    assert report["validates_family_market_metric_source_timestamp"] is True

