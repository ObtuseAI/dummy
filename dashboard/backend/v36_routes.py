from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v36.reports import V36ReportFactory

router = APIRouter(prefix="/api/v36", tags=["v36"])


def _reports() -> dict[str, dict[str, Any]]:
    return V36ReportFactory().build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/real-probe-run")
async def real_probe_run() -> dict[str, Any]:
    return _slice(
        "v36_real_probe_run_controller_v1_report.json",
        "v36_probe_run_input_state_report.json",
        "v36_probe_run_gate_decision_report.json",
        "v36_probe_run_execution_plan_report.json",
        "v36_probe_run_result_report.json",
        "v36_probe_run_blocker_report.json",
        "v36_probe_run_safety_proof_report.json",
    )


@router.get("/exact-gate")
async def exact_gate() -> dict[str, Any]:
    return _slice(
        "exact_operator_gate_runtime_v5_report.json",
        "exact_gate_snapshot_report.json",
        "exact_ack_decision_report.json",
        "exact_run_decision_report.json",
        "exact_failure_instruction_report.json",
        "exact_gate_audit_proof_report.json",
    )


@router.get("/real-transport")
async def real_transport() -> dict[str, Any]:
    return _slice(
        "real_readonly_probe_transport_v1_report.json",
        "real_transport_timeout_report.json",
        "real_transport_request_cap_report.json",
        "real_transport_failure_labeling_report.json",
        "real_transport_construction_guard_report.json",
    )


@router.get("/minimal-real-pass")
async def minimal_real_pass() -> dict[str, Any]:
    return _slice(
        "minimal_real_public_probe_pass_v1_report.json",
        "minimal_real_probe_family_cap_report.json",
        "minimal_real_probe_total_cap_report.json",
        "minimal_real_probe_timeout_budget_report.json",
        "minimal_real_probe_no_retry_storm_report.json",
        "minimal_real_probe_pass_blocker_report.json",
    )


@router.get("/weather-real-probe")
async def weather_real_probe() -> dict[str, Any]:
    return _slice(
        "weather_real_public_probe_v1_report.json",
        "weather_real_probe_packet_report.json",
        "weather_real_probe_settlement_join_report.json",
        "weather_real_probe_blocker_report.json",
    )


@router.get("/crypto-real-probe")
async def crypto_real_probe() -> dict[str, Any]:
    return _slice(
        "crypto_real_public_probe_v1_report.json",
        "crypto_real_probe_packet_report.json",
        "crypto_real_probe_settlement_join_report.json",
        "crypto_real_probe_blocker_report.json",
    )


@router.get("/public-event-real-probe")
async def public_event_real_probe() -> dict[str, Any]:
    return _slice(
        "public_event_real_public_probe_v1_report.json",
        "public_event_real_probe_packet_report.json",
        "public_event_real_probe_settlement_join_report.json",
        "public_event_real_probe_blocker_report.json",
    )


@router.get("/kalshi-real-probe")
async def kalshi_real_probe() -> dict[str, Any]:
    return _slice(
        "kalshi_readonly_real_probe_v1_report.json",
        "kalshi_readonly_packet_report.json",
        "kalshi_readonly_settlement_join_report.json",
        "kalshi_readonly_blocker_report.json",
    )


@router.get("/real-evidence-ledger")
async def real_evidence_ledger() -> dict[str, Any]:
    return _slice(
        "real_live_public_evidence_ledger_v1_report.json",
        "real_live_public_evidence_acceptance_report.json",
        "real_live_public_evidence_rejection_report.json",
        "real_live_public_evidence_provenance_report.json",
        "real_live_public_evidence_ledger_blocker_report.json",
    )


@router.get("/real-settlement-join")
async def real_settlement_join() -> dict[str, Any]:
    return _slice(
        "real_settlement_join_v1_report.json",
        "real_settlement_join_family_scope_report.json",
        "real_settlement_join_validation_report.json",
        "real_settlement_join_ambiguity_report.json",
        "real_settlement_join_blocker_report.json",
    )


@router.get("/real-due-observation")
async def real_due_observation() -> dict[str, Any]:
    return _slice(
        "real_due_forecast_observation_closure_v1_report.json",
        "real_due_observation_due_count_report.json",
        "real_due_observation_observed_count_report.json",
        "real_due_observation_unresolved_count_report.json",
        "real_due_observation_blocker_report.json",
    )


@router.get("/real-live-score")
async def real_live_score() -> dict[str, Any]:
    return _slice(
        "real_live_score_seed_v1_report.json",
        "real_live_score_mode_report.json",
        "real_live_score_low_sample_report.json",
        "real_live_score_pnl_claim_guard_report.json",
        "real_live_score_blocker_report.json",
    )


@router.get("/real-live-calibration")
async def real_live_calibration() -> dict[str, Any]:
    return _slice(
        "real_live_calibration_seed_v1_report.json",
        "real_live_calibration_source_mode_report.json",
        "real_live_calibration_low_sample_blocker_report.json",
    )


@router.get("/real-probe-cache")
async def real_probe_cache() -> dict[str, Any]:
    return _slice(
        "real_probe_artifact_cache_v1_report.json",
        "real_probe_cache_redaction_report.json",
        "real_probe_cache_freshness_report.json",
        "real_probe_cache_promotion_guard_report.json",
    )


@router.get("/real-probe-audit")
async def real_probe_audit() -> dict[str, Any]:
    return _slice(
        "real_probe_audit_ledger_v1_report.json",
        "real_probe_audit_append_only_report.json",
        "real_probe_audit_gate_record_report.json",
        "real_probe_audit_transport_record_report.json",
        "real_probe_audit_evidence_record_report.json",
    )


@router.get("/fake-real-separation")
async def fake_real_separation() -> dict[str, Any]:
    return _slice(
        "fake_to_real_evidence_separation_v1_report.json",
        "fake_pipeline_score_count_report.json",
        "real_live_score_count_report.json",
        "fake_to_real_separation_enforcement_report.json",
        "fake_to_real_promotion_blocker_report.json",
    )


@router.get("/sports-fixture-only")
async def sports_fixture_only() -> dict[str, Any]:
    return _slice(
        "sports_fixture_only_real_probe_recheck_v7_report.json",
        "sports_mode_check_v7_report.json",
        "sports_odds_scraping_guard_v7_report.json",
        "sports_approval_packet_status_v7_report.json",
    )


@router.get("/source-truth-v17")
async def source_truth_v17() -> dict[str, Any]:
    return _slice(
        "source_truth_v17_real_probe_and_sample_readiness_report.json",
        "source_truth_health_signal_report.json",
        "source_truth_availability_signal_report.json",
        "source_truth_usefulness_signal_report.json",
        "source_truth_next_action_v17_report.json",
    )


@router.get("/partial-reduction")
async def partial_reduction() -> dict[str, Any]:
    return _slice(
        "v36_partial_reduction_ledger_report.json",
        "v36_partial_cause_before_after_report.json",
        "v36_pass_delta_report.json",
        "v36_operator_action_when_gate_disabled_report.json",
    )


@router.get("/sprint-v13")
async def sprint_v13() -> dict[str, Any]:
    return _slice(
        "v36_real_probe_sprint_queue_v13_report.json",
        "v36_sprint_task_v13_report.json",
        "v36_sprint_source_target_report.json",
        "v36_sprint_settlement_target_report.json",
        "v36_sprint_scoring_target_report.json",
        "v36_sprint_operator_action_report.json",
    )


@router.get("/compounding-v20")
async def compounding_v20() -> dict[str, Any]:
    return _slice(
        "v36_compounding_control_plane_v20_report.json",
        "v36_probe_queue_report.json",
        "v36_evidence_queue_report.json",
        "v36_settlement_queue_report.json",
        "v36_observation_queue_report.json",
        "v36_score_queue_report.json",
        "v36_next_bundle_recommendation_report.json",
    )


@router.get("/market-class-scoreboard")
async def market_class_scoreboard() -> dict[str, Any]:
    return _slice(
        "domain_market_class_scoreboard_v21_report.json",
        "v36_gate_state_scoreboard_report.json",
        "v36_real_evidence_scoreboard_report.json",
        "v36_fake_pipeline_scoreboard_report.json",
        "v36_sample_status_scoreboard_report.json",
        "v36_next_action_scoreboard_report.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice(
        "dummy_mission_state_report_v22.json",
        "dashboard_v36_report_v1.json",
        "v36_runtime_budget_report_v1.json",
        "real_probe_runtime_budget_v1_report.json",
        "real_transport_runtime_budget_v1_report.json",
        "real_closure_runtime_budget_v1_report.json",
        "dashboard_cache_policy_v18_report.json",
        "report_chain_runtime_profiler_v19_report.json",
    )
