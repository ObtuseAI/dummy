from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v42.reports import V42ReportFactory

router = APIRouter(prefix="/api/v42", tags=["v42"])


def _reports() -> dict[str, dict[str, Any]]:
    return V42ReportFactory().build()


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


@router.get("/calibration-controller")
async def calibration_controller() -> dict[str, Any]:
    return _slice(
        "v42_real_calibration_deepening_controller_v1_report.json",
        "v42_calibration_input_state_report.json",
        "v42_calibration_gate_decision_report.json",
        "v42_calibration_plan_report.json",
        "v42_optional_sample_extension_plan_report.json",
        "v42_calibration_aggregate_result_report.json",
        "v42_calibration_blocker_report.json",
        "v42_calibration_safety_proof_report.json",
    )


@router.get("/exact-gate")
async def exact_gate() -> dict[str, Any]:
    return _slice(
        "exact_gate_runtime_v10_report.json",
        "v42_gate_snapshot_report.json",
        "v42_ack_validation_decision_report.json",
        "v42_gate_visibility_check_report.json",
        "v42_gate_run_authorization_report.json",
        "v42_per_cycle_gate_recheck_report.json",
        "v42_gate_failure_instruction_report.json",
        "v42_gate_safety_proof_report.json",
    )


@router.get("/v41-baseline")
async def v41_baseline() -> dict[str, Any]:
    return _slice(
        "v41_baseline_readback_v1_report.json",
        "v41_baseline_final_report_readback_report.json",
        "v41_baseline_mission_state_readback_report.json",
        "v41_baseline_audit_ledger_readback_report.json",
        "v41_baseline_count_integrity_check_report.json",
        "v41_baseline_safety_carry_forward_report.json",
        "v41_baseline_blocker_report.json",
    )


@router.get("/sample-extension")
async def sample_extension() -> dict[str, Any]:
    return _slice(
        "optional_bounded_sample_extension_v1_report.json",
        "v42_sample_extension_cycle_plan_report.json",
        "v42_sample_extension_budget_report.json",
        "v42_sample_extension_run_result_report.json",
        "v42_sample_extension_family_result_report.json",
        "v42_sample_extension_failure_summary_report.json",
        "v42_sample_extension_safety_proof_report.json",
    )


@router.get("/sample-quality")
async def sample_quality() -> dict[str, Any]:
    return _slice(
        "calibration_sample_quality_gate_v1_report.json",
        "v42_sample_freshness_quality_report.json",
        "v42_sample_dedupe_quality_report.json",
        "v42_sample_settlement_quality_report.json",
        "v42_sample_observation_quality_report.json",
        "v42_sample_score_eligibility_quality_report.json",
        "v42_sample_quality_blocker_report.json",
        "v42_sample_quality_safety_proof_report.json",
    )


@router.get("/calibration-metrics")
async def calibration_metrics() -> dict[str, Any]:
    return _slice(
        "reliability_calibration_metrics_v1_report.json",
        "v42_calibration_brier_score_proxy_report.json",
        "v42_calibration_hit_rate_report.json",
        "v42_calibration_sharpness_report.json",
        "v42_calibration_reliability_band_report.json",
        "v42_calibration_sample_variance_report.json",
        "v42_calibration_market_class_metric_report.json",
        "v42_calibration_metric_blocker_report.json",
        "v42_calibration_metric_safety_proof_report.json",
    )


@router.get("/calibration-tier-governor")
async def calibration_tier_governor() -> dict[str, Any]:
    return _slice(
        "calibration_tier_governor_v1_report.json",
        "v42_tier_input_summary_report.json",
        "v42_tier_threshold_policy_report.json",
        "v42_tier_transition_decision_report.json",
        "v42_tier_regression_decision_report.json",
        "v42_tier_warning_report.json",
        "v42_tier_safety_proof_report.json",
    )


@router.get("/source-truth-v23")
async def source_truth_v23() -> dict[str, Any]:
    return _slice(
        "source_truth_v23_stability_engine_report.json",
        "v42_source_probe_stability_report.json",
        "v42_source_evidence_stability_report.json",
        "v42_source_settlement_stability_report.json",
        "v42_source_score_stability_report.json",
        "v42_source_duplicate_stale_stability_report.json",
        "v42_source_blocker_stability_report.json",
        "v42_source_reliability_class_report.json",
        "v42_source_truth_v23_safety_proof_report.json",
    )


@router.get("/market-class-reliability")
async def market_class_reliability() -> dict[str, Any]:
    return _slice(
        "market_class_reliability_v3_report.json",
        "v42_market_class_reliability_row_report.json",
        "v42_market_class_sample_coverage_report.json",
        "v42_market_class_calibration_quality_report.json",
        "v42_market_class_source_support_report.json",
        "v42_market_class_no_trade_quality_report.json",
        "v42_market_class_blocker_profile_report.json",
        "v42_market_class_next_action_report.json",
    )


@router.get("/no-trade-discipline")
async def no_trade_discipline() -> dict[str, Any]:
    return _slice(
        "no_trade_discipline_v3_report.json",
        "v42_no_trade_case_report.json",
        "v42_no_trade_reason_quality_report.json",
        "v42_no_trade_avoided_bad_score_report.json",
        "v42_no_trade_false_abstention_check_report.json",
        "v42_no_trade_market_class_summary_report.json",
        "v42_no_trade_discipline_score_report.json",
        "v42_no_trade_discipline_safety_proof_report.json",
    )


@router.get("/forecast-quality-ledger")
async def forecast_quality_ledger() -> dict[str, Any]:
    return _slice(
        "forecast_quality_ledger_v1_report.json",
        "v42_forecast_quality_case_report.json",
        "v42_forecast_resolution_quality_report.json",
        "v42_forecast_score_quality_report.json",
        "v42_forecast_calibration_contribution_report.json",
        "v42_forecast_quality_blocker_report.json",
        "v42_forecast_quality_safety_proof_report.json",
    )


@router.get("/readiness-governor")
async def readiness_governor() -> dict[str, Any]:
    return _slice(
        "readiness_governor_v2_report.json",
        "v42_readiness_input_state_report.json",
        "v42_readiness_achieved_stage_report.json",
        "v42_readiness_blocked_stage_report.json",
        "v42_readiness_promotion_gate_report.json",
        "v42_readiness_trading_lock_report.json",
        "v42_readiness_governor_decision_report.json",
        "v42_readiness_governor_safety_proof_report.json",
    )


@router.get("/execution-lock")
async def execution_lock() -> dict[str, Any]:
    return _slice(
        "execution_lock_deep_recheck_v1_report.json",
        "v42_no_order_surface_check_report.json",
        "v42_no_shadow_order_check_report.json",
        "v42_no_dry_submit_check_report.json",
        "v42_no_broker_payload_check_report.json",
        "v42_no_execution_rehearsal_check_report.json",
        "v42_no_readiness_to_execution_bridge_check_report.json",
        "v42_execution_lock_safety_proof_report.json",
    )


@router.get("/next-action")
async def next_action() -> dict[str, Any]:
    return _slice(
        "completion_oriented_next_action_v42_report.json",
        "v42_next_action_candidate_report.json",
        "v42_next_action_decision_report.json",
        "v42_next_action_reason_report.json",
        "v42_next_action_blocker_report.json",
        "v42_next_action_safety_proof_report.json",
    )


@router.get("/audit-ledger")
async def audit_ledger() -> dict[str, Any]:
    return _slice(
        "v42_calibration_audit_ledger_report.json",
        "v42_calibration_audit_record_report.json",
        "v42_gate_audit_record_report.json",
        "v42_optional_probe_audit_record_report.json",
        "v42_sample_quality_audit_record_report.json",
        "v42_calibration_metric_audit_record_report.json",
        "v42_source_truth_audit_record_report.json",
        "v42_market_class_audit_record_report.json",
        "v42_no_trade_audit_record_report.json",
        "v42_readiness_governor_audit_record_report.json",
        "v42_safety_audit_record_report.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dashboard_v42_report_v1.json",
        "v42_api_surface_report_v1.json",
        "v42_dashboard_payload_safety_report_v1.json",
        "dummy_mission_state_report_v28.json",
        "v42_runtime_budget_report.json",
        "v42_readonly_probe_budget_report.json",
        "v42_optional_sample_cycle_budget_report.json",
        "v42_sample_quality_budget_report.json",
        "v42_calibration_budget_report.json",
        "v42_dashboard_budget_report.json",
        "v42_report_chain_budget_report.json",
        "v42_runtime_blocker_report.json",
        "no_secret_leak_report_v42.json",
        "no_direct_order_bypass_report_v42.json",
        "no_order_ticket_generation_report_v42.json",
        "no_shadow_order_generation_report_v42.json",
        "no_dry_submit_packet_generation_report_v42.json",
        "no_broker_payload_generation_report_v42.json",
        "no_execution_rehearsal_report_v42.json",
        "no_live_submit_still_disabled_report_v42.json",
        "no_caps_config_modification_report_v42.json",
        "no_browser_automation_report_v42.json",
        "no_mined_repo_execution_report_v42.json",
        "no_fake_transport_score_claimed_live_report_v42.json",
        "no_missing_ack_probe_run_report_v42.json",
        "no_fuzzy_ack_probe_run_report_v42.json",
        "no_sports_source_activation_report_v42.json",
        "no_duplicate_evidence_scored_as_new_report_v42.json",
        "no_calibration_controller_to_execution_bridge_report_v42.json",
        "no_sample_extension_to_execution_bridge_report_v42.json",
        "no_calibration_metrics_to_execution_bridge_report_v42.json",
        "no_source_truth_to_execution_bridge_report_v42.json",
        "no_market_class_reliability_to_execution_bridge_report_v42.json",
        "no_no_trade_discipline_to_execution_bridge_report_v42.json",
        "no_forecast_quality_to_execution_bridge_report_v42.json",
        "no_readiness_governor_to_execution_bridge_report_v42.json",
        "no_next_action_to_execution_bridge_report_v42.json",
        "no_audit_ledger_to_execution_bridge_report_v42.json",
        "blunder_separation_recheck_v42.json",
        "dummy_canonical_identity_report_v42.json",
        "v41_still_passes_or_partial_expected_v42_report.json",
    )
