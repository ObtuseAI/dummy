from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v43.reports import V43ReportFactory

router = APIRouter(prefix="/api/v43", tags=["v43"])


def _reports() -> dict[str, dict[str, Any]]:
    return V43ReportFactory().build()


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


@router.get("/developing-sample-controller")
async def developing_sample_controller() -> dict[str, Any]:
    return _slice(
        "v43_developing_sample_pursuit_controller_v1_report.json",
        "v43_developing_sample_input_state_report.json",
        "v43_developing_sample_gate_decision_report.json",
        "v43_developing_sample_plan_report.json",
        "v43_optional_sample_extension_plan_report.json",
        "v43_developing_sample_threshold_decision_report.json",
        "v43_developing_sample_aggregate_result_report.json",
        "v43_developing_sample_blocker_report.json",
        "v43_developing_sample_safety_proof_report.json",
    )


@router.get("/exact-gate")
async def exact_gate() -> dict[str, Any]:
    return _slice(
        "exact_gate_runtime_v11_report.json",
        "v43_gate_snapshot_report.json",
        "v43_ack_validation_decision_report.json",
        "v43_gate_visibility_check_report.json",
        "v43_gate_run_authorization_report.json",
        "v43_per_cycle_gate_recheck_report.json",
        "v43_gate_failure_instruction_report.json",
        "v43_gate_safety_proof_report.json",
    )


@router.get("/v42-baseline")
async def v42_baseline() -> dict[str, Any]:
    return _slice(
        "v42_baseline_readback_v1_report.json",
        "v42_baseline_final_report_readback_report.json",
        "v42_baseline_mission_state_readback_report.json",
        "v42_calibration_audit_ledger_readback_report.json",
        "v42_baseline_count_integrity_check_report.json",
        "v42_baseline_safety_carry_forward_report.json",
        "v42_baseline_blocker_report.json",
    )


@router.get("/sample-extension")
async def sample_extension() -> dict[str, Any]:
    return _slice(
        "optional_developing_sample_extension_v1_report.json",
        "v43_sample_extension_cycle_plan_report.json",
        "v43_sample_extension_budget_report.json",
        "v43_sample_extension_run_result_report.json",
        "v43_sample_extension_family_result_report.json",
        "v43_sample_extension_failure_summary_report.json",
        "v43_sample_extension_safety_proof_report.json",
    )


@router.get("/sample-quality")
async def sample_quality() -> dict[str, Any]:
    return _slice(
        "v43_sample_quality_gate_v2_report.json",
        "v43_sample_freshness_quality_report.json",
        "v43_sample_dedupe_quality_report.json",
        "v43_sample_settlement_quality_report.json",
        "v43_sample_observation_quality_report.json",
        "v43_sample_score_eligibility_quality_report.json",
        "v43_sample_diversity_quality_report.json",
        "v43_sample_quality_blocker_report.json",
        "v43_sample_quality_safety_proof_report.json",
    )


@router.get("/tier-governor")
async def tier_governor() -> dict[str, Any]:
    return _slice(
        "developing_sample_tier_governor_v1_report.json",
        "v43_tier_input_summary_report.json",
        "v43_tier_threshold_policy_report.json",
        "v43_tier_quality_gate_result_report.json",
        "v43_tier_transition_decision_report.json",
        "v43_tier_regression_decision_report.json",
        "v43_tier_warning_report.json",
        "v43_tier_safety_proof_report.json",
    )


@router.get("/calibration-stability")
async def calibration_stability() -> dict[str, Any]:
    return _slice(
        "calibration_stability_window_v1_report.json",
        "v43_calibration_rolling_window_report.json",
        "v43_calibration_window_metric_report.json",
        "v43_calibration_window_variance_report.json",
        "v43_calibration_window_drift_report.json",
        "v43_calibration_window_reliability_band_report.json",
        "v43_calibration_window_blocker_report.json",
        "v43_calibration_window_safety_proof_report.json",
    )


@router.get("/source-truth-v24")
async def source_truth_v24() -> dict[str, Any]:
    return _slice(
        "source_truth_v24_stability_window_report.json",
        "v43_source_rolling_window_report.json",
        "v43_source_probe_reliability_report.json",
        "v43_source_evidence_reliability_report.json",
        "v43_source_settlement_reliability_report.json",
        "v43_source_score_reliability_report.json",
        "v43_source_blocker_trend_report.json",
        "v43_source_reliability_class_report.json",
        "v43_source_truth_safety_proof_report.json",
    )


@router.get("/market-class-reliability")
async def market_class_reliability() -> dict[str, Any]:
    return _slice(
        "market_class_reliability_v4_delta_report.json",
        "v43_market_class_delta_row_report.json",
        "v43_market_class_sample_delta_report.json",
        "v43_market_class_calibration_delta_report.json",
        "v43_market_class_source_support_delta_report.json",
        "v43_market_class_no_trade_delta_report.json",
        "v43_market_class_blocker_delta_report.json",
        "v43_market_class_next_action_report.json",
        "v43_market_class_safety_proof_report.json",
    )


@router.get("/no-trade-trend")
async def no_trade_trend() -> dict[str, Any]:
    return _slice(
        "no_trade_discipline_v4_trend_engine_report.json",
        "v43_no_trade_trend_case_report.json",
        "v43_no_trade_reason_trend_report.json",
        "v43_no_trade_avoided_bad_score_trend_report.json",
        "v43_no_trade_false_abstention_trend_report.json",
        "v43_no_trade_market_class_trend_report.json",
        "v43_no_trade_discipline_trend_score_report.json",
        "v43_no_trade_discipline_safety_proof_report.json",
    )


@router.get("/forecast-quality-trend")
async def forecast_quality_trend() -> dict[str, Any]:
    return _slice(
        "forecast_quality_ledger_v2_trend_engine_report.json",
        "v43_forecast_quality_trend_case_report.json",
        "v43_forecast_resolution_trend_report.json",
        "v43_forecast_score_trend_report.json",
        "v43_forecast_calibration_contribution_trend_report.json",
        "v43_forecast_blocker_trend_report.json",
        "v43_forecast_quality_safety_proof_report.json",
    )


@router.get("/observer-scaleout")
async def observer_scaleout() -> dict[str, Any]:
    return _slice(
        "readonly_observer_scaleout_plan_v1_report.json",
        "v43_observer_lane_plan_report.json",
        "v43_observer_source_rotation_plan_report.json",
        "v43_observer_budget_plan_report.json",
        "v43_observer_quality_gate_plan_report.json",
        "v43_observer_human_action_packet_report.json",
        "v43_observer_scaleout_safety_proof_report.json",
    )


@router.get("/readiness-governor")
async def readiness_governor() -> dict[str, Any]:
    return _slice(
        "readiness_governor_v3_report.json",
        "v43_readiness_input_state_report.json",
        "v43_readiness_achieved_stage_report.json",
        "v43_readiness_blocked_stage_report.json",
        "v43_readiness_promotion_gate_report.json",
        "v43_readiness_trading_lock_report.json",
        "v43_readiness_observer_scaleout_gate_report.json",
        "v43_readiness_governor_decision_report.json",
        "v43_readiness_governor_safety_proof_report.json",
    )


@router.get("/execution-lock")
async def execution_lock() -> dict[str, Any]:
    return _slice(
        "execution_lock_deep_recheck_v2_report.json",
        "v43_no_order_surface_check_report.json",
        "v43_no_shadow_order_check_report.json",
        "v43_no_dry_submit_check_report.json",
        "v43_no_broker_payload_check_report.json",
        "v43_no_execution_rehearsal_check_report.json",
        "v43_no_capital_allocation_check_report.json",
        "v43_no_readiness_to_execution_bridge_check_report.json",
        "v43_execution_lock_safety_proof_report.json",
    )


@router.get("/next-action")
async def next_action() -> dict[str, Any]:
    return _slice(
        "completion_oriented_next_action_v43_report.json",
        "v43_next_action_candidate_report.json",
        "v43_next_action_decision_report.json",
        "v43_next_action_reason_report.json",
        "v43_next_action_blocker_report.json",
        "v43_next_action_safety_proof_report.json",
    )


@router.get("/audit-ledger")
async def audit_ledger() -> dict[str, Any]:
    return _slice(
        "v43_developing_sample_audit_ledger_report.json",
        "v43_developing_sample_audit_record_report.json",
        "v43_gate_audit_record_report.json",
        "v43_optional_probe_audit_record_report.json",
        "v43_sample_quality_audit_record_report.json",
        "v43_tier_transition_audit_record_report.json",
        "v43_calibration_stability_audit_record_report.json",
        "v43_source_truth_audit_record_report.json",
        "v43_market_class_audit_record_report.json",
        "v43_no_trade_audit_record_report.json",
        "v43_forecast_quality_audit_record_report.json",
        "v43_readiness_governor_audit_record_report.json",
        "v43_observer_scaleout_audit_record_report.json",
        "v43_safety_audit_record_report.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dashboard_v43_report_v1.json",
        "v43_api_surface_report_v1.json",
        "v43_dashboard_payload_safety_report_v1.json",
        "dummy_mission_state_report_v29.json",
        "v43_runtime_budget_report.json",
        "v43_readonly_probe_budget_report.json",
        "v43_optional_sample_cycle_budget_report.json",
        "v43_sample_quality_budget_report.json",
        "v43_calibration_stability_budget_report.json",
        "v43_dashboard_budget_report.json",
        "v43_report_chain_budget_report.json",
        "v43_runtime_blocker_report.json",
        "no_secret_leak_report_v43.json",
        "no_direct_order_bypass_report_v43.json",
        "no_order_ticket_generation_report_v43.json",
        "no_shadow_order_generation_report_v43.json",
        "no_dry_submit_packet_generation_report_v43.json",
        "no_broker_payload_generation_report_v43.json",
        "no_execution_rehearsal_report_v43.json",
        "no_broker_schema_generation_report_v43.json",
        "no_order_intent_object_generation_report_v43.json",
        "no_position_sizing_artifact_report_v43.json",
        "no_capital_allocation_artifact_report_v43.json",
        "no_live_submit_still_disabled_report_v43.json",
        "no_caps_config_modification_report_v43.json",
        "no_browser_automation_report_v43.json",
        "no_mined_repo_execution_report_v43.json",
        "no_fake_transport_score_claimed_live_report_v43.json",
        "no_missing_ack_probe_run_report_v43.json",
        "no_fuzzy_ack_probe_run_report_v43.json",
        "no_sports_source_activation_report_v43.json",
        "no_duplicate_evidence_scored_as_new_report_v43.json",
        "no_developing_sample_controller_to_execution_bridge_report_v43.json",
        "no_sample_extension_to_execution_bridge_report_v43.json",
        "no_tier_governor_to_execution_bridge_report_v43.json",
        "no_calibration_stability_to_execution_bridge_report_v43.json",
        "no_source_truth_to_execution_bridge_report_v43.json",
        "no_market_class_reliability_to_execution_bridge_report_v43.json",
        "no_no_trade_discipline_to_execution_bridge_report_v43.json",
        "no_forecast_quality_to_execution_bridge_report_v43.json",
        "no_observer_scaleout_to_execution_bridge_report_v43.json",
        "no_readiness_governor_to_execution_bridge_report_v43.json",
        "no_next_action_to_execution_bridge_report_v43.json",
        "no_audit_ledger_to_execution_bridge_report_v43.json",
        "blunder_separation_recheck_v43.json",
        "dummy_canonical_identity_report_v43.json",
        "v42_still_passes_or_partial_expected_v43_report.json",
    )
