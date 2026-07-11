from __future__ import annotations

from typing import Any

from fastapi import APIRouter

from predator_mesh.v32.reports import V32ReportFactory

router = APIRouter(prefix="/api/v32", tags=["v32"])


def _reports() -> dict[str, dict[str, Any]]:
    return V32ReportFactory(enable_network=False, env={}).build()


def _safe(payload: dict[str, Any]) -> dict[str, Any]:
    payload["live_submit_disabled"] = True
    payload["caps_unchanged"] = True
    payload["execution_bridge_present"] = False
    return payload


def _slice(*names: str) -> dict[str, Any]:
    reports = _reports()
    return _safe({name.removesuffix(".json"): reports[name] for name in names})


@router.get("/mission-state")
async def mission_state() -> dict[str, Any]:
    return _slice("dummy_mission_state_report_v18.json")


@router.get("/source-recovery")
async def source_recovery() -> dict[str, Any]:
    return _slice(
        "v32_source_recovery_controller_v1_report.json",
        "source_recovery_case_v2_report.json",
        "source_recovery_plan_v2_report.json",
        "source_recovery_attempt_v2_report.json",
        "source_recovery_decision_v2_report.json",
        "source_recovery_blocker_v2_report.json",
        "source_recovery_safety_proof_v1_report.json",
    )


@router.get("/gate")
async def gate() -> dict[str, Any]:
    return _slice(
        "operator_gated_probe_run_v2_report.json",
        "probe_gate_operator_intent_v2_report.json",
        "probe_gate_ack_validator_v2_report.json",
        "probe_gate_run_scope_v2_report.json",
        "probe_gate_budget_decision_v2_report.json",
        "probe_gate_run_blocker_v2_report.json",
        "probe_gate_no_execution_proof_v2_report.json",
    )


@router.get("/minimal-probe-pass")
async def minimal_probe_pass() -> dict[str, Any]:
    return _slice(
        "minimal_public_probe_pass_v1_report.json",
        "minimal_probe_task_v1_report.json",
        "minimal_probe_adapter_selection_v1_report.json",
        "minimal_probe_run_result_v1_report.json",
        "minimal_probe_source_family_summary_v1_report.json",
        "minimal_probe_failure_summary_v1_report.json",
        "minimal_probe_safety_summary_v1_report.json",
    )


@router.get("/domain-recovery")
async def domain_recovery() -> dict[str, Any]:
    return _slice(
        "weather_source_recovery_v2_report.json",
        "crypto_source_recovery_v2_report.json",
        "public_event_source_recovery_v2_report.json",
        "kalshi_readonly_source_recovery_v2_report.json",
        "sports_fixture_guard_v3_report.json",
    )


@router.get("/evidence")
async def evidence() -> dict[str, Any]:
    return _slice(
        "live_public_evidence_expansion_v2_report.json",
        "expanded_live_public_evidence_packet_v1_report.json",
        "live_evidence_family_summary_v1_report.json",
        "live_evidence_eligibility_decision_v1_report.json",
        "live_evidence_freshness_decision_v1_report.json",
        "live_evidence_expansion_blocker_v1_report.json",
        "settlement_compatible_evidence_expansion_v2_report.json",
        "settlement_compatible_evidence_candidate_v1_report.json",
        "settlement_evidence_join_decision_v2_report.json",
    )


@router.get("/closure")
async def closure() -> dict[str, Any]:
    return _slice(
        "due_forecast_closure_expansion_v5_report.json",
        "due_forecast_closure_case_v2_report.json",
        "due_forecast_evidence_match_v2_report.json",
        "due_forecast_closure_decision_v2_report.json",
        "due_forecast_closure_ledger_write_v2_report.json",
        "due_forecast_closure_blocker_v2_report.json",
    )


@router.get("/scoring")
async def scoring() -> dict[str, Any]:
    return _slice(
        "live_score_expansion_seed_v3_report.json",
        "live_score_expansion_candidate_v1_report.json",
        "live_score_expansion_decision_v1_report.json",
        "live_score_expansion_metric_v1_report.json",
        "live_score_expansion_ledger_write_v1_report.json",
        "live_score_expansion_blocker_v1_report.json",
        "live_calibration_expansion_v3_report.json",
    )


@router.get("/source-truth")
async def source_truth() -> dict[str, Any]:
    return _slice(
        "probe_cache_replay_separation_v2_report.json",
        "source_truth_recovery_closure_v13_report.json",
        "source_recovery_sprint_queue_v9_report.json",
        "recovery_to_score_compounding_control_plane_v16_report.json",
        "domain_market_class_scoreboard_v17_report.json",
        "dashboard_v32_report_v1.json",
    )


@router.get("/safety")
async def safety() -> dict[str, Any]:
    return _slice(
        "no_secret_leak_report_v32.json",
        "no_kalshi_private_key_leak_report_v32.json",
        "no_source_api_key_leak_report_v32.json",
        "no_github_token_leak_report_v32.json",
        "no_direct_order_bypass_report_v32.json",
        "no_direct_cancel_bypass_report_v32.json",
        "no_live_submit_still_disabled_report_v32.json",
        "no_caps_config_modification_report_v32.json",
        "no_unauthorized_source_report_v32.json",
        "no_questionable_odds_scraping_report_v32.json",
        "no_unapproved_source_activation_report_v32.json",
        "no_commercial_source_without_approval_report_v32.json",
        "no_premium_feed_required_global_blocker_report_v32.json",
        "no_browser_automation_report_v32.json",
        "no_pageagent_report_v32.json",
        "no_dom_extraction_report_v32.json",
        "no_browser_research_lane_report_v32.json",
        "no_mined_repo_clone_report_v32.json",
        "no_mined_repo_import_report_v32.json",
        "no_mined_repo_execution_report_v32.json",
        "no_blind_mined_code_copy_report_v32.json",
        "no_disabled_probe_scored_live_report_v32.json",
        "no_source_recovery_to_execution_bridge_report_v32.json",
        "blunder_separation_recheck_v32.json",
        "dummy_canonical_identity_report_v32.json",
    )
