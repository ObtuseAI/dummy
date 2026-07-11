from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v39.reports import V39ReportFactory

router = APIRouter(prefix="/api/v39", tags=["v39"])


def _reports() -> dict[str, dict[str, Any]]:
    return V39ReportFactory().build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    payload["api_can_trigger_probes"] = False
    payload["api_can_trigger_trading"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/run-controller")
async def run_controller() -> dict[str, Any]:
    return _slice(
        "v39_operator_approved_run_controller_v1_report.json",
        "v39_runtime_gate_input_report.json",
        "v39_operator_approval_scope_report.json",
        "v39_run_mode_decision_report.json",
        "v39_readonly_probe_execution_decision_report.json",
        "v39_completion_run_result_report.json",
        "v39_completion_run_blocker_report.json",
        "v39_run_safety_proof_report.json",
    )


@router.get("/exact-gate")
async def exact_gate() -> dict[str, Any]:
    return _slice(
        "exact_gate_runtime_execution_v7_report.json",
        "v39_gate_snapshot_report.json",
        "v39_ack_validation_decision_report.json",
        "v39_gate_visibility_check_report.json",
        "v39_gate_run_authorization_report.json",
        "v39_gate_failure_instruction_report.json",
        "v39_gate_safety_proof_report.json",
    )


@router.get("/v38-rerun")
async def v38_rerun() -> dict[str, Any]:
    return _slice(
        "v38_exact_gated_rerun_adapter_v1_report.json",
        "v38_rerun_command_plan_report.json",
        "v38_rerun_result_report.json",
        "v38_rerun_artifact_readback_report.json",
        "v38_rerun_consistency_check_report.json",
        "v38_rerun_blocker_report.json",
    )


@router.get("/real-public-source-run")
async def real_public_source_run() -> dict[str, Any]:
    return _slice(
        "real_public_source_run_v1_report.json",
        "real_public_source_family_run_report.json",
        "real_public_source_request_budget_report.json",
        "real_public_source_response_summary_report.json",
        "real_public_source_failure_summary_report.json",
        "real_public_source_safety_proof_report.json",
    )


@router.get("/live-public-evidence")
async def live_public_evidence() -> dict[str, Any]:
    return _slice(
        "live_public_evidence_completion_v2_report.json",
        "live_public_evidence_packet_report.json",
        "live_public_evidence_mode_decision_report.json",
        "live_public_evidence_freshness_check_report.json",
        "live_public_evidence_family_summary_report.json",
        "live_public_evidence_blocker_report.json",
        "live_public_evidence_safety_proof_report.json",
    )


@router.get("/settlement-compatible-evidence")
async def settlement_compatible_evidence() -> dict[str, Any]:
    return _slice(
        "settlement_compatible_evidence_closure_v2_report.json",
        "settlement_compatible_evidence_candidate_report.json",
        "settlement_rule_match_decision_report.json",
        "settlement_compatibility_confidence_report.json",
        "settlement_compatibility_blocker_report.json",
        "settlement_compatibility_safety_proof_report.json",
    )


@router.get("/real-due-observation")
async def real_due_observation() -> dict[str, Any]:
    return _slice(
        "real_due_observation_closure_v2_report.json",
        "real_due_observation_case_v2_report.json",
        "real_due_observation_evidence_match_v2_report.json",
        "real_due_observation_decision_v2_report.json",
        "real_due_observation_ledger_write_v2_report.json",
        "real_due_observation_blocker_v2_report.json",
        "real_due_observation_safety_proof_v2_report.json",
    )


@router.get("/first-real-live-score")
async def first_real_live_score() -> dict[str, Any]:
    return _slice(
        "first_real_live_score_closure_v2_report.json",
        "first_real_live_score_candidate_v2_report.json",
        "first_real_live_score_decision_v2_report.json",
        "first_real_live_score_metric_v2_report.json",
        "first_real_live_score_ledger_write_v2_report.json",
        "first_real_live_score_blocker_v2_report.json",
        "first_real_live_score_safety_proof_v2_report.json",
    )


@router.get("/readonly-live-intelligence")
async def readonly_live_intelligence() -> dict[str, Any]:
    return _slice(
        "readonly_live_intelligence_completion_v2_report.json",
        "readonly_live_intelligence_evidence_summary_report.json",
        "readonly_live_intelligence_coverage_summary_report.json",
        "readonly_live_intelligence_decision_report.json",
        "readonly_live_intelligence_blocker_report.json",
        "readonly_live_intelligence_safety_proof_report.json",
    )


@router.get("/first-live-score-milestone")
async def first_live_score_milestone() -> dict[str, Any]:
    return _slice(
        "first_live_score_milestone_completion_v2_report.json",
        "first_live_score_milestone_evidence_report.json",
        "first_live_score_milestone_decision_report.json",
        "first_live_score_milestone_blocker_report.json",
        "first_live_score_milestone_safety_proof_report.json",
    )


@router.get("/live-calibration")
async def live_calibration() -> dict[str, Any]:
    return _slice(
        "live_calibration_low_sample_v2_report.json",
        "live_calibration_real_sample_report.json",
        "live_calibration_bucket_v2_report.json",
        "live_calibration_decision_v2_report.json",
        "live_calibration_warning_v2_report.json",
        "live_calibration_blocker_v2_report.json",
        "live_calibration_safety_proof_v2_report.json",
    )


@router.get("/source-truth-real-outcome")
async def source_truth_real_outcome() -> dict[str, Any]:
    return _slice(
        "source_truth_real_outcome_update_v20_report.json",
        "source_truth_real_probe_signal_report.json",
        "source_truth_real_evidence_signal_report.json",
        "source_truth_real_settlement_signal_report.json",
        "source_truth_real_score_signal_report.json",
        "source_truth_real_outcome_next_action_report.json",
        "source_truth_real_outcome_safety_proof_report.json",
    )


@router.get("/completion-repair-selector")
async def completion_repair_selector() -> dict[str, Any]:
    return _slice(
        "completion_oriented_repair_selector_v1_report.json",
        "completion_repair_candidate_report.json",
        "completion_repair_decision_report.json",
        "completion_repair_queue_update_report.json",
        "completion_repair_blocker_report.json",
        "completion_repair_safety_proof_report.json",
    )


@router.get("/real-run-audit-ledger")
async def real_run_audit_ledger() -> dict[str, Any]:
    return _slice(
        "v39_real_run_audit_ledger_v1_report.json",
        "v39_real_run_audit_record_report.json",
        "v39_gate_audit_record_report.json",
        "v39_source_audit_record_report.json",
        "v39_evidence_audit_record_report.json",
        "v39_score_audit_record_report.json",
        "v39_safety_audit_record_report.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dashboard_v39_report_v1.json",
        "v39_api_surface_report_v1.json",
        "v39_dashboard_payload_safety_report_v1.json",
        "dummy_mission_state_report_v25.json",
        "v39_runtime_budget_report.json",
        "v39_readonly_probe_budget_report.json",
        "v39_evidence_closure_budget_report.json",
        "v39_dashboard_budget_report.json",
        "v39_report_chain_budget_report.json",
        "v39_runtime_blocker_report.json",
        "no_secret_leak_report_v39.json",
        "no_direct_order_bypass_report_v39.json",
        "no_live_submit_still_disabled_report_v39.json",
        "no_caps_config_modification_report_v39.json",
        "no_browser_automation_report_v39.json",
        "no_mined_repo_execution_report_v39.json",
        "no_fake_transport_score_claimed_live_report_v39.json",
        "no_missing_ack_probe_run_report_v39.json",
        "no_fuzzy_ack_probe_run_report_v39.json",
        "no_run_controller_to_execution_bridge_report_v39.json",
        "no_v38_rerun_to_execution_bridge_report_v39.json",
        "no_source_run_to_execution_bridge_report_v39.json",
        "no_evidence_completion_to_execution_bridge_report_v39.json",
        "no_live_score_to_execution_bridge_report_v39.json",
        "no_calibration_to_execution_bridge_report_v39.json",
        "no_source_truth_to_execution_bridge_report_v39.json",
        "no_repair_selector_to_execution_bridge_report_v39.json",
        "no_audit_ledger_to_execution_bridge_report_v39.json",
        "blunder_separation_recheck_v39.json",
        "dummy_canonical_identity_report_v39.json",
        "v38_still_passes_or_partial_expected_v39_report.json",
    )

