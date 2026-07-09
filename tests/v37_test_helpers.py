from __future__ import annotations

from typing import Any


def v37_reports(**kwargs: Any) -> dict[str, dict[str, Any]]:
    from scripts.generate_v37_reports import generate_all_v37_reports_for_tests

    kwargs.setdefault("env", {})
    return generate_all_v37_reports_for_tests(**kwargs)


def assert_v37_report_named(name: str, key: str | None = None) -> dict[str, Any]:
    reports = v37_reports()
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
        "test_dummy_autonomous_workflow_kernel_v1": "dummy_autonomous_workflow_kernel_v1_report.json",
        "test_workflow_task_queue_v1": "workflow_task_queue_v1_report.json",
        "test_autonomous_next_action_selector_v1": "autonomous_next_action_selector_v1_report.json",
        "test_build_verify_repair_loop_v1": "build_verify_repair_loop_v1_report.json",
        "test_regression_orchestrator_v1": "regression_orchestrator_v1_report.json",
        "test_report_dashboard_sync_loop_v1": "report_dashboard_sync_loop_v1_report.json",
        "test_fail_escalation_guard_v2": "fail_escalation_guard_v2_report.json",
        "test_exact_gated_real_probe_workflow_v2": "exact_gated_real_probe_workflow_v2_report.json",
        "test_evidence_closure_workflow_v1": "evidence_closure_workflow_v1_report.json",
        "test_source_truth_workflow_v18": "source_truth_workflow_v18_report.json",
        "test_operator_action_packet_v1": "operator_action_packet_v1_report.json",
        "test_autonomous_workflow_dashboard_v37": "autonomous_workflow_dashboard_v37_report.json",
        "test_dummy_mission_state_v37": "dummy_mission_state_report_v23.json",
        "test_runtime_loop_budget_v37": "runtime_loop_budget_v37_report.json",
        "test_no_secret_leak_v37": "no_secret_leak_report_v37.json",
        "test_no_direct_order_bypass_v37": "no_direct_order_bypass_report_v37.json",
        "test_no_live_submit_still_disabled_v37": "no_live_submit_still_disabled_report_v37.json",
        "test_no_caps_config_modification_v37": "no_caps_config_modification_report_v37.json",
        "test_no_browser_automation_v37": "no_browser_automation_report_v37.json",
        "test_no_mined_repo_execution_v37": "no_mined_repo_execution_report_v37.json",
        "test_no_fake_transport_score_claimed_live_v37": "no_fake_transport_score_claimed_live_report_v37.json",
        "test_no_missing_ack_probe_run_v37": "no_missing_ack_probe_run_report_v37.json",
        "test_no_fuzzy_ack_probe_run_v37": "no_fuzzy_ack_probe_run_report_v37.json",
        "test_no_workflow_kernel_to_execution_bridge_v37": "no_workflow_kernel_to_execution_bridge_report_v37.json",
        "test_no_task_queue_to_execution_bridge_v37": "no_task_queue_to_execution_bridge_report_v37.json",
        "test_no_next_action_selector_to_execution_bridge_v37": "no_next_action_selector_to_execution_bridge_report_v37.json",
        "test_no_build_verify_repair_to_execution_bridge_v37": "no_build_verify_repair_to_execution_bridge_report_v37.json",
        "test_no_real_probe_workflow_to_execution_bridge_v37": "no_real_probe_workflow_to_execution_bridge_report_v37.json",
        "test_no_evidence_closure_workflow_to_execution_bridge_v37": "no_evidence_closure_workflow_to_execution_bridge_report_v37.json",
        "test_no_operator_action_packet_to_execution_bridge_v37": "no_operator_action_packet_to_execution_bridge_report_v37.json",
        "test_v36_still_passes_or_partial_expected_v37": "v36_still_passes_or_partial_expected_v37_report.json",
    }
    stem = test_file.rsplit("/", 1)[-1].rsplit("\\", 1)[-1].removesuffix(".py")
    return assert_v37_report_named(candidates[stem])
