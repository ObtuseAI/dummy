from __future__ import annotations

from pathlib import Path
from typing import Any


def v33_reports() -> dict[str, dict[str, Any]]:
    from scripts.generate_v33_reports import generate_all_v33_reports_for_tests

    return generate_all_v33_reports_for_tests(enable_network=False)


def assert_v33_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v33_reports()
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
        "test_public_probe_artifact_cache_v3": "public_probe_artifact_cache_v3_report.json",
        "test_enabled_probe_audit_ledger_v2": "enabled_probe_audit_ledger_v2_report.json",
        "test_sports_probe_exclusion_guard_v4": "sports_probe_exclusion_guard_v4_report.json",
        "test_source_truth_enabled_probe_evidence_v14": "source_truth_enabled_probe_evidence_v14_report.json",
        "test_no_missing_ack_probe_run_v33": "no_missing_ack_probe_run_report_v33.json",
        "test_no_fuzzy_ack_probe_run_v33": "no_fuzzy_ack_probe_run_report_v33.json",
        "test_no_operator_enabled_probe_run_to_execution_bridge_v33": "no_operator_enabled_probe_run_to_execution_bridge_report_v33.json",
        "test_dashboard_v33": "dashboard_v33_report_v1.json",
    }
    return assert_v33_report_named(candidates[stem])
