from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v34.reports import V34ReportFactory
from predator_mesh.v34.run import build_default_v34_state

router = APIRouter(prefix="/api/v34", tags=["v34"])


def _reports() -> dict[str, dict[str, Any]]:
    return V34ReportFactory(enable_network=False, env={}).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/operator-enabled-probe-run-reconciliation")
async def operator_enabled_probe_run_reconciliation() -> dict[str, Any]:
    return _slice(
        "v34_operator_enabled_probe_run_reconciliation_controller_v1_report.json",
        "v34_probe_run_mode_decision_report.json",
        "v34_probe_run_gate_state_report.json",
        "v34_probe_run_operator_packet_report.json",
        "v34_probe_run_execution_plan_report.json",
        "v34_probe_run_result_report.json",
        "v34_probe_run_safety_proof_report.json",
    )


@router.get("/exact-gate-ack")
async def exact_gate_ack() -> dict[str, Any]:
    return _slice(
        "exact_gate_acknowledgement_hardening_v3_report.json",
        "exact_ack_input_record_report.json",
        "exact_ack_validation_decision_report.json",
        "exact_ack_failure_reason_report.json",
        "exact_ack_no_trading_language_guard_report.json",
        "exact_ack_audit_record_report.json",
    )


@router.get("/bounded-readonly-public-probe")
async def bounded_readonly_public_probe() -> dict[str, Any]:
    return _slice(
        "bounded_readonly_public_probe_pass_v2_report.json",
        "bounded_probe_execution_task_report.json",
        "bounded_probe_adapter_family_selection_report.json",
        "bounded_probe_execution_budget_report.json",
        "bounded_probe_execution_outcome_report.json",
        "bounded_probe_execution_failure_report.json",
        "bounded_probe_execution_safety_proof_report.json",
    )


@router.get("/weather-observation-reconciliation")
async def weather_observation_reconciliation() -> dict[str, Any]:
    return _slice(
        "weather_observation_reconciliation_v2_report.json",
        "weather_observation_reconciliation_task_report.json",
        "weather_observation_reconciliation_result_report.json",
        "weather_observation_reconciliation_packet_report.json",
        "weather_observation_reconciliation_settlement_join_report.json",
        "weather_observation_reconciliation_blocker_report.json",
    )


@router.get("/crypto-price-reconciliation")
async def crypto_price_reconciliation() -> dict[str, Any]:
    return _slice(
        "crypto_price_reconciliation_v2_report.json",
        "crypto_price_reconciliation_task_report.json",
        "crypto_price_reconciliation_result_report.json",
        "crypto_price_reconciliation_packet_report.json",
        "crypto_price_reconciliation_venue_consensus_report.json",
        "crypto_price_reconciliation_settlement_join_report.json",
        "crypto_price_reconciliation_blocker_report.json",
    )


@router.get("/public-event-reference-reconciliation")
async def public_event_reference_reconciliation() -> dict[str, Any]:
    return _slice(
        "public_event_reference_reconciliation_v2_report.json",
        "public_event_reference_reconciliation_task_report.json",
        "public_event_reference_reconciliation_result_report.json",
        "public_event_reference_reconciliation_reference_packet_report.json",
        "public_event_reference_reconciliation_settlement_join_report.json",
        "public_event_reference_reconciliation_blocker_report.json",
    )


@router.get("/kalshi-readonly-rule-reconciliation")
async def kalshi_readonly_rule_reconciliation() -> dict[str, Any]:
    return _slice(
        "kalshi_readonly_rule_reconciliation_v2_report.json",
        "kalshi_readonly_rule_reconciliation_task_report.json",
        "kalshi_readonly_rule_reconciliation_result_report.json",
        "kalshi_readonly_rule_reconciliation_rule_packet_report.json",
        "kalshi_readonly_rule_reconciliation_settlement_join_report.json",
        "kalshi_readonly_rule_reconciliation_blocker_report.json",
    )


@router.get("/live-evidence-reconciliation")
async def live_evidence_reconciliation() -> dict[str, Any]:
    return _slice(
        "live_evidence_reconciliation_ledger_v1_report.json",
        "reconciled_live_public_evidence_packet_report.json",
        "reconciled_live_public_evidence_family_summary_report.json",
        "reconciled_live_public_evidence_eligibility_report.json",
        "reconciled_live_public_evidence_freshness_report.json",
        "reconciled_live_public_evidence_blocker_report.json",
    )


@router.get("/settlement-join-reconciliation")
async def settlement_join_reconciliation() -> dict[str, Any]:
    return _slice(
        "settlement_join_reconciliation_v4_report.json",
        "reconciled_settlement_evidence_candidate_report.json",
        "reconciled_settlement_join_decision_report.json",
        "reconciled_settlement_join_confidence_report.json",
        "reconciled_settlement_join_blocker_report.json",
    )


@router.get("/due-forecast-closure-reconciliation")
async def due_forecast_closure_reconciliation() -> dict[str, Any]:
    return _slice(
        "due_forecast_closure_reconciliation_v7_report.json",
        "due_forecast_closure_reconciliation_case_report.json",
        "due_forecast_closure_reconciliation_evidence_match_report.json",
        "due_forecast_closure_reconciliation_decision_report.json",
        "due_forecast_closure_reconciliation_ledger_write_report.json",
        "due_forecast_closure_reconciliation_blocker_report.json",
    )


@router.get("/live-score-closure-reconciliation")
async def live_score_closure_reconciliation() -> dict[str, Any]:
    return _slice(
        "live_score_closure_reconciliation_v5_report.json",
        "live_score_closure_reconciliation_candidate_report.json",
        "live_score_closure_reconciliation_decision_report.json",
        "live_score_closure_reconciliation_metric_report.json",
        "live_score_closure_reconciliation_ledger_write_report.json",
        "live_score_closure_reconciliation_blocker_report.json",
    )


@router.get("/live-calibration-reconciliation")
async def live_calibration_reconciliation() -> dict[str, Any]:
    return _slice(
        "live_calibration_reconciliation_v5_report.json",
        "live_calibration_reconciliation_sample_report.json",
        "live_calibration_reconciliation_bucket_report.json",
        "live_calibration_reconciliation_decision_report.json",
        "live_calibration_reconciliation_warning_report.json",
        "live_calibration_reconciliation_blocker_report.json",
    )


@router.get("/probe-run-artifact-cache")
async def probe_run_artifact_cache() -> dict[str, Any]:
    return _slice(
        "probe_run_artifact_reconciliation_cache_v4_report.json",
        "reconciled_probe_cache_record_report.json",
        "reconciled_probe_cache_manifest_report.json",
        "reconciled_probe_cache_freshness_policy_report.json",
        "reconciled_probe_cache_redaction_audit_report.json",
        "reconciled_probe_cache_blocker_report.json",
    )


@router.get("/reconciled-probe-audit")
async def reconciled_probe_audit() -> dict[str, Any]:
    return _slice(
        "reconciled_probe_audit_ledger_v3_report.json",
        "reconciled_probe_audit_record_report.json",
        "reconciled_probe_gate_audit_report.json",
        "reconciled_probe_source_audit_report.json",
        "reconciled_probe_observation_audit_report.json",
        "reconciled_probe_score_audit_report.json",
        "reconciled_probe_safety_audit_report.json",
    )


@router.get("/sports-probe-exclusion")
async def sports_probe_exclusion() -> dict[str, Any]:
    return _slice(
        "sports_probe_exclusion_recheck_v5_report.json",
        "sports_probe_exclusion_recheck_decision_report.json",
        "sports_source_approval_state_v5_report.json",
        "sports_fixture_mode_proof_v5_report.json",
        "sports_operator_approval_packet_v5_report.json",
        "sports_probe_exclusion_recheck_blocker_report.json",
    )


@router.get("/source-truth-v15")
async def source_truth_v15() -> dict[str, Any]:
    return _slice(
        "source_truth_probe_reconciliation_v15_report.json",
        "reconciled_probe_health_truth_signal_report.json",
        "reconciled_evidence_compatibility_truth_signal_report.json",
        "reconciled_observation_closure_truth_signal_report.json",
        "reconciled_live_score_truth_signal_report.json",
        "reconciled_source_recovery_action_v15_report.json",
    )


@router.get("/partial-reduction")
async def partial_reduction() -> dict[str, Any]:
    return _slice(
        "v34_partial_reduction_ledger_report.json",
        "v34_partial_cause_before_after_report.json",
        "v34_partial_reduction_attempt_report.json",
        "v34_partial_reduction_result_report.json",
        "v34_remaining_partial_cause_report.json",
        "v34_pass_delta_report.json",
    )


@router.get("/probe-reconciliation-sprint-v11")
async def probe_reconciliation_sprint_v11() -> dict[str, Any]:
    return _slice(
        "probe_reconciliation_sprint_queue_v11_report.json",
        "probe_reconciliation_sprint_v11_task_report.json",
        "probe_reconciliation_sprint_v11_source_target_report.json",
        "probe_reconciliation_sprint_v11_settlement_target_report.json",
        "probe_reconciliation_sprint_v11_scoring_target_report.json",
        "probe_reconciliation_sprint_v11_operator_action_report.json",
        "probe_reconciliation_sprint_v11_risk_guard_report.json",
    )


@router.get("/compounding-v18")
async def compounding_v18() -> dict[str, Any]:
    return _slice(
        "probe_reconciliation_to_score_compounding_control_plane_v18_report.json",
        "probe_reconciliation_run_queue_v5_report.json",
        "evidence_reconciliation_queue_v2_report.json",
        "settlement_reconciliation_queue_v2_report.json",
        "forecast_closure_reconciliation_queue_v2_report.json",
        "live_score_closure_growth_queue_v5_report.json",
        "next_bundle_recommendation_v34_report.json",
    )


@router.get("/market-class-scoreboard")
async def market_class_scoreboard() -> dict[str, Any]:
    return _slice(
        "domain_market_class_scoreboard_v19_report.json",
        "probe_reconciliation_run_scoreboard_report.json",
        "live_evidence_reconciliation_scoreboard_report.json",
        "settlement_reconciliation_scoreboard_report.json",
        "due_forecast_closure_reconciliation_scoreboard_report.json",
        "live_score_closure_reconciliation_scoreboard_report.json",
    )


@router.get("/transport-guard")
async def transport_guard() -> dict[str, Any]:
    state = build_default_v34_state(enable_network=False, env={})
    guard = state["transport_guard"]
    state_slice = {
        "transport_guard_mode": guard.mode,
        "transport_guard_network_enabled": guard.network_enabled,
        "transport_guard_transport_class": guard.transport_class,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "execution_bridge_present": False,
    }
    return _safe(state_slice)


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dummy_mission_state_report_v20.json",
        "dashboard_v34_report_v1.json",
        "v34_runtime_budget_report_v1.json",
        "probe_reconciliation_runtime_budget_v1_report.json",
        "live_evidence_reconciliation_budget_v1_report.json",
        "forecast_closure_reconciliation_runtime_budget_v1_report.json",
        "dashboard_cache_policy_v16_report.json",
        "report_chain_runtime_profiler_v17_report.json",
    )
