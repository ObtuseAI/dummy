from __future__ import annotations

from typing import Any


def v38_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v38_reports import generate_all_v38_reports_for_tests

    kwargs.setdefault("env", {})
    return generate_all_v38_reports_for_tests(**kwargs)


def assert_v38_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v38_reports()
    assert name in reports, f"missing report: {name}"
    report = reports[name]
    assert report["live_submit_disabled"] is True
    assert report["caps_unchanged"] is True
    assert report["execution_bridge_present"] is False
    assert report["order_endpoints_used"] is False
    assert report["cancel_endpoints_used"] is False
    assert report["browser_automation_added"] is False
    assert report["mined_repo_executed"] is False
    if key is not None:
        assert key in report, f"missing key {key} in {name}"
    return report


def assert_current_test_report(test_file: str) -> dict[str, Any]:
    candidates = {
        "test_v38_required_report_manifest": "operator_gated_real_readonly_probe_completion_v1_report.json",
        "test_v38_gate_runtime": "v38_exact_operator_gate_recheck_v1_report.json",
        "test_v38_enabled_fake_transport_evidence_score_chain": "v38_real_probe_evidence_score_chain_v1_report.json",
        "test_v38_safety_invariants": "v38_safety_invariant_report_v1.json",
        "test_autonomous_workflow_dashboard_v38": "dashboard_v38_report_v1.json",
        "test_v37_still_passes_or_partial_expected_v38": "v37_still_passes_or_partial_expected_v38_report.json",
    }
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    return assert_v38_report_named(candidates[stem])
