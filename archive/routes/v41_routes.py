from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v41.reports import V41ReportFactory

router = APIRouter(prefix="/api/v41", tags=["v41"])


def _reports() -> dict[str, dict[str, Any]]:
    return V41ReportFactory().build()


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


@router.get("/multi-cycle-expansion-controller")
async def multi_cycle_expansion_controller() -> dict[str, Any]:
    return _slice(
        "v41_multi_cycle_real_sample_expansion_controller_v1_report.json",
        "v41_expansion_input_state_report.json",
        "v41_expansion_gate_decision_report.json",
        "v41_expansion_cycle_plan_report.json",
        "v41_expansion_cycle_result_report.json",
        "v41_expansion_aggregate_result_report.json",
        "v41_expansion_blocker_report.json",
        "v41_expansion_safety_proof_report.json",
    )


@router.get("/exact-gate")
async def exact_gate() -> dict[str, Any]:
    return _slice(
        "exact_gate_runtime_v9_report.json",
        "v41_gate_snapshot_report.json",
        "v41_ack_validation_decision_report.json",
        "v41_gate_visibility_check_report.json",
        "v41_gate_run_authorization_report.json",
        "v41_per_cycle_gate_recheck_report.json",
        "v41_gate_failure_instruction_report.json",
        "v41_gate_safety_proof_report.json",
    )


@router.get("/v40-baseline")
async def v40_baseline() -> dict[str, Any]:
    return _slice(
        "v40_baseline_readback_v1_report.json",
        "v40_baseline_final_report_readback_report.json",
        "v40_baseline_mission_state_readback_report.json",
        "v40_baseline_audit_ledger_readback_report.json",
        "v40_baseline_count_integrity_check_report.json",
        "v40_baseline_safety_carry_forward_report.json",
        "v40_baseline_blocker_report.json",
    )


@router.get("/probe-expansion")
async def probe_expansion() -> dict[str, Any]:
    return _slice(
        "bounded_real_public_probe_expansion_v2_report.json",
        "v41_probe_cycle_plan_report.json",
        "v41_probe_cycle_budget_report.json",
        "v41_probe_cycle_run_result_report.json",
        "v41_probe_family_result_report.json",
        "v41_probe_failure_summary_report.json",
        "v41_probe_expansion_safety_proof_report.json",
    )


@router.get("/freshness-dedupe")
async def freshness_dedupe() -> dict[str, Any]:
    return _slice(
        "freshness_and_dedupe_gate_v1_report.json",
        "evidence_freshness_window_policy_report.json",
        "evidence_dedupe_key_policy_report.json",
        "evidence_duplicate_decision_report.json",
        "evidence_stale_decision_report.json",
        "evidence_freshness_dedupe_ledger_report.json",
        "evidence_freshness_dedupe_blocker_report.json",
    )


@router.get("/real-evidence-ledger")
async def real_evidence_ledger() -> dict[str, Any]:
    return _slice(
        "expanded_real_evidence_ledger_v2_report.json",
        "v41_real_evidence_packet_report.json",
        "v41_evidence_eligibility_decision_report.json",
        "v41_evidence_family_summary_report.json",
        "v41_evidence_market_class_summary_report.json",
        "v41_evidence_cumulative_summary_report.json",
        "v41_evidence_safety_proof_report.json",
    )


@router.get("/settlement-expansion")
async def settlement_expansion() -> dict[str, Any]:
    return _slice(
        "settlement_compatibility_expansion_v2_report.json",
        "v41_settlement_candidate_report.json",
        "v41_settlement_join_decision_report.json",
        "v41_settlement_confidence_report.json",
        "v41_settlement_family_summary_report.json",
        "v41_settlement_market_class_summary_report.json",
        "v41_settlement_blocker_report.json",
        "v41_settlement_safety_proof_report.json",
    )


@router.get("/observation-expansion")
async def observation_expansion() -> dict[str, Any]:
    return _slice(
        "due_observation_closure_expansion_v2_report.json",
        "v41_due_observation_case_report.json",
        "v41_due_observation_evidence_match_report.json",
        "v41_due_observation_decision_report.json",
        "v41_due_observation_ledger_write_report.json",
        "v41_due_observation_family_summary_report.json",
        "v41_due_observation_blocker_report.json",
        "v41_due_observation_safety_proof_report.json",
    )


@router.get("/real-live-score-expansion")
async def real_live_score_expansion() -> dict[str, Any]:
    return _slice(
        "real_live_score_sample_expansion_v2_report.json",
        "v41_real_live_score_candidate_report.json",
        "v41_real_live_score_decision_report.json",
        "v41_real_live_score_metric_report.json",
        "v41_real_live_score_ledger_write_report.json",
        "v41_real_live_score_family_summary_report.json",
        "v41_real_live_score_cumulative_summary_report.json",
        "v41_real_live_score_blocker_report.json",
        "v41_real_live_score_safety_proof_report.json",
    )


@router.get("/calibration-deepening")
async def calibration_deepening() -> dict[str, Any]:
    return _slice(
        "calibration_deepening_v2_report.json",
        "v41_calibration_sample_ledger_report.json",
        "v41_calibration_bucket_report.json",
        "v41_calibration_confidence_tier_decision_report.json",
        "v41_calibration_reliability_warning_report.json",
        "v41_calibration_market_class_summary_report.json",
        "v41_calibration_blocker_report.json",
        "v41_calibration_safety_proof_report.json",
    )


@router.get("/source-truth-v22")
async def source_truth_v22() -> dict[str, Any]:
    return _slice(
        "source_truth_v22_real_sample_ranking_report.json",
        "v41_source_probe_health_signal_report.json",
        "v41_source_evidence_availability_signal_report.json",
        "v41_source_settlement_usefulness_signal_report.json",
        "v41_source_score_truth_signal_report.json",
        "v41_source_no_trade_signal_report.json",
        "v41_source_reliability_rank_report.json",
        "v41_source_truth_next_action_report.json",
        "v41_source_truth_safety_proof_report.json",
    )


@router.get("/no-trade-discipline")
async def no_trade_discipline() -> dict[str, Any]:
    return _slice(
        "no_trade_discipline_v2_report.json",
        "v41_no_trade_case_report.json",
        "v41_no_trade_reason_quality_report.json",
        "v41_no_trade_avoided_bad_score_report.json",
        "v41_no_trade_market_class_summary_report.json",
        "v41_no_trade_discipline_score_report.json",
        "v41_no_trade_discipline_blocker_report.json",
        "v41_no_trade_discipline_safety_proof_report.json",
    )


@router.get("/market-class-scoreboard")
async def market_class_scoreboard() -> dict[str, Any]:
    return _slice(
        "market_class_scoreboard_v2_report.json",
        "v41_market_class_scoreboard_row_report.json",
        "v41_market_class_evidence_coverage_report.json",
        "v41_market_class_settlement_coverage_report.json",
        "v41_market_class_score_coverage_report.json",
        "v41_market_class_calibration_coverage_report.json",
        "v41_market_class_no_trade_coverage_report.json",
        "v41_market_class_next_action_report.json",
    )


@router.get("/readiness-ladder")
async def readiness_ladder() -> dict[str, Any]:
    return _slice(
        "readiness_ladder_v1_report.json",
        "readiness_stage_readonly_intelligence_report.json",
        "readiness_stage_live_scoring_report.json",
        "readiness_stage_calibration_deepening_report.json",
        "readiness_stage_no_trade_discipline_report.json",
        "readiness_stage_operator_armed_rehearsal_blocker_report.json",
        "readiness_stage_live_trading_locked_report.json",
        "readiness_ladder_safety_proof_report.json",
    )


@router.get("/next-action")
async def next_action() -> dict[str, Any]:
    return _slice(
        "completion_oriented_next_action_v41_report.json",
        "v41_next_action_candidate_report.json",
        "v41_next_action_decision_report.json",
        "v41_next_action_reason_report.json",
        "v41_next_action_blocker_report.json",
        "v41_next_action_safety_proof_report.json",
    )


@router.get("/audit-ledger")
async def audit_ledger() -> dict[str, Any]:
    return _slice(
        "v41_real_sample_audit_ledger_report.json",
        "v41_real_sample_audit_record_report.json",
        "v41_gate_audit_record_report.json",
        "v41_probe_cycle_audit_record_report.json",
        "v41_source_audit_record_report.json",
        "v41_evidence_audit_record_report.json",
        "v41_settlement_audit_record_report.json",
        "v41_observation_audit_record_report.json",
        "v41_score_audit_record_report.json",
        "v41_calibration_audit_record_report.json",
        "v41_no_trade_audit_record_report.json",
        "v41_safety_audit_record_report.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dashboard_v41_report_v1.json",
        "v41_api_surface_report_v1.json",
        "v41_dashboard_payload_safety_report_v1.json",
        "dummy_mission_state_report_v27.json",
        "v41_runtime_budget_report.json",
        "v41_readonly_probe_budget_report.json",
        "v41_probe_cycle_budget_report.json",
        "v41_evidence_closure_budget_report.json",
        "v41_calibration_budget_report.json",
        "v41_dashboard_budget_report.json",
        "v41_report_chain_budget_report.json",
        "v41_runtime_blocker_report.json",
        "no_secret_leak_report_v41.json",
        "no_direct_order_bypass_report_v41.json",
        "no_order_ticket_generation_report_v41.json",
        "no_shadow_order_generation_report_v41.json",
        "no_dry_submit_packet_generation_report_v41.json",
        "no_broker_payload_generation_report_v41.json",
        "no_execution_rehearsal_report_v41.json",
        "no_live_submit_still_disabled_report_v41.json",
        "no_caps_config_modification_report_v41.json",
        "no_browser_automation_report_v41.json",
        "no_mined_repo_execution_report_v41.json",
        "no_fake_transport_score_claimed_live_report_v41.json",
        "no_missing_ack_probe_run_report_v41.json",
        "no_fuzzy_ack_probe_run_report_v41.json",
        "no_sports_source_activation_report_v41.json",
        "no_multi_cycle_controller_to_execution_bridge_report_v41.json",
        "no_probe_expansion_to_execution_bridge_report_v41.json",
        "no_live_score_to_execution_bridge_report_v41.json",
        "no_calibration_to_execution_bridge_report_v41.json",
        "no_source_truth_to_execution_bridge_report_v41.json",
        "no_no_trade_discipline_to_execution_bridge_report_v41.json",
        "no_readiness_ladder_to_execution_bridge_report_v41.json",
        "no_next_action_to_execution_bridge_report_v41.json",
        "no_audit_ledger_to_execution_bridge_report_v41.json",
        "blunder_separation_recheck_v41.json",
        "dummy_canonical_identity_report_v41.json",
        "v40_still_passes_or_partial_expected_v41_report.json",
    )
