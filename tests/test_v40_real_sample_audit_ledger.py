from __future__ import annotations

from tests.v40_test_helpers import assert_current_test_report, v40_enabled_reports


def test_v40_real_sample_audit_ledger() -> None:
    report = assert_current_test_report(__file__)
    assert report["append_only_modeled"] is True
    assert report["baseline_real_scored_count"] >= 3
    assert report["v40_real_sample_audit_ledger_status"] == "PASS"
    assert report["safety_proof"]["execution_bridge_present"] is False


def test_v40_real_sample_audit_ledger_enabled_records_new_counts() -> None:
    report = v40_enabled_reports()["v40_real_sample_audit_ledger_report.json"]
    assert report["v40_new_real_scored_count"] > 0
    assert report["cumulative_real_scored_count"] > report["baseline_real_scored_count"]
