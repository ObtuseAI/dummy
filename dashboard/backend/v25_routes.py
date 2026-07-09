from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v25.reports import V25ReportFactory

router = APIRouter(prefix="/api/v25", tags=["v25"])


def _reports() -> dict[str, dict[str, Any]]:
    return V25ReportFactory(enable_network=False).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/market-class-ontology")
async def market_class_ontology() -> dict[str, Any]:
    return _slice(
        "market_class_ontology_v1_report.json",
        "market_class_definition_report_v1.json",
        "market_class_family_report_v1.json",
        "market_class_evidence_need_report_v1.json",
        "market_class_settlement_need_report_v1.json",
        "market_class_readiness_state_report_v1.json",
    )


@router.get("/market-class-registry")
async def market_class_registry() -> dict[str, Any]:
    return _slice(
        "market_class_registry_v1_report.json",
        "market_class_registry_entry_report_v1.json",
        "market_class_activation_mode_report_v1.json",
        "market_class_capability_score_report_v1.json",
        "market_class_blocker_report_v1.json",
    )


@router.get("/evidence-to-market-mapper")
async def evidence_to_market_mapper() -> dict[str, Any]:
    return _slice(
        "generic_evidence_to_market_mapper_v2_report.json",
        "evidence_market_class_link_report_v1.json",
        "evidence_market_class_confidence_report_v1.json",
        "evidence_market_class_blocker_report_v1.json",
        "evidence_settlement_dependency_report_v1.json",
        "evidence_forecast_eligibility_report_v1.json",
    )


@router.get("/settlement-mapping")
async def settlement_mapping() -> dict[str, Any]:
    return _slice(
        "settlement_mapping_engine_v2_report.json",
        "settlement_rule_template_report_v1.json",
        "settlement_source_candidate_report_v1.json",
        "settlement_observation_plan_report_v1.json",
        "settlement_ambiguity_score_report_v1.json",
        "settlement_blocker_report_v1.json",
    )


@router.get("/forecast-cadence")
async def forecast_cadence() -> dict[str, Any]:
    return _slice(
        "market_class_forecast_cadence_engine_v1_report.json",
        "market_class_forecast_cycle_report_v1.json",
        "forecast_cadence_candidate_report_v1.json",
        "forecast_cadence_decision_report_v1.json",
        "forecast_cadence_budget_report_v1.json",
        "forecast_cadence_backpressure_report_v1.json",
    )


@router.get("/no-trade-quality")
async def no_trade_quality() -> dict[str, Any]:
    return _slice(
        "generic_no_trade_quality_engine_v1_report.json",
        "no_trade_quality_record_report_v1.json",
        "no_trade_blocker_quality_report_v1.json",
        "no_trade_opportunity_cost_proxy_report_v1.json",
        "no_trade_correctness_pending_report_v1.json",
        "no_trade_quality_score_report_v1.json",
    )


@router.get("/live-observer-loop")
async def live_observer_loop() -> dict[str, Any]:
    return _slice(
        "live_observer_loop_v2_report.json",
        "observer_loop_cycle_report_v1.json",
        "observer_due_check_report_v1.json",
        "observer_resolution_attempt_report_v1.json",
        "observer_resolution_state_report_v1.json",
        "observer_loop_backpressure_report_v1.json",
    )


@router.get("/market-class-scoring")
async def market_class_scoring() -> dict[str, Any]:
    return _slice(
        "market_class_scoring_engine_v1_report.json",
        "market_class_score_candidate_report_v1.json",
        "market_class_score_result_report_v1.json",
        "market_class_score_bucket_report_v1.json",
        "market_class_score_blocker_report_v1.json",
        "market_class_score_integrity_proof_report_v1.json",
    )


@router.get("/replay-factory")
async def replay_factory() -> dict[str, Any]:
    return _slice(
        "market_class_replay_factory_v1_report.json",
        "market_class_replay_case_report_v1.json",
        "replay_case_source_plan_report_v1.json",
        "replay_case_forecast_policy_report_v1.json",
        "replay_case_outcome_policy_report_v1.json",
        "replay_case_integrity_proof_report_v1.json",
    )


@router.get("/calibration-v5")
async def calibration_v5() -> dict[str, Any]:
    return _slice(
        "market_class_calibration_engine_v5_report.json",
        "market_class_calibration_lane_report_v1.json",
        "market_class_calibration_bucket_report_v1.json",
        "market_class_calibration_update_report_v1.json",
        "market_class_calibration_readiness_report_v1.json",
        "market_class_calibration_overclaim_guard_report_v1.json",
    )


@router.get("/source-truth-v7")
async def source_truth_v7() -> dict[str, Any]:
    return _slice(
        "source_truth_engine_v7_report.json",
        "source_market_class_truth_report_v1.json",
        "source_evidence_role_truth_report_v1.json",
        "source_no_trade_truth_report_v1.json",
        "source_replay_truth_report_v1.json",
        "source_live_truth_report_v1.json",
        "source_truth_action_recommendation_report_v1.json",
    )


@router.get("/approved-market-class-discovery")
async def approved_market_class_discovery() -> dict[str, Any]:
    return _slice(
        "approved_market_class_discovery_v1_report.json",
        "approved_market_candidate_report_v1.json",
        "market_discovery_source_report_v1.json",
        "market_discovery_legality_gate_report_v1.json",
        "market_discovery_readiness_report_v1.json",
        "market_discovery_blocker_report_v1.json",
    )


@router.get("/source-stack-builder")
async def source_stack_builder() -> dict[str, Any]:
    return _slice(
        "generic_source_stack_builder_v1_report.json",
        "market_class_source_stack_report_v1.json",
        "source_stack_evidence_role_report_v1.json",
        "source_stack_sufficiency_report_v1.json",
        "source_stack_optional_upgrade_report_v1.json",
        "source_stack_no_trade_gate_report_v1.json",
    )


@router.get("/forecast-ledger")
async def forecast_ledger() -> dict[str, Any]:
    return _slice(
        "market_class_forecast_ledger_v1_report.json",
        "market_class_forecast_record_report_v1.json",
        "market_class_no_trade_record_report_v1.json",
        "market_class_observer_record_report_v1.json",
        "market_class_ledger_integrity_check_report_v1.json",
    )


@router.get("/adapter-acceleration")
async def adapter_acceleration() -> dict[str, Any]:
    return _slice(
        "open_source_adapter_acceleration_v2_report.json",
        "adapter_acceleration_candidate_report_v1.json",
        "adapter_acceleration_priority_report_v1.json",
        "adapter_implementation_bundle_plan_report_v1.json",
        "adapter_risk_control_plan_report_v1.json",
        "adapter_validation_plan_report_v1.json",
    )


@router.get("/compounding-v9")
async def compounding_v9() -> dict[str, Any]:
    return _slice(
        "market_class_compounding_control_plane_v9_report.json",
        "market_class_improvement_queue_report_v1.json",
        "source_stack_improvement_queue_report_v1.json",
        "forecast_cadence_improvement_queue_report_v1.json",
        "observer_loop_improvement_queue_report_v1.json",
        "calibration_improvement_queue_report_v1.json",
        "next_bundle_recommendation_v25_report.json",
    )


@router.get("/scoreboard-v10")
async def scoreboard_v10() -> dict[str, Any]:
    return _slice(
        "domain_market_class_scoreboard_v10_report.json",
        "market_class_status_matrix_report_v1.json",
        "forecast_cadence_scoreboard_v1.json",
        "observer_loop_scoreboard_v1.json",
        "calibration_source_truth_scoreboard_v1.json",
    )


@router.get("/runtime-budget")
async def runtime_budget() -> dict[str, Any]:
    return _slice(
        "v25_runtime_budget_report_v1.json",
        "market_class_cadence_budget_report_v1.json",
        "observer_loop_budget_v2_report.json",
        "replay_factory_runtime_guard_report_v1.json",
        "dashboard_cache_policy_v7_report.json",
        "report_chain_runtime_profiler_v8_report.json",
    )


@router.get("/safety")
async def safety() -> dict[str, Any]:
    return _slice(
        "no_secret_leak_report_v25.json",
        "no_kalshi_private_key_leak_report_v25.json",
        "no_source_api_key_leak_report_v25.json",
        "no_github_token_leak_report_v25.json",
        "no_llm_secret_leak_report_v25.json",
        "no_direct_order_bypass_report_v25.json",
        "no_direct_cancel_bypass_report_v25.json",
        "no_live_submit_still_disabled_report_v25.json",
        "no_caps_config_modification_report_v25.json",
        "readonly_only_source_activation_report_v25.json",
        "no_unauthorized_source_report_v25.json",
        "no_questionable_odds_scraping_report_v25.json",
        "no_unapproved_source_activation_report_v25.json",
        "no_commercial_source_without_approval_report_v25.json",
        "no_premium_feed_required_global_blocker_report_v25.json",
        "no_fixture_claimed_real_report_v25.json",
        "no_replay_claimed_live_report_v25.json",
        "no_replay_score_claimed_live_report_v25.json",
        "no_proxy_claimed_exchange_native_report_v25.json",
        "no_context_claimed_edge_report_v25.json",
        "no_example_market_canonical_center_report_v25.json",
        "no_outcome_fabrication_report_v25.json",
        "no_github_repo_code_execution_report_v25.json",
        "no_forecast_cadence_to_execution_bridge_report_v25.json",
        "no_observer_loop_to_execution_bridge_report_v25.json",
        "no_market_class_scoring_to_execution_bridge_report_v25.json",
        "no_calibration_to_execution_bridge_report_v25.json",
        "no_source_truth_to_execution_bridge_report_v25.json",
        "no_adapter_acceleration_to_execution_bridge_report_v25.json",
        "blunder_separation_recheck_v25.json",
        "dummy_canonical_identity_report_v25.json",
    )


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice("dummy_mission_state_report_v11.json")
