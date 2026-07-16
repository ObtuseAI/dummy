from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report, v39_enabled_reports


def test_v39_real_run_audit_ledger_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["v39_real_run_audit_ledger_status"] == "PASS"
    assert report["append_only_modeled"] is True
    assert report["request_count"] == 0


def test_v39_real_run_audit_ledger_enabled_records_counts() -> None:
    report = v39_enabled_reports()["v39_real_run_audit_ledger_v1_report.json"]
    assert report["append_only_modeled"] is True
    assert report["request_count"] > 0
    assert report["evidence_count"] > 0
    assert report["score_count"] > 0
