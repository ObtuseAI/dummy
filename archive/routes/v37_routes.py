from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v37.reports import V37ReportFactory

router = APIRouter(prefix="/api/v37", tags=["v37"])


def _reports() -> dict[str, dict[str, Any]]:
    return V37ReportFactory().build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/workflow-kernel")
async def workflow_kernel() -> dict[str, Any]:
    return _slice(
        "dummy_autonomous_workflow_kernel_v1_report.json",
        "workflow_run_state_v1_report.json",
        "workflow_mode_decision_v1_report.json",
        "workflow_lane_registry_v1_report.json",
        "workflow_safety_envelope_v1_report.json",
        "workflow_run_result_v1_report.json",
        "workflow_kernel_blocker_v1_report.json",
    )


@router.get("/task-queue")
async def task_queue() -> dict[str, Any]:
    return _slice(
        "workflow_task_queue_v1_report.json",
        "workflow_task_record_v1_report.json",
        "workflow_task_priority_v1_report.json",
        "workflow_task_dependency_v1_report.json",
        "workflow_task_acceptance_gate_v1_report.json",
        "workflow_task_blocker_v1_report.json",
    )


@router.get("/next-action")
async def next_action() -> dict[str, Any]:
    return _slice(
        "autonomous_next_action_selector_v1_report.json",
        "next_action_candidate_v1_report.json",
        "next_action_decision_v1_report.json",
        "next_action_reason_v1_report.json",
        "next_action_safety_check_v1_report.json",
        "next_action_blocker_v1_report.json",
    )


@router.get("/build-verify-repair")
async def build_verify_repair() -> dict[str, Any]:
    return _slice(
        "build_verify_repair_loop_v1_report.json",
        "build_verify_command_plan_v1_report.json",
        "build_verify_result_v1_report.json",
        "build_repair_attempt_v1_report.json",
        "build_repair_decision_v1_report.json",
        "build_repair_blocker_v1_report.json",
    )


@router.get("/regression-orchestrator")
async def regression_orchestrator() -> dict[str, Any]:
    return _slice(
        "regression_orchestrator_v1_report.json",
        "regression_command_set_v1_report.json",
        "regression_result_summary_v1_report.json",
        "regression_failure_classifier_v1_report.json",
        "regression_slow_test_ledger_v1_report.json",
        "regression_orchestrator_blocker_v1_report.json",
    )


@router.get("/report-dashboard-sync")
async def report_dashboard_sync() -> dict[str, Any]:
    return _slice(
        "report_dashboard_sync_loop_v1_report.json",
        "report_manifest_sync_check_v1_report.json",
        "final_report_sync_check_v1_report.json",
        "tests_summary_sync_check_v1_report.json",
        "dashboard_route_sync_check_v1_report.json",
        "dashboard_payload_sync_check_v1_report.json",
        "report_dashboard_sync_blocker_v1_report.json",
    )


@router.get("/fail-escalation")
async def fail_escalation() -> dict[str, Any]:
    return _slice(
        "fail_escalation_guard_v2_report.json",
        "component_fail_scan_v1_report.json",
        "build_fail_escalation_check_v1_report.json",
        "route_smoke_fail_escalation_check_v1_report.json",
        "safety_fail_escalation_check_v1_report.json",
        "fail_escalation_decision_v1_report.json",
        "fail_escalation_blocker_v1_report.json",
    )


@router.get("/real-probe-workflow")
async def real_probe_workflow() -> dict[str, Any]:
    return _slice(
        "exact_gated_real_probe_workflow_v2_report.json",
        "real_probe_workflow_gate_check_v1_report.json",
        "real_probe_workflow_run_plan_v1_report.json",
        "real_probe_workflow_run_result_v1_report.json",
        "real_probe_workflow_evidence_result_v1_report.json",
        "real_probe_workflow_blocker_v1_report.json",
    )


@router.get("/evidence-closure")
async def evidence_closure() -> dict[str, Any]:
    return _slice(
        "evidence_closure_workflow_v1_report.json",
        "evidence_closure_input_v1_report.json",
        "settlement_join_workflow_v1_report.json",
        "due_observation_workflow_v1_report.json",
        "live_score_workflow_v1_report.json",
        "calibration_workflow_v1_report.json",
        "evidence_closure_workflow_blocker_v1_report.json",
    )


@router.get("/source-truth-workflow")
async def source_truth_workflow() -> dict[str, Any]:
    return _slice(
        "source_truth_workflow_v18_report.json",
        "source_truth_workflow_signal_v1_report.json",
        "source_truth_workflow_update_v1_report.json",
        "source_truth_workflow_action_v1_report.json",
        "source_truth_workflow_blocker_v1_report.json",
    )


@router.get("/operator-actions")
async def operator_actions() -> dict[str, Any]:
    return _slice(
        "operator_action_packet_v1_report.json",
        "operator_probe_gate_packet_v1_report.json",
        "operator_sports_approval_packet_v1_report.json",
        "operator_failure_review_packet_v1_report.json",
        "operator_action_blocker_v1_report.json",
    )


@router.get("/workflow-scoreboard")
async def workflow_scoreboard() -> dict[str, Any]:
    return _slice(
        "autonomous_workflow_dashboard_v37_report.json",
        "workflow_scoreboard_v37_report.json",
        "dashboard_v37_report_v1.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dummy_mission_state_report_v23.json",
        "runtime_loop_budget_v37_report.json",
        "workflow_loop_iteration_budget_v1_report.json",
        "repair_attempt_budget_v1_report.json",
        "regression_runtime_budget_v1_report.json",
        "probe_workflow_budget_v1_report.json",
        "dashboard_cache_policy_v19_report.json",
        "report_chain_runtime_profiler_v20_report.json",
    )
