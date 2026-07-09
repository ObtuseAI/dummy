from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v35.reports import V35ReportFactory

router = APIRouter(prefix="/api/v35", tags=["v35"])


def _reports() -> dict[str, dict[str, Any]]:
    return V35ReportFactory().build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/v34-qc")
async def v34_qc() -> dict[str, Any]:
    return _slice(
        "v34_change_review_and_qc_confirmation_v2_report.json",
        "v34_fixed_issue_inventory_report.json",
        "v34_dispatch_overlap_fix_check_report.json",
        "v34_dead_constant_removal_check_report.json",
        "v34_route_registration_review_report.json",
        "v34_report_transform_review_report.json",
        "v34_qc_issue_resolution_status_report.json",
        "v34_qc_residual_risk_report.json",
    )


@router.get("/frontend-build")
async def frontend_build() -> dict[str, Any]:
    return _slice(
        "frontend_build_confirmation_v1_report.json",
        "frontend_build_command_record_report.json",
        "frontend_build_result_report.json",
        "frontend_route_coverage_check_report.json",
        "frontend_dashboard_link_check_report.json",
        "frontend_build_blocker_report.json",
    )


@router.get("/default-path")
async def default_path() -> dict[str, Any]:
    return _slice(
        "v34_default_path_reverification_v1_report.json",
        "default_gate_state_check_v1_report.json",
        "default_ack_failure_check_v1_report.json",
        "default_probe_no_run_check_v1_report.json",
        "default_no_evidence_no_score_check_v1_report.json",
        "default_partial_verdict_check_v1_report.json",
        "default_path_blocker_v1_report.json",
    )


@router.get("/enabled-path")
async def enabled_path() -> dict[str, Any]:
    return _slice(
        "v34_enabled_path_reverification_v1_report.json",
        "enabled_gate_state_check_v1_report.json",
        "enabled_probe_run_count_check_v1_report.json",
        "enabled_evidence_count_check_v1_report.json",
        "enabled_observation_count_check_v1_report.json",
        "enabled_live_score_count_check_v1_report.json",
        "enabled_unresolved_count_check_v1_report.json",
        "enabled_path_blocker_v1_report.json",
    )


@router.get("/evidence-mode")
async def evidence_mode() -> dict[str, Any]:
    return _slice(
        "enabled_path_evidence_mode_audit_v1_report.json",
        "enabled_evidence_mode_record_report.json",
        "enabled_evidence_live_eligibility_decision_report.json",
        "enabled_evidence_fake_transport_guard_report.json",
        "enabled_evidence_cache_guard_report.json",
        "enabled_evidence_mode_blocker_report.json",
    )


@router.get("/live-score-sample-readiness")
async def live_score_sample_readiness() -> dict[str, Any]:
    return _slice(
        "live_score_sample_expansion_readiness_v1_report.json",
        "live_score_sample_candidate_report.json",
        "live_score_sample_eligibility_report.json",
        "live_score_sample_expansion_plan_report.json",
        "live_score_low_sample_status_report.json",
        "live_score_sample_expansion_blocker_report.json",
    )


@router.get("/calibration-low-sample")
async def calibration_low_sample() -> dict[str, Any]:
    return _slice(
        "live_calibration_low_sample_qc_v1_report.json",
        "calibration_default_path_check_report.json",
        "calibration_enabled_path_check_report.json",
        "calibration_sample_mode_separation_report.json",
        "calibration_readiness_decision_report.json",
        "calibration_low_sample_blocker_report.json",
    )


@router.get("/v34-route-smoke")
async def v34_route_smoke() -> dict[str, Any]:
    return _slice(
        "v34_route_api_smoke_v1_report.json",
        "v34_route_smoke_result_report.json",
        "v34_endpoint_payload_shape_check_report.json",
        "v34_endpoint_redaction_check_report.json",
        "v34_endpoint_consistency_check_report.json",
        "v34_route_smoke_blocker_report.json",
    )


@router.get("/report-transform-consistency")
async def report_transform_consistency() -> dict[str, Any]:
    return _slice(
        "report_transform_consistency_v1_report.json",
        "report_transform_input_check_report.json",
        "report_transform_output_check_report.json",
        "final_report_consistency_check_report.json",
        "tests_summary_consistency_check_report.json",
        "report_transform_blocker_report.json",
    )


@router.get("/protected-hash")
async def protected_hash() -> dict[str, Any]:
    return _slice(
        "protected_hash_reverification_v1_report.json",
        "live_submit_hash_check_v1_report.json",
        "caps_hash_check_v1_report.json",
        "protected_config_diff_check_v1_report.json",
        "live_submit_enabled_check_v1_report.json",
        "protected_hash_blocker_v1_report.json",
    )


@router.get("/no-execution-bridge-deep-recheck")
async def no_execution_bridge_deep_recheck() -> dict[str, Any]:
    return _slice(
        "no_execution_bridge_deep_recheck_v1_report.json",
        "adapter_no_execution_bridge_check_report.json",
        "probe_no_execution_bridge_check_report.json",
        "evidence_no_execution_bridge_check_report.json",
        "scoring_no_execution_bridge_check_report.json",
        "calibration_no_execution_bridge_check_report.json",
        "source_truth_no_execution_bridge_check_report.json",
        "dashboard_no_execution_bridge_check_report.json",
    )


@router.get("/sports-fixture-only")
async def sports_fixture_only() -> dict[str, Any]:
    return _slice(
        "sports_fixture_only_reverification_v6_report.json",
        "sports_mode_check_v6_report.json",
        "sports_betting_source_activation_check_v6_report.json",
        "sports_fixture_scoring_guard_v6_report.json",
        "sports_approval_packet_status_v6_report.json",
        "sports_fixture_only_blocker_v6_report.json",
    )


@router.get("/source-truth-v16")
async def source_truth_v16() -> dict[str, Any]:
    return _slice(
        "source_truth_v16_qc_and_sample_readiness_report.json",
        "source_truth_qc_signal_report.json",
        "source_truth_evidence_mode_signal_report.json",
        "source_truth_sample_readiness_signal_report.json",
        "source_truth_frontend_build_signal_report.json",
        "source_truth_next_action_v16_report.json",
    )


@router.get("/partial-reduction")
async def partial_reduction() -> dict[str, Any]:
    return _slice(
        "v35_partial_reduction_ledger_report.json",
        "v35_partial_cause_before_after_report.json",
        "v35_partial_reduction_attempt_report.json",
        "v35_partial_reduction_result_report.json",
        "v35_remaining_partial_cause_report.json",
        "v35_pass_delta_report.json",
    )


@router.get("/sprint-v12")
async def sprint_v12() -> dict[str, Any]:
    return _slice(
        "v35_sprint_queue_v12_report.json",
        "v35_sprint_task_report.json",
        "v35_frontend_or_route_target_report.json",
        "v35_enabled_probe_target_report.json",
        "v35_sample_expansion_target_report.json",
        "v35_operator_action_report.json",
        "v35_risk_guard_report.json",
    )


@router.get("/compounding-v19")
async def compounding_v19() -> dict[str, Any]:
    return _slice(
        "v35_compounding_control_plane_v19_report.json",
        "v35_qc_queue_report.json",
        "v35_frontend_build_queue_report.json",
        "v35_enabled_probe_queue_report.json",
        "v35_sample_expansion_queue_report.json",
        "v35_next_bundle_recommendation_report.json",
    )


@router.get("/market-class-scoreboard")
async def market_class_scoreboard() -> dict[str, Any]:
    return _slice(
        "domain_market_class_scoreboard_v20_report.json",
        "v35_qc_scoreboard_report.json",
        "v35_enabled_path_scoreboard_report.json",
        "v35_evidence_mode_scoreboard_report.json",
        "v35_sample_readiness_scoreboard_report.json",
        "v35_frontend_build_scoreboard_report.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dummy_mission_state_report_v21.json",
        "dashboard_v35_report_v1.json",
        "v35_runtime_budget_report_v1.json",
        "v35_qc_runtime_budget_report.json",
        "v35_frontend_build_budget_report.json",
        "v35_route_smoke_budget_report.json",
        "dashboard_cache_policy_v17_report.json",
        "report_chain_runtime_profiler_v18_report.json",
    )
