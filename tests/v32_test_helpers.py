from __future__ import annotations

from pathlib import Path
from typing import Any


def v32_reports() -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v32_reports import generate_all_v32_reports_for_tests

    return generate_all_v32_reports_for_tests(enable_network=False)


def assert_v32_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v32_reports()
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
        "test_dashboard_v32": "dashboard_v32_report_v1.json",
        "test_probe_cache_replay_separation_v2": "probe_cache_replay_separation_v2_report.json",
        "test_source_truth_recovery_closure_v13": "source_truth_recovery_closure_v13_report.json",
        "test_no_source_recovery_to_execution_bridge_v32": "no_source_recovery_to_execution_bridge_report_v32.json",
        "test_no_disabled_probe_scored_live_v32": "no_disabled_probe_scored_live_report_v32.json",
    }
    return assert_v32_report_named(candidates[stem])
