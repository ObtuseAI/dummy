from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v27.reports import V27ReportFactory

router = APIRouter(prefix="/api/v27", tags=["v27"])


def _reports() -> dict[str, dict[str, Any]]:
    return V27ReportFactory(enable_network=False).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/integration-mode-probes")
async def integration_mode_probes() -> dict[str, Any]:
    return _slice(
        "integration_mode_public_probe_controller_v1_report.json",
        "integration_mode_policy_report_v1.json",
        "integration_mode_approval_state_report_v1.json",
        "integration_mode_probe_plan_report_v1.json",
        "integration_mode_probe_result_report_v1.json",
        "integration_mode_blocker_report_v1.json",
        "integration_mode_safety_proof_report_v1.json",
    )


@router.get("/public-probe-matrix")
async def public_probe_matrix() -> dict[str, Any]:
    return _slice(
        "public_probe_execution_matrix_v1_report.json",
        "public_probe_candidate_report_v1.json",
        "public_probe_market_class_role_report_v1.json",
        "public_probe_settlement_role_report_v1.json",
        "public_probe_priority_report_v1.json",
        "public_probe_fallback_report_v1.json",
    )


@router.get("/settlement-rule-library")
async def settlement_rule_library() -> dict[str, Any]:
    return _slice(
        "settlement_rule_library_v1_report.json",
        "settlement_rule_definition_report_v1.json",
        "settlement_metric_definition_report_v1.json",
        "settlement_timing_definition_report_v1.json",
        "settlement_source_requirement_report_v1.json",
        "settlement_rule_ambiguity_report_v1.json",
        "settlement_rule_blocker_report_v1.json",
    )


@router.get("/kalshi-settlement-rules")
async def kalshi_settlement_rules() -> dict[str, Any]:
    return _slice(
        "kalshi_settlement_rule_mapper_v3_report.json",
        "kalshi_rule_text_normalizer_report_v1.json",
        "kalshi_rule_market_class_mapper_report_v1.json",
        "kalshi_settlement_rule_candidate_report_v1.json",
        "kalshi_settlement_rule_confidence_report_v1.json",
        "kalshi_settlement_rule_blocker_report_v1.json",
    )


@router.get("/due-forecast-resolution")
async def due_forecast_resolution() -> dict[str, Any]:
    return _slice(
        "due_forecast_resolution_engine_v2_report.json",
        "due_forecast_candidate_v2_report.json",
        "due_forecast_settlement_lookup_report_v1.json",
        "due_forecast_observation_attempt_v2_report.json",
        "due_forecast_resolution_decision_v2_report.json",
        "due_forecast_resolution_blocker_v2_report.json",
    )


@router.get("/weather-live-settlement")
async def weather_live_settlement() -> dict[str, Any]:
    return _slice(
        "weather_live_settlement_resolver_v3_report.json",
        "weather_live_observation_lookup_report_v1.json",
        "weather_station_metric_resolver_report_v1.json",
        "weather_settlement_time_window_report_v1.json",
        "weather_outcome_value_normalizer_report_v1.json",
        "weather_live_settlement_blocker_report_v1.json",
    )


@router.get("/crypto-live-settlement")
async def crypto_live_settlement() -> dict[str, Any]:
    return _slice(
        "crypto_live_settlement_resolver_v3_report.json",
        "crypto_live_price_lookup_report_v1.json",
        "crypto_venue_consensus_v3_report.json",
        "crypto_settlement_time_window_report_v1.json",
        "crypto_outcome_value_normalizer_report_v1.json",
        "crypto_live_settlement_blocker_report_v1.json",
    )


@router.get("/commodity-macro-settlement")
async def commodity_macro_settlement() -> dict[str, Any]:
    return _slice(
        "commodity_macro_settlement_resolver_v1_report.json",
        "commodity_reference_settlement_lookup_report_v1.json",
        "macro_release_settlement_lookup_report_v1.json",
        "public_event_settlement_lookup_report_v1.json",
        "reference_outcome_normalizer_report_v1.json",
        "commodity_macro_settlement_blocker_report_v1.json",
    )


@router.get("/sports-terms")
async def sports_terms() -> dict[str, Any]:
    return _slice(
        "sports_terms_resolution_workbench_v1_report.json",
        "sports_source_terms_candidate_report_v1.json",
        "sports_source_terms_verdict_report_v1.json",
        "sports_schedule_status_approval_plan_report_v1.json",
        "sports_fixture_only_fallback_report_v1.json",
        "sports_terms_blocker_report_v1.json",
    )


@router.get("/sports-adapter-stub")
async def sports_adapter_stub() -> dict[str, Any]:
    return _slice(
        "sports_public_adapter_stub_v2_report.json",
        "sports_schedule_status_stub_report_v1.json",
        "sports_result_settlement_stub_report_v1.json",
        "sports_weather_join_stub_report_v1.json",
        "sports_adapter_mode_report_v1.json",
        "sports_adapter_stub_blocker_report_v1.json",
    )


@router.get("/live-scoring-closure")
async def live_scoring_closure() -> dict[str, Any]:
    return _slice(
        "live_scoring_closure_v2_report.json",
        "live_score_candidate_v2_report.json",
        "live_score_decision_v2_report.json",
        "live_score_metric_v2_report.json",
        "live_score_calibration_write_report_v1.json",
        "live_score_blocker_v2_report.json",
    )


@router.get("/live-calibration")
async def live_calibration() -> dict[str, Any]:
    return _slice(
        "live_calibration_update_v6_report.json",
        "live_calibration_sample_v2_report.json",
        "live_calibration_bucket_v2_report.json",
        "live_calibration_low_sample_guard_v2_report.json",
        "live_calibration_readiness_v2_report.json",
        "live_calibration_blocker_v2_report.json",
    )


@router.get("/forecast-cadence")
async def forecast_cadence() -> dict[str, Any]:
    return _slice(
        "forecast_cadence_v3_report.json",
        "observability_first_forecast_selector_report_v1.json",
        "market_class_cadence_throttle_report_v1.json",
        "forecast_cadence_write_plan_v3_report.json",
        "forecast_cadence_no_trade_plan_v3_report.json",
        "forecast_cadence_observer_plan_v3_report.json",
    )


@router.get("/observer-queue")
async def observer_queue() -> dict[str, Any]:
    return _slice(
        "observer_queue_prioritizer_v3_report.json",
        "observer_priority_record_report_v1.json",
        "observer_due_priority_report_v1.json",
        "observer_settlement_priority_report_v1.json",
        "observer_backlog_state_report_v1.json",
        "observer_queue_blocker_v3_report.json",
    )


@router.get("/source-truth-v9")
async def source_truth_v9() -> dict[str, Any]:
    return _slice(
        "market_class_source_truth_v9_report.json",
        "integration_probe_truth_signal_report_v1.json",
        "settlement_resolution_truth_signal_report_v1.json",
        "live_score_truth_signal_v2_report.json",
        "sports_terms_truth_signal_report_v1.json",
        "source_truth_next_action_v9_report.json",
        "source_truth_starve_promote_policy_v2_report.json",
    )


@router.get("/partial-reduction")
async def partial_reduction() -> dict[str, Any]:
    return _slice(
        "market_class_partial_reduction_engine_v1_report.json",
        "partial_cause_record_report_v1.json",
        "partial_reduction_action_report_v1.json",
        "partial_reduction_priority_report_v1.json",
        "partial_reduction_progress_report_v1.json",
        "partial_remaining_blocker_report_v1.json",
    )


@router.get("/adapter-sprint")
async def adapter_sprint() -> dict[str, Any]:
    return _slice(
        "adapter_sprint_queue_v4_report.json",
        "adapter_sprint_task_v4_report.json",
        "adapter_sprint_market_class_target_report_v1.json",
        "adapter_sprint_settlement_target_report_v1.json",
        "adapter_sprint_acceptance_gate_v4_report.json",
        "adapter_sprint_risk_guard_v4_report.json",
    )


@router.get("/compounding-v11")
async def compounding_v11() -> dict[str, Any]:
    return _slice(
        "market_class_compounding_control_plane_v11_report.json",
        "live_score_growth_queue_v2_report.json",
        "settlement_rule_mapping_queue_v2_report.json",
        "sports_terms_closure_queue_v2_report.json",
        "public_probe_expansion_queue_v2_report.json",
        "next_bundle_recommendation_v27_report.json",
    )


@router.get("/scoreboard-v12")
async def scoreboard_v12() -> dict[str, Any]:
    return _slice(
        "domain_market_class_scoreboard_v12_report.json",
        "integration_probe_scoreboard_report_v1.json",
        "settlement_rule_scoreboard_report_v1.json",
        "live_resolution_scoreboard_report_v1.json",
        "sports_terms_scoreboard_report_v1.json",
        "partial_reduction_scoreboard_report_v1.json",
    )


@router.get("/runtime-budget")
async def runtime_budget() -> dict[str, Any]:
    return _slice(
        "v27_runtime_budget_report_v1.json",
        "integration_probe_runtime_budget_report_v1.json",
        "settlement_rule_mapping_budget_report_v1.json",
        "due_forecast_resolution_budget_report_v1.json",
        "dashboard_cache_policy_v9_report.json",
        "report_chain_runtime_profiler_v10_report.json",
    )


@router.get("/safety")
async def safety() -> dict[str, Any]:
    return _slice(
        "no_secret_leak_report_v27.json",
        "no_kalshi_private_key_leak_report_v27.json",
        "no_source_api_key_leak_report_v27.json",
        "no_github_token_leak_report_v27.json",
        "no_llm_secret_leak_report_v27.json",
        "no_direct_order_bypass_report_v27.json",
        "no_direct_cancel_bypass_report_v27.json",
        "no_live_submit_still_disabled_report_v27.json",
        "no_caps_config_modification_report_v27.json",
        "readonly_only_source_activation_report_v27.json",
        "no_unauthorized_source_report_v27.json",
        "no_questionable_odds_scraping_report_v27.json",
        "no_unapproved_source_activation_report_v27.json",
        "no_commercial_source_without_approval_report_v27.json",
        "no_premium_feed_required_global_blocker_report_v27.json",
        "no_fixture_claimed_real_report_v27.json",
        "no_replay_claimed_live_report_v27.json",
        "no_replay_score_claimed_live_report_v27.json",
        "no_proxy_claimed_exchange_native_report_v27.json",
        "no_context_claimed_edge_report_v27.json",
        "no_example_market_canonical_center_report_v27.json",
        "no_unresolved_forecast_scored_report_v27.json",
        "no_ambiguous_settlement_scored_report_v27.json",
        "no_source_unavailable_forecast_scored_report_v27.json",
        "no_not_due_forecast_scored_report_v27.json",
        "no_outcome_fabrication_report_v27.json",
        "no_github_repo_code_execution_report_v27.json",
        "no_integration_probe_to_execution_bridge_report_v27.json",
        "no_settlement_rule_mapping_to_execution_bridge_report_v27.json",
        "no_due_forecast_resolution_to_execution_bridge_report_v27.json",
        "no_live_scoring_to_execution_bridge_report_v27.json",
        "no_live_calibration_to_execution_bridge_report_v27.json",
        "no_source_truth_to_execution_bridge_report_v27.json",
        "no_adapter_sprint_to_execution_bridge_report_v27.json",
        "blunder_separation_recheck_v27.json",
        "dummy_canonical_identity_report_v27.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice("dummy_mission_state_report_v13.json")
