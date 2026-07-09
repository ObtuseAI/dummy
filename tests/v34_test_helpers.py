from __future__ import annotations

from pathlib import Path
from typing import Any


def v34_reports() -> dict[str, dict[str, Any]]:
    from scripts.generate_v34_reports import generate_all_v34_reports_for_tests

    return generate_all_v34_reports_for_tests(enable_network=False)


def assert_v34_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v34_reports()
    assert name in reports
    report = reports[name]
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["execution_bridge_present"] is False
    if key is not None:
        assert key in report
    return report


def assert_current_test_report(test_file: str) -> dict[str, Any]:
    stem = Path(test_file).stem
    candidates = {
        "test_probe_run_artifact_reconciliation_cache_v4": "probe_run_artifact_reconciliation_cache_v4_report.json",
        "test_reconciled_probe_audit_ledger_v3": "reconciled_probe_audit_ledger_v3_report.json",
        "test_sports_probe_exclusion_recheck_v5": "sports_probe_exclusion_recheck_v5_report.json",
        "test_source_truth_probe_reconciliation_v15": "source_truth_probe_reconciliation_v15_report.json",
        "test_no_missing_ack_probe_run_v34": "no_missing_ack_probe_run_report_v34.json",
        "test_no_fuzzy_ack_probe_run_v34": "no_fuzzy_ack_probe_run_report_v34.json",
        "test_no_operator_enabled_probe_run_to_execution_bridge_v34": "no_operator_enabled_probe_run_to_execution_bridge_report_v34.json",
        "test_dashboard_v34": "dashboard_v34_report_v1.json",
        "test_public_probe_transport_guard_v1": "dashboard_v34_report_v1.json",
    }
    return assert_v34_report_named(candidates[stem])
