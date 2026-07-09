from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v33.reports import V33ReportFactory

router = APIRouter(prefix="/api/v33", tags=["v33"])


def _reports() -> dict[str, dict[str, Any]]:
    return V33ReportFactory(enable_network=False, env={}).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/operator-enabled-probe-run")
async def operator_enabled_probe_run() -> dict[str, Any]:
    return _slice(
        "v33_operator_enabled_probe_run_controller_v1_report.json",
        "v33_probe_run_mode_decision_report.json",
        "v33_probe_run_gate_state_report.json",
        "v33_probe_run_operator_packet_report.json",
        "v33_probe_run_execution_plan_report.json",
        "v33_probe_run_result_report.json",
        "v33_probe_run_safety_proof_report.json",
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


@router.get("/minimal-live-public-probe")
async def minimal_live_public_probe() -> dict[str, Any]:
    return _slice(
        "minimal_live_public_probe_execution_v1_report.json",
        "live_probe_execution_task_report.json",
        "live_probe_adapter_family_selection_report.json",
        "live_probe_execution_budget_report.json",
        "live_probe_execution_outcome_report.json",
        "live_probe_execution_failure_report.json",
        "live_probe_execution_safety_proof_report.json",
    )


@router.get("/weather-enabled-probe")
async def weather_enabled_probe() -> dict[str, Any]:
    return _slice(
        "weather_enabled_probe_run_v1_report.json",
        "weather_enabled_probe_task_report.json",
        "weather_enabled_probe_result_report.json",
        "weather_enabled_observation_packet_report.json",
        "weather_enabled_settlement_join_report.json",
        "weather_enabled_probe_blocker_report.json",
    )


@router.get("/crypto-enabled-probe")
async def crypto_enabled_probe() -> dict[str, Any]:
    return _slice(
        "crypto_enabled_probe_run_v1_report.json",
        "crypto_enabled_probe_task_report.json",
        "crypto_enabled_probe_result_report.json",
        "crypto_enabled_price_packet_report.json",
        "crypto_enabled_venue_consensus_report.json",
        "crypto_enabled_settlement_join_report.json",
        "crypto_enabled_probe_blocker_report.json",
    )


@router.get("/public-event-enabled-probe")
async def public_event_enabled_probe() -> dict[str, Any]:
    return _slice(
        "public_event_enabled_probe_run_v1_report.json",
        "public_event_enabled_probe_task_report.json",
        "public_event_enabled_probe_result_report.json",
        "public_event_enabled_reference_packet_report.json",
        "public_event_enabled_settlement_join_report.json",
        "public_event_enabled_probe_blocker_report.json",
    )


@router.get("/kalshi-readonly-enabled-probe")
async def kalshi_readonly_enabled_probe() -> dict[str, Any]:
    return _slice(
        "kalshi_readonly_enabled_probe_run_v1_report.json",
        "kalshi_readonly_enabled_probe_task_report.json",
        "kalshi_readonly_enabled_probe_result_report.json",
        "kalshi_readonly_rule_packet_report.json",
        "kalshi_readonly_settlement_join_report.json",
        "kalshi_readonly_enabled_probe_blocker_report.json",
    )


@router.get("/live-public-evidence")
async def live_public_evidence() -> dict[str, Any]:
    return _slice(
        "live_public_evidence_ingestion_v3_report.json",
        "enabled_live_public_evidence_packet_report.json",
        "enabled_live_public_evidence_family_summary_report.json",
        "enabled_live_public_evidence_eligibility_report.json",
        "enabled_live_public_evidence_freshness_report.json",
        "enabled_live_public_evidence_blocker_report.json",
    )


@router.get("/settlement-evidence-join")
async def settlement_evidence_join() -> dict[str, Any]:
    return _slice(
        "settlement_evidence_join_v3_report.json",
        "live_settlement_evidence_candidate_report.json",
        "live_settlement_join_decision_report.json",
        "live_settlement_join_confidence_report.json",
        "live_settlement_join_blocker_report.json",
    )


@router.get("/due-forecast-observation")
async def due_forecast_observation() -> dict[str, Any]:
    return _slice(
        "due_forecast_observation_run_v6_report.json",
        "due_observation_run_case_report.json",
        "due_observation_evidence_match_report.json",
        "due_observation_decision_report.json",
        "due_observation_ledger_write_report.json",
        "due_observation_blocker_report.json",
    )


@router.get("/live-score-observation")
async def live_score_observation() -> dict[str, Any]:
    return _slice(
        "live_score_observation_run_v4_report.json",
        "live_score_observation_candidate_report.json",
        "live_score_observation_decision_report.json",
        "live_score_observation_metric_report.json",
        "live_score_observation_ledger_write_report.json",
        "live_score_observation_blocker_report.json",
    )


@router.get("/live-calibration-observation")
async def live_calibration_observation() -> dict[str, Any]:
    return _slice(
        "live_calibration_observation_run_v4_report.json",
        "live_calibration_observation_sample_report.json",
        "live_calibration_observation_bucket_report.json",
        "live_calibration_observation_decision_report.json",
        "live_calibration_observation_warning_report.json",
        "live_calibration_observation_blocker_report.json",
    )


@router.get("/public-probe-cache")
async def public_probe_cache() -> dict[str, Any]:
    return _slice(
        "public_probe_artifact_cache_v3_report.json",
        "enabled_probe_cache_record_report.json",
        "enabled_probe_cache_manifest_report.json",
        "enabled_probe_cache_freshness_policy_report.json",
        "enabled_probe_cache_redaction_audit_report.json",
        "enabled_probe_cache_blocker_report.json",
    )


@router.get("/enabled-probe-audit")
async def enabled_probe_audit() -> dict[str, Any]:
    return _slice(
        "enabled_probe_audit_ledger_v2_report.json",
        "enabled_probe_audit_record_report.json",
        "enabled_probe_gate_audit_report.json",
        "enabled_probe_source_audit_report.json",
        "enabled_probe_observation_audit_report.json",
        "enabled_probe_score_audit_report.json",
        "enabled_probe_safety_audit_report.json",
    )


@router.get("/sports-probe-exclusion")
async def sports_probe_exclusion() -> dict[str, Any]:
    return _slice(
        "sports_probe_exclusion_guard_v4_report.json",
        "sports_probe_exclusion_decision_report.json",
        "sports_source_approval_state_v4_report.json",
        "sports_fixture_mode_proof_v4_report.json",
        "sports_operator_approval_packet_v4_report.json",
        "sports_probe_exclusion_blocker_report.json",
    )


@router.get("/source-truth-v14")
async def source_truth_v14() -> dict[str, Any]:
    return _slice(
        "source_truth_enabled_probe_evidence_v14_report.json",
        "enabled_probe_health_truth_signal_report.json",
        "enabled_evidence_compatibility_truth_signal_report.json",
        "enabled_observation_closure_truth_signal_report.json",
        "enabled_live_score_truth_signal_report.json",
        "enabled_source_recovery_action_v14_report.json",
    )


@router.get("/partial-reduction")
async def partial_reduction() -> dict[str, Any]:
    return _slice(
        "v33_partial_reduction_ledger_report.json",
        "v33_partial_cause_before_after_report.json",
        "v33_partial_reduction_attempt_report.json",
        "v33_partial_reduction_result_report.json",
        "v33_remaining_partial_cause_report.json",
        "v33_pass_delta_report.json",
    )


@router.get("/probe-sprint-v10")
async def probe_sprint_v10() -> dict[str, Any]:
    return _slice(
        "operator_enabled_probe_sprint_queue_v10_report.json",
        "probe_sprint_v10_task_report.json",
        "probe_sprint_v10_source_target_report.json",
        "probe_sprint_v10_settlement_target_report.json",
        "probe_sprint_v10_scoring_target_report.json",
        "probe_sprint_v10_operator_action_report.json",
        "probe_sprint_v10_risk_guard_report.json",
    )


@router.get("/compounding-v17")
async def compounding_v17() -> dict[str, Any]:
    return _slice(
        "enabled_probe_to_score_compounding_control_plane_v17_report.json",
        "enabled_probe_run_queue_v5_report.json",
        "evidence_ingestion_queue_v2_report.json",
        "settlement_join_queue_v2_report.json",
        "observation_run_queue_v2_report.json",
        "live_score_growth_queue_v4_report.json",
        "next_bundle_recommendation_v33_report.json",
    )


@router.get("/market-class-scoreboard")
async def market_class_scoreboard() -> dict[str, Any]:
    return _slice(
        "domain_market_class_scoreboard_v18_report.json",
        "enabled_probe_run_scoreboard_report.json",
        "live_evidence_ingestion_scoreboard_report.json",
        "settlement_join_scoreboard_report.json",
        "due_observation_run_scoreboard_report.json",
        "live_score_run_scoreboard_report.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dummy_mission_state_report_v19.json",
        "dashboard_v33_report_v1.json",
        "v33_runtime_budget_report_v1.json",
        "enabled_probe_runtime_budget_v1_report.json",
        "live_evidence_ingestion_budget_v1_report.json",
        "observation_run_runtime_budget_v1_report.json",
        "dashboard_cache_policy_v15_report.json",
        "report_chain_runtime_profiler_v16_report.json",
    )
