from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v26.reports import V26ReportFactory

router = APIRouter(prefix="/api/v26", tags=["v26"])


def _reports() -> dict[str, dict[str, Any]]:
    return V26ReportFactory(enable_network=False).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/keyless-public-adapters")
async def keyless_public_adapters() -> dict[str, Any]:
    return _slice(
        "keyless_public_adapter_registry_v2_report.json",
        "keyless_public_adapter_entry_report_v1.json",
        "keyless_public_adapter_capability_report_v1.json",
        "keyless_public_adapter_legality_report_v1.json",
        "keyless_public_adapter_health_report_v1.json",
        "keyless_public_adapter_blocker_report_v1.json",
    )


@router.get("/keyless-probes")
async def keyless_probes() -> dict[str, Any]:
    return _slice(
        "keyless_adapter_probe_orchestrator_v1_report.json",
        "keyless_probe_task_report_v1.json",
        "keyless_probe_budget_report_v1.json",
        "keyless_probe_result_report_v1.json",
        "keyless_probe_fallback_report_v1.json",
        "keyless_probe_safety_proof_report_v1.json",
    )


@router.get("/weather-settlement")
async def weather_settlement() -> dict[str, Any]:
    return _slice(
        "weather_settlement_expansion_v2_report.json",
        "weather_station_resolver_v2_report.json",
        "weather_observation_resolver_v2_report.json",
        "weather_threshold_settlement_plan_v2_report.json",
        "weather_event_settlement_plan_v2_report.json",
        "weather_settlement_blocker_v2_report.json",
    )


@router.get("/crypto-settlement")
async def crypto_settlement() -> dict[str, Any]:
    return _slice(
        "crypto_settlement_expansion_v2_report.json",
        "crypto_public_price_resolver_v2_report.json",
        "crypto_venue_consensus_resolver_v2_report.json",
        "crypto_threshold_settlement_plan_v2_report.json",
        "crypto_range_settlement_plan_v2_report.json",
        "crypto_settlement_blocker_v2_report.json",
    )


@router.get("/commodity-reference")
async def commodity_reference() -> dict[str, Any]:
    return _slice(
        "commodity_public_reference_adapter_v1_report.json",
        "commodity_reference_source_candidate_report_v1.json",
        "commodity_reference_evidence_report_v1.json",
        "commodity_reference_settlement_plan_report_v1.json",
        "commodity_reference_freshness_gate_report_v1.json",
        "commodity_reference_blocker_report_v1.json",
    )


@router.get("/finance-macro-events")
async def finance_macro_events() -> dict[str, Any]:
    return _slice(
        "finance_macro_public_event_adapter_v1_report.json",
        "macro_event_source_candidate_report_v1.json",
        "macro_release_evidence_report_v1.json",
        "macro_settlement_plan_report_v1.json",
        "macro_release_freshness_gate_report_v1.json",
        "macro_event_blocker_report_v1.json",
    )


@router.get("/sports-schedule-status")
async def sports_schedule_status() -> dict[str, Any]:
    return _slice(
        "sports_public_schedule_status_adapter_v1_report.json",
        "sports_public_source_candidate_report_v1.json",
        "sports_schedule_evidence_report_v1.json",
        "sports_event_status_evidence_report_v1.json",
        "sports_settlement_plan_report_v1.json",
        "sports_source_terms_guard_v2_report.json",
        "sports_adapter_blocker_report_v1.json",
    )


@router.get("/public-events")
async def public_events() -> dict[str, Any]:
    return _slice(
        "public_event_generic_adapter_v1_report.json",
        "public_event_source_candidate_report_v1.json",
        "public_event_evidence_report_v1.json",
        "public_event_settlement_plan_report_v1.json",
        "public_event_legality_gate_report_v1.json",
        "public_event_blocker_report_v1.json",
    )


@router.get("/kalshi-readonly-join")
async def kalshi_readonly_join() -> dict[str, Any]:
    return _slice(
        "kalshi_readonly_market_class_join_v2_report.json",
        "kalshi_market_class_candidate_report_v1.json",
        "kalshi_settlement_hint_report_v1.json",
        "kalshi_evidence_join_candidate_report_v1.json",
        "kalshi_join_blocker_report_v1.json",
    )


@router.get("/settlement-closure")
async def settlement_closure() -> dict[str, Any]:
    return _slice(
        "settlement_closure_engine_v1_report.json",
        "settlement_closure_candidate_report_v1.json",
        "settlement_closure_action_report_v1.json",
        "settlement_closure_priority_report_v1.json",
        "settlement_closure_blocker_report_v1.json",
        "settlement_closure_proof_report_v1.json",
    )


@router.get("/forecast-resolution")
async def forecast_resolution() -> dict[str, Any]:
    return _slice(
        "forecast_resolution_accelerator_v1_report.json",
        "due_forecast_resolution_candidate_report_v1.json",
        "resolution_attempt_plan_report_v1.json",
        "resolution_attempt_result_report_v1.json",
        "observable_forecast_expansion_candidate_report_v1.json",
        "resolution_accelerator_blocker_report_v1.json",
    )


@router.get("/forecast-cadence")
async def forecast_cadence() -> dict[str, Any]:
    return _slice(
        "market_class_forecast_cadence_v2_report.json",
        "cadence_eligibility_score_v2_report.json",
        "cadence_observable_priority_report_v1.json",
        "cadence_forecast_write_v2_report.json",
        "cadence_no_trade_write_v2_report.json",
        "cadence_observer_queue_write_v2_report.json",
    )


@router.get("/live-scoring-closure")
async def live_scoring_closure() -> dict[str, Any]:
    return _slice(
        "live_scoring_closure_v1_report.json",
        "live_score_closure_candidate_report_v1.json",
        "live_score_closure_result_report_v1.json",
        "live_score_closure_blocker_report_v1.json",
        "live_score_ledger_write_report_v1.json",
        "live_score_calibration_trigger_report_v1.json",
    )


@router.get("/replay-to-live")
async def replay_to_live() -> dict[str, Any]:
    return _slice(
        "replay_to_live_candidate_selector_v1_report.json",
        "replay_performance_signal_report_v1.json",
        "replay_to_live_promotion_candidate_report_v1.json",
        "replay_to_live_promotion_guard_report_v1.json",
        "replay_to_live_blocker_report_v1.json",
    )


@router.get("/source-truth-v8")
async def source_truth_v8() -> dict[str, Any]:
    return _slice(
        "market_class_source_truth_v8_report.json",
        "adapter_health_truth_signal_report_v1.json",
        "settlement_usefulness_signal_report_v1.json",
        "live_score_truth_signal_report_v1.json",
        "replay_score_truth_signal_report_v1.json",
        "no_trade_truth_signal_report_v1.json",
        "source_truth_next_action_v8_report.json",
    )


@router.get("/adapter-sprint")
async def adapter_sprint() -> dict[str, Any]:
    return _slice(
        "adapter_implementation_sprint_queue_v3_report.json",
        "adapter_sprint_candidate_report_v1.json",
        "adapter_sprint_priority_report_v1.json",
        "adapter_sprint_scope_report_v1.json",
        "adapter_sprint_acceptance_gate_report_v1.json",
        "adapter_sprint_risk_guard_report_v1.json",
    )


@router.get("/compounding-v10")
async def compounding_v10() -> dict[str, Any]:
    return _slice(
        "market_class_compounding_control_plane_v10_report.json",
        "settlement_expansion_queue_report_v1.json",
        "keyless_adapter_expansion_queue_v2_report.json",
        "forecast_resolution_queue_report_v1.json",
        "live_scoring_growth_queue_report_v1.json",
        "next_bundle_recommendation_v26_report.json",
    )


@router.get("/scoreboard-v11")
async def scoreboard_v11() -> dict[str, Any]:
    return _slice(
        "domain_market_class_scoreboard_v11_report.json",
        "market_class_observability_scoreboard_report_v1.json",
        "live_scoring_scoreboard_report_v1.json",
        "keyless_adapter_scoreboard_report_v1.json",
        "settlement_expansion_scoreboard_report_v1.json",
    )


@router.get("/runtime-budget")
async def runtime_budget() -> dict[str, Any]:
    return _slice(
        "v26_runtime_budget_report_v1.json",
        "keyless_probe_budget_v2_report.json",
        "settlement_probe_budget_v2_report.json",
        "forecast_resolution_runtime_guard_report_v1.json",
        "dashboard_cache_policy_v8_report.json",
        "report_chain_runtime_profiler_v9_report.json",
    )


@router.get("/safety")
async def safety() -> dict[str, Any]:
    return _slice(
        "no_secret_leak_report_v26.json",
        "no_kalshi_private_key_leak_report_v26.json",
        "no_source_api_key_leak_report_v26.json",
        "no_github_token_leak_report_v26.json",
        "no_llm_secret_leak_report_v26.json",
        "no_direct_order_bypass_report_v26.json",
        "no_direct_cancel_bypass_report_v26.json",
        "no_live_submit_still_disabled_report_v26.json",
        "no_caps_config_modification_report_v26.json",
        "readonly_only_source_activation_report_v26.json",
        "no_unauthorized_source_report_v26.json",
        "no_questionable_odds_scraping_report_v26.json",
        "no_unapproved_source_activation_report_v26.json",
        "no_commercial_source_without_approval_report_v26.json",
        "no_premium_feed_required_global_blocker_report_v26.json",
        "no_fixture_claimed_real_report_v26.json",
        "no_replay_claimed_live_report_v26.json",
        "no_replay_score_claimed_live_report_v26.json",
        "no_proxy_claimed_exchange_native_report_v26.json",
        "no_context_claimed_edge_report_v26.json",
        "no_example_market_canonical_center_report_v26.json",
        "no_unresolved_forecast_scored_report_v26.json",
        "no_outcome_fabrication_report_v26.json",
        "no_github_repo_code_execution_report_v26.json",
        "no_keyless_probe_to_execution_bridge_report_v26.json",
        "no_settlement_probe_to_execution_bridge_report_v26.json",
        "no_forecast_resolution_to_execution_bridge_report_v26.json",
        "no_live_scoring_to_execution_bridge_report_v26.json",
        "no_replay_to_live_selector_to_execution_bridge_report_v26.json",
        "no_source_truth_to_execution_bridge_report_v26.json",
        "no_adapter_sprint_to_execution_bridge_report_v26.json",
        "blunder_separation_recheck_v26.json",
        "dummy_canonical_identity_report_v26.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice("dummy_mission_state_report_v12.json")
