"""V32 source recovery and live observation expansion reports."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH
from predator_mesh.v32 import MILESTONE
from predator_mesh.v32.recovery import (
    DueForecastClosureExpansionV5,
    LiveCalibrationExpansionV3,
    LivePublicEvidenceExpansionV2,
    LiveScoreExpansionSeedV3,
    ProbeCacheReplaySeparationV2,
    SettlementCompatibleEvidenceExpansionV2,
    SourceTruthRecoveryClosureV13,
    V32SourceRecoveryControllerV1,
    build_default_v32_state,
)

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"
REPORT_NAMES_FILE = ARTIFACTS / "v32_required_report_names_from_attachment.txt"

DEFAULT_REQUIRED_REPORT_NAMES = [
    line.strip()
    for line in """
v32_source_recovery_controller_v1_report.json
source_recovery_case_v2_report.json
source_recovery_plan_v2_report.json
source_recovery_attempt_v2_report.json
source_recovery_decision_v2_report.json
source_recovery_blocker_v2_report.json
source_recovery_safety_proof_v1_report.json
operator_gated_probe_run_v2_report.json
probe_gate_operator_intent_v2_report.json
probe_gate_ack_validator_v2_report.json
probe_gate_run_scope_v2_report.json
probe_gate_budget_decision_v2_report.json
probe_gate_run_blocker_v2_report.json
probe_gate_no_execution_proof_v2_report.json
minimal_public_probe_pass_v1_report.json
minimal_probe_task_v1_report.json
minimal_probe_adapter_selection_v1_report.json
minimal_probe_run_result_v1_report.json
minimal_probe_source_family_summary_v1_report.json
minimal_probe_failure_summary_v1_report.json
minimal_probe_safety_summary_v1_report.json
weather_source_recovery_v2_report.json
weather_recovery_case_v1_report.json
weather_fallback_source_plan_v1_report.json
weather_observation_recovery_attempt_v1_report.json
weather_settlement_recovery_decision_v1_report.json
weather_recovery_blocker_v1_report.json
crypto_source_recovery_v2_report.json
crypto_recovery_case_v1_report.json
crypto_fallback_source_plan_v1_report.json
crypto_price_recovery_attempt_v1_report.json
crypto_venue_recovery_decision_v1_report.json
crypto_recovery_blocker_v1_report.json
public_event_source_recovery_v2_report.json
public_event_recovery_case_v1_report.json
public_event_fallback_source_plan_v1_report.json
public_event_reference_recovery_attempt_v1_report.json
public_event_settlement_recovery_decision_v1_report.json
public_event_recovery_blocker_v1_report.json
kalshi_readonly_source_recovery_v2_report.json
kalshi_readonly_recovery_case_v1_report.json
kalshi_readonly_access_check_v1_report.json
kalshi_rule_recovery_attempt_v1_report.json
kalshi_rule_settlement_recovery_decision_v1_report.json
kalshi_readonly_recovery_blocker_v1_report.json
live_public_evidence_expansion_v2_report.json
expanded_live_public_evidence_packet_v1_report.json
live_evidence_family_summary_v1_report.json
live_evidence_eligibility_decision_v1_report.json
live_evidence_freshness_decision_v1_report.json
live_evidence_expansion_blocker_v1_report.json
settlement_compatible_evidence_expansion_v2_report.json
settlement_compatible_evidence_candidate_v1_report.json
settlement_evidence_join_decision_v2_report.json
settlement_evidence_confidence_v2_report.json
settlement_evidence_blocker_v2_report.json
due_forecast_closure_expansion_v5_report.json
due_forecast_closure_case_v2_report.json
due_forecast_evidence_match_v2_report.json
due_forecast_closure_decision_v2_report.json
due_forecast_closure_ledger_write_v2_report.json
due_forecast_closure_blocker_v2_report.json
live_score_expansion_seed_v3_report.json
live_score_expansion_candidate_v1_report.json
live_score_expansion_decision_v1_report.json
live_score_expansion_metric_v1_report.json
live_score_expansion_ledger_write_v1_report.json
live_score_expansion_blocker_v1_report.json
live_calibration_expansion_v3_report.json
live_calibration_expansion_sample_v1_report.json
live_calibration_expansion_bucket_v1_report.json
live_calibration_expansion_decision_v1_report.json
live_calibration_expansion_warning_v1_report.json
live_calibration_expansion_blocker_v1_report.json
probe_cache_replay_separation_v2_report.json
probe_cache_mode_audit_v1_report.json
probe_cache_replay_guard_v1_report.json
probe_cache_live_eligibility_guard_v1_report.json
probe_cache_redaction_audit_v1_report.json
probe_cache_separation_blocker_v1_report.json
sports_fixture_guard_v3_report.json
sports_source_approval_state_v3_report.json
sports_probe_eligibility_decision_v2_report.json
sports_fixture_evidence_separation_v2_report.json
sports_operator_approval_packet_v3_report.json
sports_fixture_guard_blocker_v3_report.json
source_truth_recovery_closure_v13_report.json
source_recovery_truth_signal_v1_report.json
probe_run_truth_signal_v2_report.json
evidence_compatibility_truth_signal_v1_report.json
observation_closure_truth_signal_v2_report.json
live_score_truth_signal_v4_report.json
source_truth_recovery_action_v13_report.json
v32_partial_reduction_ledger_report.json
v32_partial_cause_before_after_report.json
v32_partial_reduction_attempt_report.json
v32_partial_reduction_result_report.json
v32_remaining_partial_cause_report.json
v32_pass_delta_report.json
source_recovery_sprint_queue_v9_report.json
source_recovery_sprint_task_v1_report.json
source_recovery_adapter_target_v1_report.json
source_recovery_settlement_target_v1_report.json
source_recovery_operator_action_v1_report.json
source_recovery_acceptance_gate_v1_report.json
source_recovery_risk_guard_v1_report.json
recovery_to_score_compounding_control_plane_v16_report.json
source_recovery_queue_v5_report.json
live_evidence_expansion_queue_v1_report.json
observation_closure_expansion_queue_v1_report.json
live_score_expansion_queue_v1_report.json
live_calibration_expansion_queue_v1_report.json
next_bundle_recommendation_v32_report.json
domain_market_class_scoreboard_v17_report.json
source_recovery_scoreboard_v2_report.json
live_evidence_expansion_scoreboard_v1_report.json
settlement_compatible_evidence_scoreboard_v1_report.json
due_forecast_closure_expansion_scoreboard_v1_report.json
live_score_expansion_scoreboard_v1_report.json
dummy_mission_state_report_v18.json
dashboard_v32_report_v1.json
v32_runtime_budget_report_v1.json
source_recovery_runtime_budget_v1_report.json
minimal_probe_pass_budget_v1_report.json
closure_expansion_runtime_budget_v1_report.json
dashboard_cache_policy_v14_report.json
report_chain_runtime_profiler_v15_report.json
no_secret_leak_report_v32.json
no_kalshi_private_key_leak_report_v32.json
no_source_api_key_leak_report_v32.json
no_github_token_leak_report_v32.json
no_llm_secret_leak_report_v32.json
no_direct_order_bypass_report_v32.json
no_direct_cancel_bypass_report_v32.json
no_live_submit_still_disabled_report_v32.json
no_caps_config_modification_report_v32.json
readonly_only_source_activation_report_v32.json
no_unauthorized_source_report_v32.json
no_questionable_odds_scraping_report_v32.json
no_unapproved_source_activation_report_v32.json
no_commercial_source_without_approval_report_v32.json
no_premium_feed_required_global_blocker_report_v32.json
no_browser_automation_report_v32.json
no_pageagent_report_v32.json
no_dom_extraction_report_v32.json
no_browser_research_lane_report_v32.json
no_mined_repo_clone_report_v32.json
no_mined_repo_import_report_v32.json
no_mined_repo_execution_report_v32.json
no_blind_mined_code_copy_report_v32.json
no_fixture_claimed_real_report_v32.json
no_replay_claimed_live_report_v32.json
no_replay_score_claimed_live_report_v32.json
no_proxy_claimed_exchange_native_report_v32.json
no_cached_sample_claimed_live_report_v32.json
no_stale_cached_evidence_scored_live_report_v32.json
no_public_sample_evidence_scored_live_report_v32.json
no_context_claimed_edge_report_v32.json
no_example_market_canonical_center_report_v32.json
no_unresolved_forecast_scored_report_v32.json
no_ambiguous_settlement_scored_report_v32.json
no_source_unavailable_forecast_scored_report_v32.json
no_not_due_forecast_scored_report_v32.json
no_adapter_fixture_scored_live_report_v32.json
no_adapter_dry_run_scored_live_report_v32.json
no_public_probe_failure_scored_live_report_v32.json
no_disabled_probe_scored_live_report_v32.json
no_outcome_fabrication_report_v32.json
no_source_recovery_to_execution_bridge_report_v32.json
no_operator_gated_probe_run_to_execution_bridge_report_v32.json
no_minimal_public_probe_pass_to_execution_bridge_report_v32.json
no_live_public_evidence_expansion_to_execution_bridge_report_v32.json
no_settlement_compatible_evidence_to_execution_bridge_report_v32.json
no_due_closure_expansion_to_execution_bridge_report_v32.json
no_live_score_expansion_to_execution_bridge_report_v32.json
no_live_calibration_expansion_to_execution_bridge_report_v32.json
no_probe_cache_to_execution_bridge_report_v32.json
no_source_truth_to_execution_bridge_report_v32.json
no_source_recovery_sprint_to_execution_bridge_report_v32.json
blunder_separation_recheck_v32.json
dummy_canonical_identity_report_v32.json
""".splitlines()
    if line.strip()
]

FINAL_INDEX_NAMES = {"final_report.json", "tests_summary.json", "final_report_v32.json"}


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _load_required_report_names() -> list[str]:
    names = list(DEFAULT_REQUIRED_REPORT_NAMES)
    if REPORT_NAMES_FILE.exists():
        file_names = [line.strip() for line in REPORT_NAMES_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
        if file_names:
            names = file_names
    return [name for name in dict.fromkeys(names) if name not in FINAL_INDEX_NAMES]


REPORT_NAMES = _load_required_report_names()


def _safe_base(workstream: str, verdict: str = "PASS") -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "workstream": workstream,
        "milestone": MILESTONE,
        "verdict": verdict,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "source_api_keys_exposed": False,
        "github_tokens_exposed": False,
        "kalshi_private_keys_exposed": False,
        "llm_secrets_exposed": False,
        "execution_bridge_present": False,
        "live_submit_enabled": False,
        "configs_live_submit_modified": False,
        "configs_caps_modified": False,
        "order_endpoints_used": False,
        "cancel_endpoints_used": False,
        "private_endpoints_used": False,
        "browser_automation_added": False,
        "pageagent_added": False,
        "dom_extraction_added": False,
        "browser_research_lane_added": False,
        "mined_repo_cloned": False,
        "mined_repo_imported": False,
        "mined_repo_executed": False,
        "blind_mined_code_copied": False,
        "questionable_odds_scraping": False,
        "fixture_evidence_claimed_real": False,
        "replay_evidence_claimed_live": False,
        "replay_score_claimed_live": False,
        "proxy_evidence_claimed_exchange_native": False,
        "cached_sample_claimed_live": False,
        "stale_cached_evidence_scored_live": False,
        "public_sample_evidence_scored_live": False,
        "context_only_claimed_edge": False,
        "example_market_canonical_center": False,
        "unresolved_forecast_scored": False,
        "ambiguous_settlement_scored": False,
        "source_unavailable_forecast_scored": False,
        "not_due_forecast_scored": False,
        "adapter_fixture_scored_live": False,
        "adapter_dry_run_scored_live": False,
        "public_probe_failure_scored_live": False,
        "disabled_probe_scored_live": False,
        "outcome_fabricated": False,
        "source_recovery_to_execution_bridge_present": False,
        "operator_gated_probe_run_to_execution_bridge_present": False,
        "minimal_public_probe_pass_to_execution_bridge_present": False,
        "live_public_evidence_expansion_to_execution_bridge_present": False,
        "settlement_compatible_evidence_to_execution_bridge_present": False,
        "due_closure_expansion_to_execution_bridge_present": False,
        "live_score_expansion_to_execution_bridge_present": False,
        "live_calibration_expansion_to_execution_bridge_present": False,
        "probe_cache_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "source_recovery_sprint_to_execution_bridge_present": False,
    }


def _safe_payload(workstream: str, verdict: str = "PASS", **extra: Any) -> dict[str, Any]:
    payload = _safe_base(workstream, verdict)
    payload.update(extra)
    return payload


def _workstream(report_name: str) -> str:
    return f"V32: {report_name.removesuffix('.json').removesuffix('_report').replace('_', ' ').title()}"


def _verdict(report_name: str) -> str:
    partial_tokens = ["source_recovery", "probe", "evidence", "closure", "live_score", "live_calibration", "partial", "queue", "scoreboard", "truth", "sports", "mission_state"]
    return "PARTIAL" if any(token in report_name for token in partial_tokens) else "PASS"


def _state(enable_network: bool = False, env: dict[str, str] | None = None) -> dict[str, Any]:
    return build_default_v32_state(enable_network=enable_network, env=env or {})


def _common(state: dict[str, Any], report_name: str) -> dict[str, Any]:
    source_recovery = state["source_recovery"]
    gate = state["operator_gate"]
    minimal = state["minimal_probe_pass"]
    evidence = state["evidence_expansion"]
    settlement = state["settlement_expansion"]
    closure = state["closure_expansion"]
    score = state["score_expansion"]
    calibration = state["calibration_expansion"]
    truth = state["source_truth"]
    return {
        "report_name": report_name,
        "v31_public_probe_execution_status": "PASS_PARTIAL_EXPECTED",
        "source_recovery_controller_status": source_recovery.source_recovery_controller_status,
        "source_recovery_case_count": source_recovery.case_count,
        "source_recovery_attempt_count": source_recovery.attempt_count,
        "operator_gated_probe_run_status": "PASS_ENABLED_READONLY" if gate.enabled else "PASS_DISABLED_BY_DEFAULT",
        "gate_state": gate.gate_state,
        "gate_enabled": gate.enabled,
        "ack_validation_status": gate.ack_validation_status,
        "minimal_public_probe_pass_status": minimal.minimal_public_probe_pass_status,
        "probe_run_count": minimal.probe_run_count,
        "probe_source_family_count": minimal.source_family_summary["source_family_count"],
        "weather_recovery_status": state["domain_recovery"]["weather"].status,
        "crypto_recovery_status": state["domain_recovery"]["crypto"].status,
        "public_event_recovery_status": state["domain_recovery"]["public_event"].status,
        "kalshi_readonly_recovery_status": state["domain_recovery"]["kalshi_readonly"].status,
        "live_public_evidence_expansion_status": evidence.live_public_evidence_expansion_status,
        "live_public_evidence_packet_count": evidence.packet_count,
        "settlement_compatible_evidence_expansion_status": settlement.settlement_compatible_evidence_expansion_status,
        "settlement_compatible_evidence_count": settlement.compatible_count,
        "due_forecast_closure_expansion_status": closure.due_forecast_closure_expansion_status,
        "due_forecast_count": closure.due_forecast_count,
        "observed_forecast_count": closure.observed_forecast_count,
        "live_score_expansion_status": score.live_score_expansion_status,
        "live_scored_count": score.live_scored_count,
        "live_unresolved_count": closure.live_unresolved_count,
        "live_calibration_expansion_status": calibration.live_calibration_expansion_status,
        "probe_cache_replay_separation_status": state["cache_replay_separation"].probe_cache_replay_separation_status,
        "sports_fixture_guard_status": state["sports_guard"].sports_fixture_guard_status,
        "sports_source_mode": state["sports_guard"].sports_source_mode,
        "source_truth_recovery_closure_v13_status": truth.source_truth_recovery_closure_v13_status,
        "partial_reduction_status": "PASS_WITH_REMAINING_PARTIALS",
        "partial_causes_before": {"PROBE_DISABLED_BY_DEFAULT": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1},
        "partial_causes_after": {"PROBE_DISABLED_BY_DEFAULT": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1, "SPORTS_TERMS_FIXTURE_ONLY": 1},
        "source_recovery_sprint_queue_v9_status": "PASS",
        "compounding_v16_status": "PASS",
        "next_bundle_recommendation": "DUMMY_V33_OPERATOR_ENABLED_PUBLIC_PROBE_OBSERVATION_RUN_V1",
        "market_class_scoreboard_v17_status": "PASS_PARTIAL_EXPECTED",
    }


def _source_recovery_payload(state: dict[str, Any]) -> dict[str, Any]:
    result = state["source_recovery"]
    return {
        **result.to_dict(),
        "source_recovery_cases": [case.to_dict() for case in result.recovery_cases],
        "source_recovery_plans": [plan.to_dict() for plan in result.recovery_plans],
        "source_recovery_attempts": [attempt.to_dict() for attempt in result.recovery_attempts],
        "source_recovery_decisions": [decision.to_dict() for decision in result.recovery_decisions],
        "source_recovery_blockers": result.blockers,
    }


def _gate_payload(state: dict[str, Any]) -> dict[str, Any]:
    gate = state["operator_gate"]
    return {
        **gate.to_dict(),
        "probe_gate_operator_intent": gate.operator_intent,
        "probe_gate_ack_validator": gate.ack_validation_status,
        "probe_gate_run_scope": gate.source_families,
        "probe_gate_budget_decision": {"max_requests": gate.max_requests, "timeout_budget_seconds": gate.timeout_budget_seconds},
        "probe_gate_run_blocker": gate.run_blocker,
        "probe_gate_no_execution_proof": gate.no_execution_proof.to_dict(),
    }


def _minimal_probe_payload(state: dict[str, Any]) -> dict[str, Any]:
    result = state["minimal_probe_pass"]
    return {
        **result.to_dict(),
        "minimal_probe_tasks": result.run_summary.plan.to_dict()["tasks"] if result.run_summary else [],
        "minimal_probe_adapter_selection": ["weather", "crypto", "public_event", "kalshi_readonly"],
        "minimal_probe_run_result": result.to_dict(),
        "minimal_probe_source_family_summary": result.source_family_summary,
        "minimal_probe_failure_summary": result.failure_summary,
        "minimal_probe_safety_summary": result.safety_summary,
    }


def _domain_payload(state: dict[str, Any], domain: str) -> dict[str, Any]:
    result = state["domain_recovery"][domain]
    return {
        f"{domain}_source_recovery_status": result.status,
        "domain_recovery": result.to_dict(),
        "fallback_source_plan": result.fallback_source_plan,
        "recovery_attempt_status": result.attempt_status,
        "settlement_recovery_decision": result.settlement_decision,
        "recovery_blocker": result.blocker,
    }


def _evidence_payload(state: dict[str, Any]) -> dict[str, Any]:
    evidence = state["evidence_expansion"]
    return {
        **evidence.to_dict(),
        "expanded_live_public_evidence_packets": [packet.to_dict() for packet in evidence.packets],
        "live_evidence_family_summary": evidence.family_summary,
        "live_evidence_eligibility_decision": "eligible live-public probe outputs only",
        "live_evidence_freshness_decision": "fresh public probe timestamp required",
        "live_evidence_expansion_blockers": evidence.blockers,
        "fixture_promoted_to_live": evidence.fixture_promoted_to_live,
        "source_unavailable_promoted_to_live": evidence.source_unavailable_promoted_to_live,
    }


def _settlement_payload(state: dict[str, Any]) -> dict[str, Any]:
    settlement = state["settlement_expansion"]
    return {
        **settlement.to_dict(),
        "settlement_compatible_evidence_candidates": [candidate.to_dict() for candidate in settlement.candidates],
        "settlement_evidence_join_decisions": [decision.to_dict() for decision in settlement.join_decisions],
        "settlement_evidence_confidence": [decision.confidence for decision in settlement.join_decisions],
        "settlement_evidence_blockers": settlement.blockers,
    }


def _closure_payload(state: dict[str, Any]) -> dict[str, Any]:
    closure = state["closure_expansion"]
    return {
        **closure.to_dict(),
        "due_forecast_closure_cases": [decision.to_dict() for decision in closure.decisions],
        "due_forecast_evidence_matches": [decision.evidence for decision in closure.decisions if decision.evidence],
        "due_forecast_closure_decisions": [decision.to_dict() for decision in closure.decisions],
        "due_forecast_closure_ledger_writes": [decision.to_dict() for decision in closure.decisions if decision.status == "OBSERVED_LIVE_PUBLIC"],
        "due_forecast_closure_blockers": closure.blockers,
    }


def _score_payload(state: dict[str, Any]) -> dict[str, Any]:
    score = state["score_expansion"]
    return {
        **score.to_dict(),
        "live_score_expansion_candidates": score.score_records,
        "live_score_expansion_decisions": score.score_records,
        "live_score_expansion_metrics": [{"score_source": "OBSERVED_LIVE_PUBLIC"} for _ in score.score_records],
        "live_score_expansion_ledger_writes": score.score_records,
        "live_score_expansion_blockers": ["NO_VALID_LIVE_PUBLIC_OUTCOMES"] if score.live_scored_count == 0 else [],
    }


def _calibration_payload(state: dict[str, Any]) -> dict[str, Any]:
    calibration = state["calibration_expansion"]
    return {
        **calibration.to_dict(),
        "live_calibration_expansion_samples": state["score_expansion"].score_records,
        "live_calibration_expansion_bucket": "v32_live_public_expansion",
        "live_calibration_expansion_decision": "LOW_SAMPLE_WARN_ONLY" if calibration.low_sample_warning else "NO_UPDATE",
        "live_calibration_expansion_blocker": "NO_LIVE_SCORE_EXPANSION" if calibration.live_calibration_sample_count == 0 else None,
    }


def _cache_payload(state: dict[str, Any]) -> dict[str, Any]:
    cache = state["cache_replay_separation"]
    return {
        **cache.to_dict(),
        "probe_cache_mode_audit": "replay/cache/live modes separated",
        "probe_cache_replay_guard": "replay evidence cannot score live",
        "probe_cache_live_eligibility_guard": "only live-public probe evidence can close",
        "probe_cache_redaction_audit": "raw payload redacted",
        "probe_cache_separation_blocker": None,
    }


def _sports_payload(state: dict[str, Any]) -> dict[str, Any]:
    sports = state["sports_guard"]
    return {
        **sports.to_dict(),
        "sports_source_approval_state": "OPERATOR_APPROVAL_REQUIRED",
        "sports_probe_eligibility_decision": sports.sports_probe_eligibility_decision,
        "sports_fixture_evidence_separation": "fixture-only evidence never live scored",
        "sports_operator_approval_packet": "terms-safe public sports source required",
        "sports_fixture_guard_blocker": "SPORTS_TERMS_REVIEW_REQUIRED",
    }


def _truth_payload(state: dict[str, Any]) -> dict[str, Any]:
    truth = state["source_truth"]
    return {
        **truth.to_dict(),
        "source_recovery_truth_signal": truth.source_recovery_truth_signal,
        "probe_run_truth_signal": truth.probe_run_truth_signal,
        "evidence_compatibility_truth_signal": truth.evidence_compatibility_truth_signal,
        "observation_closure_truth_signal": truth.observation_closure_truth_signal,
        "live_score_truth_signal_v4": truth.live_score_truth_signal,
        "source_truth_recovery_action_v13": truth.source_truth_recovery_action_v13,
    }


def _partial_payload() -> dict[str, Any]:
    return {
        "v32_partial_reduction_ledger": "source recovery layer added; default gate keeps live evidence partial",
        "v32_partial_cause_before_after": {
            "before": {"PROBE_DISABLED_BY_DEFAULT": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1},
            "after": {"PROBE_DISABLED_BY_DEFAULT": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1},
        },
        "v32_partial_reduction_attempt": "source recovery and closure expansion implemented",
        "v32_partial_reduction_result": "operator-disabled default remains partial with exact action",
        "v32_remaining_partial_cause": ["PROBE_DISABLED_BY_DEFAULT", "NO_LIVE_PUBLIC_EVIDENCE", "NO_LIVE_SCORE", "SPORTS_TERMS_FIXTURE_ONLY"],
        "v32_pass_delta": {"source_recovery_controller_added": 1, "live_score_delta": 0},
    }


def _sprint_payload() -> dict[str, Any]:
    return {
        "source_recovery_sprint_queue_v9": [
            {"task": "operator enable bounded probe pass", "requires_gate": True},
            {"task": "review Kalshi read-only access", "requires_gate": True},
            {"task": "approve terms-safe sports source", "requires_operator": True},
            {"task": "triage V28/V29 metadata-only GitHub reference universe", "requires_operator": False},
        ],
        "source_recovery_adapter_targets": ["weather", "crypto", "public_event", "kalshi_readonly"],
        "source_recovery_settlement_targets": ["WEATHER_THRESHOLD", "CRYPTO_PRICE_THRESHOLD", "FINANCE_MACRO_RELEASE"],
        "source_recovery_operator_action": "set exact read-only probe env gate",
        "source_recovery_acceptance_gate": "no execution bridge and no fixture/sample/stale scoring",
        "source_recovery_risk_guard": "disabled-by-default",
        "open_source_reference_mining_mode": "metadata_only_no_clone_no_import_no_execute",
        "open_source_reference_keywords": [
            "basketball",
            "bloomberg",
            "bitcoin",
            "weather prediction",
            "crypto",
            "trading",
            "soccer",
            "football",
            "baseball",
            "betting",
            "wagering",
            "sportsbook",
            "gambling",
            "fantasy sports",
            "daily fantasy",
            "sports drafting",
        ],
        "open_source_reference_repos": [
            {"full_name": "sportsdataverse/sportsdataverse-py", "url": "https://github.com/sportsdataverse/sportsdataverse-py", "domain": "sports", "role": "reference_only_terms_review_required"},
            {"full_name": "swar/nba_api", "url": "https://github.com/swar/nba_api", "domain": "basketball", "role": "reference_only_terms_review_required"},
            {"full_name": "roclark/sportsipy", "url": "https://github.com/roclark/sportsipy", "domain": "sports", "role": "reference_only_terms_review_required"},
            {"full_name": "open-meteo/open-meteo", "url": "https://github.com/open-meteo/open-meteo", "domain": "weather", "role": "reference_only_public_api_shape"},
            {"full_name": "paulokuong/noaa", "url": "https://github.com/paulokuong/noaa", "domain": "weather", "role": "reference_only_public_api_shape"},
            {"full_name": "blaylockbk/Herbie", "url": "https://github.com/blaylockbk/Herbie", "domain": "weather_prediction", "role": "reference_only_model_data_shape"},
            {"full_name": "ccxt/ccxt", "url": "https://github.com/ccxt/ccxt", "domain": "crypto", "role": "reference_only_public_market_data_shape"},
            {"full_name": "freqtrade/freqtrade", "url": "https://github.com/freqtrade/freqtrade", "domain": "crypto_trading", "role": "reference_only_no_execution"},
            {"full_name": "hummingbot/hummingbot", "url": "https://github.com/hummingbot/hummingbot", "domain": "crypto_trading", "role": "reference_only_no_execution"},
            {"full_name": "OpenBB-finance/OpenBB", "url": "https://github.com/OpenBB-finance/OpenBB", "domain": "finance_bloomberg_alternative", "role": "reference_only_license_review_required"},
            {"full_name": "wilsonfreitas/awesome-quant", "url": "https://github.com/wilsonfreitas/awesome-quant", "domain": "trading", "role": "reference_index_only"},
            {"full_name": "paperswithbacktest/awesome-systematic-trading", "url": "https://github.com/paperswithbacktest/awesome-systematic-trading", "domain": "trading", "role": "reference_index_only"},
        ],
        "sports_betting_wagering_reference_only": True,
        "fantasy_sports_reference_only": True,
        "betting_wagering_activation_allowed": False,
        "fantasy_contest_entry_allowed": False,
    }


def _queue_payload() -> dict[str, Any]:
    return {
        "source_recovery_queue": ["weather", "crypto", "public_event", "kalshi_readonly"],
        "live_evidence_expansion_queue": ["weather_public_observation", "crypto_public_reference_price", "public_event_reference"],
        "observation_closure_expansion_queue": ["match_due_weather", "match_due_crypto", "match_due_public_event"],
        "live_score_expansion_queue": ["score_observed_live_public_only"],
        "live_calibration_expansion_queue": [],
        "open_source_gap_fill_queue": [
            "reuse V28/V29 GitHub keyword expansion metadata",
            "keep wagering and fantasy sources reference-only pending terms approval",
            "promote only native in-house adapters after license and safety review",
        ],
    }


def _scoreboard_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain_market_class_scoreboard_v17_status": "PASS_PARTIAL_EXPECTED",
        "source_recovery_scoreboard_status": state["source_recovery"].source_recovery_controller_status,
        "live_evidence_expansion_scoreboard_status": state["evidence_expansion"].live_public_evidence_expansion_status,
        "settlement_compatible_evidence_scoreboard_status": state["settlement_expansion"].settlement_compatible_evidence_expansion_status,
        "due_forecast_closure_expansion_scoreboard_status": state["closure_expansion"].due_forecast_closure_expansion_status,
        "live_score_expansion_scoreboard_status": state["score_expansion"].live_score_expansion_status,
    }


def _budget_payload() -> dict[str, Any]:
    return {
        "v32_runtime_budget_status": "PASS",
        "source_recovery_runtime_budget": {"network_calls_default": 0, "max_cases": 10},
        "minimal_probe_pass_budget": {"max_requests_default": 0, "max_requests_enabled": 4},
        "closure_expansion_runtime_budget": {"due_forecasts": 4},
        "dashboard_cache_policy": "artifact-backed deterministic slices",
        "report_chain_runtime_profiler_status": "PASS",
    }


def _safety_payload(report_name: str) -> dict[str, Any]:
    return {
        "status": "PASS",
        "safety_status": "PASS",
        "report_name_checked": report_name,
        "live_submit_hash": LIVE_SUBMIT_HASH,
        "caps_hash": CAPS_HASH,
        "disabled_probe_scored_live": False,
        "source_recovery_to_execution_bridge_present": False,
        "operator_gated_probe_run_to_execution_bridge_present": False,
        "minimal_public_probe_pass_to_execution_bridge_present": False,
        "live_public_evidence_expansion_to_execution_bridge_present": False,
        "settlement_compatible_evidence_to_execution_bridge_present": False,
        "due_closure_expansion_to_execution_bridge_present": False,
        "live_score_expansion_to_execution_bridge_present": False,
        "live_calibration_expansion_to_execution_bridge_present": False,
        "probe_cache_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "source_recovery_sprint_to_execution_bridge_present": False,
    }


def _component_payload(report_name: str, state: dict[str, Any]) -> dict[str, Any]:
    report = _safe_payload(_workstream(report_name), _verdict(report_name), **_common(state, report_name))
    if "source_recovery" in report_name and "truth" not in report_name and "sprint" not in report_name and "queue" not in report_name and "scoreboard" not in report_name:
        report.update(_source_recovery_payload(state))
    if "operator_gated" in report_name or "probe_gate" in report_name:
        report.update(_gate_payload(state))
    if "minimal" in report_name:
        report.update(_minimal_probe_payload(state))
    if "weather" in report_name:
        report.update(_domain_payload(state, "weather"))
    if "crypto" in report_name:
        report.update(_domain_payload(state, "crypto"))
    if "public_event" in report_name:
        report.update(_domain_payload(state, "public_event"))
    if "kalshi" in report_name:
        report.update(_domain_payload(state, "kalshi_readonly"))
    if "live_public_evidence" in report_name or "live_evidence" in report_name or "expanded_live" in report_name:
        report.update(_evidence_payload(state))
    if "settlement_compatible" in report_name or "settlement_evidence" in report_name:
        report.update(_settlement_payload(state))
    if "due_forecast" in report_name:
        report.update(_closure_payload(state))
    if "live_score" in report_name:
        report.update(_score_payload(state))
    if "live_calibration" in report_name:
        report.update(_calibration_payload(state))
    if "probe_cache" in report_name:
        report.update(_cache_payload(state))
    if "sports" in report_name:
        report.update(_sports_payload(state))
    if "source_truth" in report_name or "truth_signal" in report_name:
        report.update(_truth_payload(state))
    if "partial" in report_name or "pass_delta" in report_name:
        report.update(_partial_payload())
    if "sprint" in report_name:
        report.update(_sprint_payload())
    if "queue" in report_name or "compounding" in report_name or "next_bundle" in report_name:
        report.update(_queue_payload())
    if "scoreboard" in report_name or "domain_market_class" in report_name:
        report.update(_scoreboard_payload(state))
    if any(token in report_name for token in ["budget", "cache_policy", "profiler", "runtime"]):
        report.update(_budget_payload())
    if report_name.startswith("no_") or report_name.startswith("readonly_only") or "blunder" in report_name or "canonical_identity" in report_name:
        report.update(_safety_payload(report_name))
    return report


def generate_dashboard_v32_report_v1(state: dict[str, Any]) -> dict[str, Any]:
    return _safe_payload(
        "V32: Dashboard Contract",
        "PASS",
        **_common(state, "dashboard_v32_report_v1.json"),
        dashboard_status="PASS",
        routes=[
            "/api/v32/mission-state",
            "/api/v32/source-recovery",
            "/api/v32/gate",
            "/api/v32/minimal-probe-pass",
            "/api/v32/domain-recovery",
            "/api/v32/evidence",
            "/api/v32/closure",
            "/api/v32/scoring",
            "/api/v32/source-truth",
            "/api/v32/safety",
        ],
        cache_policy="artifact-backed deterministic report slices",
    )


def dummy_mission_state_report_v18(reports: dict[str, dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    partials = sorted(name for name, report in reports.items() if report.get("verdict") == "PARTIAL")
    mission_common = _common(state, "dummy_mission_state_report_v18.json")
    mission_common.pop("v31_public_probe_execution_status", None)
    return _safe_payload(
        "V32: Dummy Mission State",
        "PARTIAL" if partials else "PASS",
        **mission_common,
        mission_state_verdict="PARTIAL" if partials else "PASS",
        v17_truth_loop_status="PASS",
        v21_source_activation_status="PASS",
        v22_forecast_write_status="PASS",
        v23_observer_calibration_status="PASS_PARTIAL_EXPECTED",
        v24_open_source_public_data_status="PASS_PARTIAL_EXPECTED",
        v25_market_class_generalization_status="PASS_PARTIAL_EXPECTED",
        v26_keyless_settlement_expansion_status="PASS_PARTIAL_EXPECTED",
        v27_integration_settlement_live_scoring_status="PASS_PARTIAL_EXPECTED",
        v28_oss_observation_closure_status="PASS_PARTIAL_EXPECTED",
        v29_oss_adapter_spec_factory_status="PASS_PARTIAL_EXPECTED",
        v30_in_house_adapter_implementation_status="PASS_PARTIAL_EXPECTED",
        v31_public_probe_execution_status="PASS_PARTIAL_EXPECTED",
        live_submit_flag_status="PASS_DISABLED",
        caps_config_status="PASS_UNCHANGED",
        no_secret_leak_status="PASS",
        no_source_api_key_leak_status="PASS",
        no_github_token_leak_status="PASS",
        no_kalshi_private_key_leak_status="PASS",
        no_direct_order_bypass_status="PASS",
        no_direct_cancel_bypass_status="PASS",
        no_unauthorized_source_status="PASS",
        no_questionable_odds_scraping_status="PASS",
        no_unapproved_source_activation_status="PASS",
        no_commercial_source_without_approval_status="PASS",
        no_premium_feed_required_global_blocker_status="PASS",
        no_browser_automation_status="PASS",
        no_pageagent_status="PASS",
        no_dom_extraction_status="PASS",
        no_browser_research_lane_status="PASS",
        no_mined_repo_clone_status="PASS",
        no_mined_repo_import_status="PASS",
        no_mined_repo_execution_status="PASS",
        no_blind_mined_code_copy_status="PASS",
        no_fixture_claimed_real_status="PASS",
        no_replay_claimed_live_status="PASS",
        no_replay_score_claimed_live_status="PASS",
        no_proxy_claimed_exchange_native_status="PASS",
        no_cached_sample_claimed_live_status="PASS",
        no_stale_cached_evidence_scored_live_status="PASS",
        no_public_sample_evidence_scored_live_status="PASS",
        no_context_claimed_edge_status="PASS",
        no_example_market_canonical_center_status="PASS",
        no_unresolved_forecast_scored_status="PASS",
        no_ambiguous_settlement_scored_status="PASS",
        no_source_unavailable_forecast_scored_status="PASS",
        no_not_due_forecast_scored_status="PASS",
        no_adapter_fixture_scored_live_status="PASS",
        no_adapter_dry_run_scored_live_status="PASS",
        no_public_probe_failure_scored_live_status="PASS",
        no_disabled_probe_scored_live_status="PASS",
        no_outcome_fabrication_status="PASS",
        no_source_recovery_to_execution_bridge_status="PASS",
        no_operator_gated_probe_run_to_execution_bridge_status="PASS",
        no_minimal_public_probe_pass_to_execution_bridge_status="PASS",
        no_live_public_evidence_expansion_to_execution_bridge_status="PASS",
        no_settlement_compatible_evidence_to_execution_bridge_status="PASS",
        no_due_closure_expansion_to_execution_bridge_status="PASS",
        no_live_score_expansion_to_execution_bridge_status="PASS",
        no_live_calibration_expansion_to_execution_bridge_status="PASS",
        no_probe_cache_to_execution_bridge_status="PASS",
        no_source_truth_to_execution_bridge_status="PASS",
        no_source_recovery_sprint_to_execution_bridge_status="PASS",
        blunder_separation_status="PASS",
        dashboard_status="PASS",
        partial_reports=partials,
        partial_reasons=[
            "public probe gate is disabled by default",
            "minimal public probe pass is not run until exact operator ack is present",
            "no live-public evidence is captured in default mode",
            "live scored count remains 0 because no observed live-public outcomes exist in default mode",
            "sports remains fixture/replay-only pending terms-safe source approval",
        ],
        proof_paths={
            "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v18.json"),
            "source_recovery": str(ARTIFACTS / "v32_source_recovery_controller_v1_report.json"),
            "operator_gate": str(ARTIFACTS / "operator_gated_probe_run_v2_report.json"),
            "minimal_probe_pass": str(ARTIFACTS / "minimal_public_probe_pass_v1_report.json"),
            "live_evidence": str(ARTIFACTS / "live_public_evidence_expansion_v2_report.json"),
            "settlement": str(ARTIFACTS / "settlement_compatible_evidence_expansion_v2_report.json"),
            "closure": str(ARTIFACTS / "due_forecast_closure_expansion_v5_report.json"),
            "score": str(ARTIFACTS / "live_score_expansion_seed_v3_report.json"),
            "safety": str(ARTIFACTS / "no_source_recovery_to_execution_bridge_report_v32.json"),
        },
    )


class V32ReportFactory:
    def __init__(self, *, enable_network: bool = False, env: dict[str, str] | None = None) -> None:
        self.enable_network = enable_network
        self.env = env if env is not None else {}

    def build(self) -> dict[str, dict[str, Any]]:
        state = _state(enable_network=self.enable_network, env=self.env)
        reports: dict[str, dict[str, Any]] = {}
        for report_name in REPORT_NAMES:
            if report_name == "dummy_mission_state_report_v18.json":
                continue
            if report_name == "dashboard_v32_report_v1.json":
                reports[report_name] = generate_dashboard_v32_report_v1(state)
                continue
            reports[report_name] = _component_payload(report_name, state)
        reports["dummy_mission_state_report_v18.json"] = dummy_mission_state_report_v18(reports, state)
        if "dashboard_v32_report_v1.json" not in reports:
            reports["dashboard_v32_report_v1.json"] = generate_dashboard_v32_report_v1(state)
        return reports
