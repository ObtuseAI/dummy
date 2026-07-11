from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v40.reports import V40ReportFactory

router = APIRouter(prefix="/api/v40", tags=["v40"])


def _reports() -> dict[str, dict[str, Any]]:
    return V40ReportFactory().build()


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


@router.get("/sample-expansion-controller")
async def sample_expansion_controller() -> dict[str, Any]:
    return _slice(
        "v40_real_score_sample_expansion_controller_v1_report.json",
        "v40_sample_expansion_input_state_report.json",
        "v40_sample_expansion_gate_decision_report.json",
        "v40_sample_expansion_plan_report.json",
        "v40_sample_expansion_result_report.json",
        "v40_sample_expansion_blocker_report.json",
        "v40_sample_expansion_safety_proof_report.json",
    )


@router.get("/exact-gate")
async def exact_gate() -> dict[str, Any]:
    return _slice(
        "exact_gate_runtime_v8_report.json",
        "v40_gate_snapshot_report.json",
        "v40_ack_validation_decision_report.json",
        "v40_gate_visibility_check_report.json",
        "v40_gate_run_authorization_report.json",
        "v40_gate_failure_instruction_report.json",
        "v40_gate_safety_proof_report.json",
    )


@router.get("/v39-baseline")
async def v39_baseline() -> dict[str, Any]:
    return _slice(
        "v39_baseline_readback_v1_report.json",
        "v39_baseline_final_report_readback_report.json",
        "v39_baseline_mission_state_readback_report.json",
        "v39_baseline_count_integrity_check_report.json",
        "v39_baseline_safety_carry_forward_report.json",
        "v39_baseline_blocker_report.json",
    )


@router.get("/real-public-probe-expansion")
async def real_public_probe_expansion() -> dict[str, Any]:
    return _slice(
        "real_public_probe_expansion_v1_report.json",
        "real_public_probe_expansion_family_plan_report.json",
        "real_public_probe_expansion_budget_report.json",
        "real_public_probe_expansion_run_result_report.json",
        "real_public_probe_expansion_failure_summary_report.json",
        "real_public_probe_expansion_safety_proof_report.json",
    )


@router.get("/expanded-live-evidence")
async def expanded_live_evidence() -> dict[str, Any]:
    return _slice(
        "expanded_live_public_evidence_ledger_v1_report.json",
        "expanded_live_public_evidence_packet_report.json",
        "expanded_evidence_mode_decision_report.json",
        "expanded_evidence_freshness_check_report.json",
        "expanded_evidence_deduplication_check_report.json",
        "expanded_evidence_family_summary_report.json",
        "expanded_evidence_blocker_report.json",
        "expanded_evidence_safety_proof_report.json",
    )


@router.get("/expanded-settlement")
async def expanded_settlement() -> dict[str, Any]:
    return _slice(
        "expanded_settlement_join_v1_report.json",
        "expanded_settlement_join_candidate_report.json",
        "expanded_settlement_join_decision_report.json",
        "expanded_settlement_join_confidence_report.json",
        "expanded_settlement_join_family_summary_report.json",
        "expanded_settlement_join_blocker_report.json",
        "expanded_settlement_join_safety_proof_report.json",
    )


@router.get("/expanded-observation")
async def expanded_observation() -> dict[str, Any]:
    return _slice(
        "expanded_due_observation_closure_v1_report.json",
        "expanded_due_observation_case_report.json",
        "expanded_due_observation_evidence_match_report.json",
        "expanded_due_observation_decision_report.json",
        "expanded_due_observation_ledger_write_report.json",
        "expanded_due_observation_family_summary_report.json",
        "expanded_due_observation_blocker_report.json",
        "expanded_due_observation_safety_proof_report.json",
    )


@router.get("/expanded-real-live-score")
async def expanded_real_live_score() -> dict[str, Any]:
    return _slice(
        "expanded_real_live_score_sample_v1_report.json",
        "expanded_real_live_score_candidate_report.json",
        "expanded_real_live_score_decision_report.json",
        "expanded_real_live_score_metric_report.json",
        "expanded_real_live_score_ledger_write_report.json",
        "expanded_real_live_score_family_summary_report.json",
        "expanded_real_live_score_blocker_report.json",
        "expanded_real_live_score_safety_proof_report.json",
    )


@router.get("/calibration-growth")
async def calibration_growth() -> dict[str, Any]:
    return _slice(
        "real_calibration_sample_growth_v1_report.json",
        "real_calibration_sample_growth_bucket_report.json",
        "real_calibration_confidence_decision_report.json",
        "real_calibration_low_sample_warning_report.json",
        "real_calibration_market_class_summary_report.json",
        "real_calibration_blocker_report.json",
        "real_calibration_safety_proof_report.json",
    )


@router.get("/source-truth-v21")
async def source_truth_v21() -> dict[str, Any]:
    return _slice(
        "source_truth_v21_real_sample_growth_report.json",
        "source_truth_real_probe_growth_signal_report.json",
        "source_truth_real_evidence_growth_signal_report.json",
        "source_truth_real_settlement_growth_signal_report.json",
        "source_truth_real_score_growth_signal_report.json",
        "source_truth_real_no_trade_signal_report.json",
        "source_truth_v21_next_action_report.json",
        "source_truth_v21_safety_proof_report.json",
    )


@router.get("/no-trade-discipline")
async def no_trade_discipline() -> dict[str, Any]:
    return _slice(
        "no_trade_discipline_real_sample_v1_report.json",
        "no_trade_real_evidence_case_report.json",
        "no_trade_reason_quality_report.json",
        "no_trade_avoided_bad_score_report.json",
        "no_trade_market_class_summary_report.json",
        "no_trade_discipline_blocker_report.json",
        "no_trade_discipline_safety_proof_report.json",
    )


@router.get("/market-class-scoreboard")
async def market_class_scoreboard() -> dict[str, Any]:
    return _slice(
        "market_class_real_sample_scoreboard_v1_report.json",
        "market_class_real_sample_row_report.json",
        "market_class_evidence_coverage_report.json",
        "market_class_settlement_coverage_report.json",
        "market_class_score_coverage_report.json",
        "market_class_calibration_coverage_report.json",
        "market_class_next_action_report.json",
    )


@router.get("/next-action")
async def next_action() -> dict[str, Any]:
    return _slice(
        "completion_oriented_next_action_v40_report.json",
        "v40_next_action_candidate_report.json",
        "v40_next_action_decision_report.json",
        "v40_next_action_reason_report.json",
        "v40_next_action_blocker_report.json",
        "v40_next_action_safety_proof_report.json",
    )


@router.get("/audit-ledger")
async def audit_ledger() -> dict[str, Any]:
    return _slice(
        "v40_real_sample_audit_ledger_report.json",
        "v40_real_sample_audit_record_report.json",
        "v40_gate_audit_record_report.json",
        "v40_source_audit_record_report.json",
        "v40_evidence_audit_record_report.json",
        "v40_settlement_audit_record_report.json",
        "v40_score_audit_record_report.json",
        "v40_calibration_audit_record_report.json",
        "v40_safety_audit_record_report.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dashboard_v40_report_v1.json",
        "v40_api_surface_report_v1.json",
        "v40_dashboard_payload_safety_report_v1.json",
        "dummy_mission_state_report_v26.json",
        "v40_runtime_budget_report.json",
        "v40_readonly_probe_budget_report.json",
        "v40_evidence_closure_budget_report.json",
        "v40_calibration_budget_report.json",
        "v40_dashboard_budget_report.json",
        "v40_report_chain_budget_report.json",
        "v40_runtime_blocker_report.json",
        "no_secret_leak_report_v40.json",
        "no_direct_order_bypass_report_v40.json",
        "no_live_submit_still_disabled_report_v40.json",
        "no_caps_config_modification_report_v40.json",
        "no_browser_automation_report_v40.json",
        "no_mined_repo_execution_report_v40.json",
        "no_fake_transport_score_claimed_live_report_v40.json",
        "no_missing_ack_probe_run_report_v40.json",
        "no_fuzzy_ack_probe_run_report_v40.json",
        "no_sports_source_activation_report_v40.json",
        "no_sample_expansion_controller_to_execution_bridge_report_v40.json",
        "no_source_run_to_execution_bridge_report_v40.json",
        "no_live_score_to_execution_bridge_report_v40.json",
        "no_calibration_to_execution_bridge_report_v40.json",
        "no_source_truth_to_execution_bridge_report_v40.json",
        "no_no_trade_discipline_to_execution_bridge_report_v40.json",
        "no_next_action_to_execution_bridge_report_v40.json",
        "no_audit_ledger_to_execution_bridge_report_v40.json",
        "blunder_separation_recheck_v40.json",
        "dummy_canonical_identity_report_v40.json",
        "v39_still_passes_or_partial_expected_v40_report.json",
    )
