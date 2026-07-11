from __future__ import annotations

from typing import Any


class RepresentativeReadOnlyTransport:
    def fetch_json(self, task: Any, timeout_seconds: int) -> dict[str, Any]:
        if task.source_family == "weather":
            return {"properties": {"temperature": {"value": 22.4}, "timestamp": "2026-07-04T12:00:00Z"}}
        if task.source_family == "crypto":
            return {"data": {"amount": "61234.12"}, "timestamp": "2026-07-04T12:00:00Z"}
        if task.source_family == "public_event":
            return [{"indicator": {"id": "FP.CPI.TOTL.ZG"}, "value": 3.2, "date": "2025"}]
        raise AssertionError(f"unexpected source family: {task.source_family}")


def v39_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from archive.report_scripts.generate_v39_reports import generate_all_v39_reports_for_tests

    return generate_all_v39_reports_for_tests(**kwargs)


def v39_enabled_reports() -> dict[str, dict[str, Any]]:
    from predator_mesh.v36.run import EXACT_GATE_ENV

    return v39_reports(env=EXACT_GATE_ENV, enable_real_probe=True, real_transport=RepresentativeReadOnlyTransport())


def assert_v39_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v39_reports()
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
        "test_v39_operator_approved_run_controller_v1": "v39_operator_approved_run_controller_v1_report.json",
        "test_exact_gate_runtime_execution_v7": "exact_gate_runtime_execution_v7_report.json",
        "test_v38_exact_gated_rerun_adapter_v1": "v38_exact_gated_rerun_adapter_v1_report.json",
        "test_real_public_source_run_v1": "real_public_source_run_v1_report.json",
        "test_live_public_evidence_completion_v2": "live_public_evidence_completion_v2_report.json",
        "test_settlement_compatible_evidence_closure_v2": "settlement_compatible_evidence_closure_v2_report.json",
        "test_real_due_observation_closure_v2": "real_due_observation_closure_v2_report.json",
        "test_first_real_live_score_closure_v2": "first_real_live_score_closure_v2_report.json",
        "test_readonly_live_intelligence_completion_v2": "readonly_live_intelligence_completion_v2_report.json",
        "test_first_live_score_milestone_completion_v2": "first_live_score_milestone_completion_v2_report.json",
        "test_live_calibration_low_sample_v2": "live_calibration_low_sample_v2_report.json",
        "test_source_truth_real_outcome_update_v20": "source_truth_real_outcome_update_v20_report.json",
        "test_completion_oriented_repair_selector_v1": "completion_oriented_repair_selector_v1_report.json",
        "test_v39_real_run_audit_ledger_v1": "v39_real_run_audit_ledger_v1_report.json",
        "test_dashboard_v39": "dashboard_v39_report_v1.json",
        "test_dummy_mission_state_v39": "dummy_mission_state_report_v25.json",
        "test_v39_runtime_budget": "v39_runtime_budget_report.json",
        "test_no_secret_leak_v39": "no_secret_leak_report_v39.json",
        "test_no_direct_order_bypass_v39": "no_direct_order_bypass_report_v39.json",
        "test_no_live_submit_still_disabled_v39": "no_live_submit_still_disabled_report_v39.json",
        "test_no_caps_config_modification_v39": "no_caps_config_modification_report_v39.json",
        "test_no_browser_automation_v39": "no_browser_automation_report_v39.json",
        "test_no_mined_repo_execution_v39": "no_mined_repo_execution_report_v39.json",
        "test_no_fake_transport_score_claimed_live_v39": "no_fake_transport_score_claimed_live_report_v39.json",
        "test_no_missing_ack_probe_run_v39": "no_missing_ack_probe_run_report_v39.json",
        "test_no_fuzzy_ack_probe_run_v39": "no_fuzzy_ack_probe_run_report_v39.json",
        "test_no_run_controller_to_execution_bridge_v39": "no_run_controller_to_execution_bridge_report_v39.json",
        "test_no_v38_rerun_to_execution_bridge_v39": "no_v38_rerun_to_execution_bridge_report_v39.json",
        "test_no_source_run_to_execution_bridge_v39": "no_source_run_to_execution_bridge_report_v39.json",
        "test_no_live_score_to_execution_bridge_v39": "no_live_score_to_execution_bridge_report_v39.json",
        "test_no_audit_ledger_to_execution_bridge_v39": "no_audit_ledger_to_execution_bridge_report_v39.json",
        "test_v38_still_passes_or_partial_expected_v39": "v38_still_passes_or_partial_expected_v39_report.json",
    }
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    return assert_v39_report_named(candidates[stem])

