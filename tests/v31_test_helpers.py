from __future__ import annotations

from pathlib import Path
from typing import Any


def v31_reports() -> dict[str, dict[str, Any]]:
    from scripts.generate_v31_reports import generate_all_v31_reports_for_tests

    return generate_all_v31_reports_for_tests(enable_network=False)


def assert_v31_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v31_reports()
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
        "test_dashboard_v31": "dashboard_v31_report_v1.json",
        "test_public_probe_cache_and_audit_v1": "public_probe_cache_writer_v1_report.json",
        "test_probe_source_truth_v12": "probe_source_truth_v12_report.json",
        "test_no_public_probe_gate_to_execution_bridge_v31": "no_public_probe_gate_to_execution_bridge_report_v31.json",
        "test_no_public_probe_failure_scored_live_v31": "no_public_probe_failure_scored_live_report_v31.json",
    }
    return assert_v31_report_named(candidates[stem])
