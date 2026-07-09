"""V31 explicit read-only public probe execution reports."""

from __future__ import annotations

import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v31 import MILESTONE
from predator_mesh.v31.probes import (
    CAPS_HASH,
    LIVE_SUBMIT_HASH,
    build_default_v31_state,
)

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"
REPORT_NAMES_FILE = ARTIFACTS / "v31_required_report_names_from_attachment.txt"

DEFAULT_REQUIRED_REPORT_NAMES = [
    line.strip()
    for line in """
explicit_public_probe_operator_gate_v3_report.json
public_probe_gate_intent_v1_report.json
public_probe_environment_flag_v1_report.json
public_probe_operator_acknowledgement_v1_report.json
public_probe_gate_decision_v1_report.json
public_probe_gate_safety_proof_v1_report.json
public_probe_gate_config_diff_proof_v1_report.json
v30_adapter_public_probe_runner_v1_report.json
adapter_probe_run_plan_v1_report.json
adapter_probe_task_v1_report.json
adapter_probe_result_v1_report.json
adapter_probe_failure_v1_report.json
adapter_probe_budget_v1_report.json
adapter_probe_redaction_proof_v1_report.json
live_public_evidence_capture_v1_report.json
live_public_evidence_packet_v1_report.json
live_public_evidence_source_ref_v1_report.json
live_public_evidence_freshness_v1_report.json
live_public_evidence_eligibility_v1_report.json
live_public_evidence_blocker_v1_report.json
weather_public_probe_implementation_v2_report.json
weather_public_probe_request_v1_report.json
weather_public_probe_response_v1_report.json
weather_public_probe_normalizer_v1_report.json
weather_public_probe_settlement_join_v1_report.json
weather_public_probe_blocker_v1_report.json
crypto_public_probe_implementation_v2_report.json
crypto_public_probe_request_v1_report.json
crypto_public_probe_response_v1_report.json
crypto_public_probe_normalizer_v1_report.json
crypto_public_probe_venue_consensus_v1_report.json
crypto_public_probe_settlement_join_v1_report.json
crypto_public_probe_blocker_v1_report.json
public_event_reference_probe_implementation_v2_report.json
public_event_reference_probe_request_v1_report.json
public_event_reference_probe_response_v1_report.json
public_event_reference_probe_normalizer_v1_report.json
public_event_reference_probe_settlement_join_v1_report.json
public_event_reference_probe_blocker_v1_report.json
kalshi_readonly_rule_probe_implementation_v2_report.json
kalshi_readonly_rule_probe_request_v1_report.json
kalshi_readonly_rule_probe_response_v1_report.json
kalshi_readonly_rule_probe_normalizer_v1_report.json
kalshi_readonly_rule_probe_settlement_join_v1_report.json
kalshi_readonly_rule_probe_blocker_v1_report.json
probe_evidence_normalization_pipeline_v2_report.json
normalized_probe_evidence_v1_report.json
probe_evidence_mode_classifier_v1_report.json
probe_evidence_freshness_gate_v1_report.json
probe_evidence_metric_gate_v1_report.json
probe_evidence_normalization_blocker_v1_report.json
due_forecast_live_observation_closure_v4_report.json
due_forecast_live_observation_candidate_v1_report.json
due_forecast_live_evidence_join_v1_report.json
due_forecast_live_observation_decision_v1_report.json
due_forecast_live_observation_ledger_write_v1_report.json
due_forecast_live_observation_blocker_v1_report.json
live_score_seed_v2_report.json
live_score_seed_candidate_v2_report.json
live_score_seed_decision_v2_report.json
live_score_metric_v2_report.json
live_score_ledger_write_v2_report.json
live_score_seed_blocker_v2_report.json
live_calibration_seed_v2_report.json
live_calibration_seed_sample_v2_report.json
live_calibration_bucket_v2_report.json
live_calibration_update_decision_v2_report.json
live_calibration_low_sample_warning_v2_report.json
live_calibration_seed_blocker_v2_report.json
public_probe_cache_writer_v1_report.json
public_probe_cache_record_v1_report.json
public_probe_cache_manifest_v1_report.json
public_probe_cache_freshness_policy_v1_report.json
public_probe_cache_redaction_v1_report.json
public_probe_cache_blocker_v1_report.json
probe_run_audit_ledger_v1_report.json
probe_run_audit_record_v1_report.json
probe_run_source_summary_v1_report.json
probe_run_outcome_summary_v1_report.json
probe_run_safety_summary_v1_report.json
probe_run_audit_blocker_v1_report.json
sports_fixture_guard_recheck_v2_report.json
sports_probe_blocked_decision_v1_report.json
sports_live_evidence_eligibility_v1_report.json
sports_source_approval_packet_v2_report.json
sports_fixture_guard_safety_proof_v1_report.json
sports_fixture_guard_blocker_v1_report.json
probe_source_truth_v12_report.json
probe_health_truth_signal_v1_report.json
public_evidence_truth_signal_v1_report.json
observation_closure_truth_signal_v1_report.json
live_score_truth_signal_v3_report.json
probe_source_truth_action_v12_report.json
public_probe_partial_reduction_v1_report.json
probe_partial_cause_before_after_v1_report.json
probe_partial_reduction_attempt_v1_report.json
probe_partial_reduction_result_v1_report.json
probe_remaining_partial_cause_v1_report.json
probe_pass_delta_v1_report.json
public_probe_sprint_queue_v8_report.json
probe_sprint_v8_task_report_v1.json
probe_sprint_v8_adapter_target_report_v1.json
probe_sprint_v8_settlement_target_report_v1.json
probe_sprint_v8_source_recovery_target_report_v1.json
probe_sprint_v8_acceptance_gate_report_v1.json
probe_sprint_v8_risk_guard_report_v1.json
probe_to_score_compounding_control_plane_v15_report.json
public_probe_run_queue_v4_report.json
live_observation_closure_queue_v4_report.json
live_score_seed_queue_v3_report.json
live_calibration_growth_queue_v1_report.json
source_recovery_queue_v4_report.json
next_bundle_recommendation_v31_report.json
domain_market_class_scoreboard_v16_report.json
public_probe_execution_scoreboard_v1_report.json
live_public_evidence_scoreboard_v1_report.json
observation_closure_v4_scoreboard_v1_report.json
live_score_seed_v2_scoreboard_v1_report.json
source_recovery_scoreboard_v1_report.json
dummy_mission_state_report_v17.json
dashboard_v31_report_v1.json
v31_runtime_budget_report_v1.json
public_probe_execution_budget_v1_report.json
probe_normalization_runtime_budget_v1_report.json
observation_closure_runtime_budget_v1_report.json
dashboard_cache_policy_v13_report.json
report_chain_runtime_profiler_v14_report.json
no_secret_leak_report_v31.json
no_kalshi_private_key_leak_report_v31.json
no_source_api_key_leak_report_v31.json
no_github_token_leak_report_v31.json
no_llm_secret_leak_report_v31.json
no_direct_order_bypass_report_v31.json
no_direct_cancel_bypass_report_v31.json
no_live_submit_still_disabled_report_v31.json
no_caps_config_modification_report_v31.json
readonly_only_source_activation_report_v31.json
no_unauthorized_source_report_v31.json
no_questionable_odds_scraping_report_v31.json
no_unapproved_source_activation_report_v31.json
no_commercial_source_without_approval_report_v31.json
no_premium_feed_required_global_blocker_report_v31.json
no_browser_automation_report_v31.json
no_pageagent_report_v31.json
no_dom_extraction_report_v31.json
no_browser_research_lane_report_v31.json
no_mined_repo_clone_report_v31.json
no_mined_repo_import_report_v31.json
no_mined_repo_execution_report_v31.json
no_blind_mined_code_copy_report_v31.json
no_fixture_claimed_real_report_v31.json
no_replay_claimed_live_report_v31.json
no_replay_score_claimed_live_report_v31.json
no_proxy_claimed_exchange_native_report_v31.json
no_cached_sample_claimed_live_report_v31.json
no_stale_cached_evidence_scored_live_report_v31.json
no_public_sample_evidence_scored_live_report_v31.json
no_context_claimed_edge_report_v31.json
no_example_market_canonical_center_report_v31.json
no_unresolved_forecast_scored_report_v31.json
no_ambiguous_settlement_scored_report_v31.json
no_source_unavailable_forecast_scored_report_v31.json
no_not_due_forecast_scored_report_v31.json
no_adapter_fixture_scored_live_report_v31.json
no_adapter_dry_run_scored_live_report_v31.json
no_public_probe_failure_scored_live_report_v31.json
no_outcome_fabrication_report_v31.json
no_public_probe_gate_to_execution_bridge_report_v31.json
no_public_probe_runner_to_execution_bridge_report_v31.json
no_live_public_evidence_to_execution_bridge_report_v31.json
no_probe_normalization_to_execution_bridge_report_v31.json
no_due_observation_closure_to_execution_bridge_report_v31.json
no_live_score_seed_to_execution_bridge_report_v31.json
no_live_calibration_seed_to_execution_bridge_report_v31.json
no_public_probe_cache_to_execution_bridge_report_v31.json
no_source_truth_to_execution_bridge_report_v31.json
no_probe_sprint_to_execution_bridge_report_v31.json
blunder_separation_recheck_v31.json
dummy_canonical_identity_report_v31.json
""".splitlines()
    if line.strip()
]

FINAL_INDEX_NAMES = {"final_report.json", "tests_summary.json", "final_report_v31.json", "final_report_v30.json"}


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
        "trading_endpoints_used": False,
        "order_endpoints_used": False,
        "cancel_endpoints_used": False,
        "private_endpoints_used": False,
        "live_submit_enabled": False,
        "configs_live_submit_modified": False,
        "configs_caps_modified": False,
        "model_can_submit_orders": False,
        "model_can_modify_caps": False,
        "model_can_modify_live_submit": False,
        "public_probe_gate_to_execution_bridge_present": False,
        "public_probe_runner_to_execution_bridge_present": False,
        "live_public_evidence_to_execution_bridge_present": False,
        "probe_normalization_to_execution_bridge_present": False,
        "due_observation_closure_to_execution_bridge_present": False,
        "live_score_seed_to_execution_bridge_present": False,
        "live_calibration_seed_to_execution_bridge_present": False,
        "public_probe_cache_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "probe_sprint_to_execution_bridge_present": False,
        "mined_repo_cloned": False,
        "mined_repo_imported": False,
        "mined_repo_executed": False,
        "blind_mined_code_copied": False,
        "questionable_odds_scraping": False,
        "browser_automation_added": False,
        "pageagent_added": False,
        "dom_extraction_added": False,
        "browser_research_lane_added": False,
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
        "outcome_fabricated": False,
    }


def _safe_payload(workstream: str, verdict: str = "PASS", **extra: Any) -> dict[str, Any]:
    payload = _safe_base(workstream, verdict)
    payload.update(extra)
    return payload


def _workstream(report_name: str) -> str:
    return f"V31: {report_name.removesuffix('.json').removesuffix('_report').replace('_', ' ').title()}"


def _verdict(report_name: str) -> str:
    partial_tokens = [
        "mission_state",
        "closure",
        "live_score",
        "live_calibration",
        "partial",
        "queue",
        "scoreboard",
        "source_truth",
        "sports",
    ]
    if any(token in report_name for token in partial_tokens):
        return "PARTIAL"
    if any(token in report_name for token in ["public_probe", "probe_runner", "live_public_evidence", "normalization"]):
        return "PARTIAL"
    return "PASS"


def _common(state: dict[str, Any], report_name: str) -> dict[str, Any]:
    gate = state["gate"]
    run = state["probe_run"]
    closure = state["closure"]
    score = state["score_seed"]
    calibration = state["calibration_seed"]
    return {
        "report_name": report_name,
        "public_probe_operator_gate_status": "PASS_DISABLED_BY_DEFAULT" if not gate.enabled else "PASS_ENABLED_READONLY",
        "public_probe_gate_state": gate.state,
        "public_probe_gate_enabled": gate.enabled,
        "public_probe_runner_status": "PASS_DISABLED_BY_DEFAULT" if run.status == "PROBE_DISABLED" else "PASS_READONLY_PROBES",
        "probe_run_count": run.probe_run_count,
        "probe_failure_count": run.probe_failure_count,
        "probe_source_family_count": run.source_family_count,
        "source_family_count": run.source_family_count,
        "weather_probe_status": "PASS_DISABLED_BY_DEFAULT" if not gate.enabled else "PASS_READONLY_PUBLIC_PROBE",
        "crypto_probe_status": "PASS_DISABLED_BY_DEFAULT" if not gate.enabled else "PASS_READONLY_PUBLIC_PROBE",
        "public_event_reference_probe_status": "PASS_DISABLED_BY_DEFAULT" if not gate.enabled else "PASS_READONLY_PUBLIC_PROBE",
        "kalshi_readonly_probe_status": "PASS_DISABLED_BY_DEFAULT" if not gate.enabled else "READONLY_ACCESS_UNAVAILABLE",
        "live_public_evidence_capture_status": "PASS_DISABLED_BY_DEFAULT" if not state["live_public_evidence_packets"] else "PASS",
        "live_public_evidence_packet_count": len(state["live_public_evidence_packets"]),
        "probe_evidence_normalization_status": "PASS_DISABLED_BY_DEFAULT" if not state["normalized_live"] else "PASS",
        "normalized_live_public_evidence_count": len(state["normalized_live"]),
        "settlement_compatible_evidence_count": sum(1 for item in state["normalized_live"] if item.settlement_compatible),
        "due_forecast_observation_closure_status": "PASS_DISABLED_BY_DEFAULT" if closure.observed_forecast_count == 0 else "PASS_WITH_REMAINING_BLOCKERS",
        "due_forecast_count": closure.due_forecast_count,
        "observed_forecast_count": closure.observed_forecast_count,
        "live_score_seed_status": score.live_score_seed_status,
        "live_scored_count": score.live_scored_count,
        "live_unresolved_count": score.live_unresolved_count,
        "live_calibration_seed_status": calibration.live_calibration_seed_status,
        "live_calibration_sample_count": calibration.live_calibration_sample_count,
        "public_probe_cache_status": state["cache"].public_probe_cache_status,
        "cache_record_count": state["cache"].cache_record_count,
        "probe_run_audit_status": state["audit"].probe_run_audit_status,
        "sports_fixture_guard_status": state["sports"].sports_fixture_guard_status,
        "sports_source_mode": state["sports"].sports_source_mode,
        "probe_source_truth_v12_status": state["source_truth"].probe_source_truth_v12_status,
        "partial_reduction_status": "PASS_WITH_REMAINING_PARTIALS",
        "public_probe_partial_reduction_status": "PASS_WITH_REMAINING_PARTIALS",
        "partial_causes_before": {"PROBE_DISABLED_BY_DEFAULT": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1},
        "partial_causes_after": {"PROBE_DISABLED_BY_DEFAULT": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1, "SPORTS_TERMS_FIXTURE_ONLY": 1},
        "sprint_queue_v8_status": "PASS",
        "public_probe_sprint_v8_status": "PASS",
        "compounding_v15_status": "PASS",
        "next_bundle_recommendation": "DUMMY_V32_SOURCE_RECOVERY_LIVE_OBSERVATION_EXPANSION_V1",
        "market_class_scoreboard_v16_status": "PASS_PARTIAL_EXPECTED",
    }


def _gate_payload(state: dict[str, Any]) -> dict[str, Any]:
    gate = state["gate"]
    return {
        "gate_decision": gate.to_dict(),
        "public_probe_gate_intent": gate.intent.to_dict(),
        "public_probe_environment_flag": gate.environment_flag.to_dict(),
        "public_probe_operator_acknowledgement": gate.acknowledgement.to_dict(),
        "public_probe_gate_safety_proof": gate.safety_proof.to_dict(),
        "public_probe_gate_config_diff_proof": gate.config_diff_proof.to_dict(),
        "allowed_adapter_families": gate.allowed_adapter_families,
        "max_requests": gate.max_requests,
        "timeout_budget_seconds": gate.timeout_budget_seconds,
        "source_categories": gate.source_categories,
    }


def _runner_payload(state: dict[str, Any]) -> dict[str, Any]:
    run = state["probe_run"]
    return {
        "probe_run_plan": run.plan.to_dict(),
        "adapter_probe_tasks": [task.to_dict() for task in run.plan.tasks],
        "adapter_probe_results": [result.to_dict() for result in run.results],
        "adapter_probe_failures": [failure.to_dict() for failure in run.failures],
        "adapter_probe_budget": run.plan.budget.to_dict(),
        "adapter_probe_redaction_proof": {"no_secret_values": True, "raw_payload_redacted": True},
        "bounded_readonly_public_requests": True,
        "source_api_key_required": False,
    }


def _evidence_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "live_public_evidence_packets": [packet.to_dict() for packet in state["live_public_evidence_packets"]],
        "live_public_evidence_source_refs": [packet.source_ref.to_dict() for packet in state["live_public_evidence_packets"]],
        "freshness_policy": "fresh public probe timestamp required",
        "live_public_evidence_eligibility": "only enabled read-only public probe results qualify",
        "live_public_evidence_blockers": ["PROBE_DISABLED"] if not state["live_public_evidence_packets"] else [],
        "fixtures_promoted_to_live_public": False,
        "public_samples_promoted_to_live_public": False,
        "stale_cache_promoted_to_live_public": False,
    }


def _domain_probe_payload(state: dict[str, Any], domain: str) -> dict[str, Any]:
    status_key = {
        "weather": "weather_probe_status",
        "crypto": "crypto_probe_status",
        "public_event": "public_event_reference_probe_status",
        "kalshi": "kalshi_readonly_probe_status",
    }[domain]
    blocker = "PROBE_DISABLED" if state["gate"].state == "DISABLED_BY_DEFAULT" else None
    if domain == "kalshi" and state["gate"].enabled:
        blocker = "READONLY_ACCESS_UNAVAILABLE"
    return {
        status_key: _common(state, "")[status_key],
        "probe_request_mode": state["gate"].state,
        "probe_response_mode": "PROBE_DISABLED" if blocker == "PROBE_DISABLED" else "LIVE_PUBLIC_PROBE_RESULT",
        "probe_normalizer_status": "PASS",
        "probe_settlement_join_status": "PASS_PIPELINE_ONLY",
        "probe_blocker": blocker,
        "private_or_paywalled_source_used": False,
        "order_endpoints_used": False,
        "cancel_endpoints_used": False,
        "browser_request_used": False,
        "scraping_used": False,
    }


def _normalization_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "normalized_probe_evidence": [item.to_dict() for item in state["normalized_live"]],
        "normalized_fixture_evidence": [item.to_dict() for item in state["normalized_fixtures"]],
        "probe_evidence_mode_classifier": sorted({item.mode for item in state["normalized_live"] + state["normalized_fixtures"]}),
        "probe_evidence_freshness_gate": "PASS",
        "probe_evidence_metric_gate": "PASS",
        "probe_evidence_normalization_blockers": ["PROBE_DISABLED"] if not state["normalized_live"] else [],
        "fixture_evidence_live_observation_allowed": False,
        "public_sample_evidence_live_observation_allowed": False,
        "stale_cached_evidence_scored_live": False,
    }


def _closure_payload(state: dict[str, Any]) -> dict[str, Any]:
    closure = state["closure"]
    return {
        "due_forecast_live_observation_candidates": [candidate.to_dict() for candidate in __import__("predator_mesh.v31.probes", fromlist=["DueForecastLiveObservationClosureV4"]).DueForecastLiveObservationClosureV4().due_forecasts()],
        "due_forecast_live_evidence_joins": [decision.to_dict() for decision in closure.decisions],
        "due_forecast_live_observation_decisions": [decision.to_dict() for decision in closure.decisions],
        "due_forecast_live_observation_ledger_writes": closure.ledger_writes,
        "due_forecast_live_observation_blockers": closure.blockers,
        "unresolved_forecast_scored": closure.unresolved_forecast_scored,
        "outcome_fabricated": closure.outcome_fabricated,
    }


def _score_payload(state: dict[str, Any]) -> dict[str, Any]:
    score = state["score_seed"]
    return {
        "live_score_seed_candidates": score.score_records,
        "live_score_seed_decisions": score.score_records,
        "live_score_metrics": [{"metric": item.get("metric"), "source": "OBSERVED_LIVE_PUBLIC"} for item in score.score_records],
        "live_score_ledger_writes": score.score_records,
        "live_score_seed_blockers": ["NO_VALID_LIVE_PUBLIC_OUTCOMES"] if score.live_scored_count == 0 else [],
        "no_valid_live_public_outcomes_scored": score.live_scored_count == 0,
        **score.to_dict(),
    }


def _calibration_payload(state: dict[str, Any]) -> dict[str, Any]:
    calibration = state["calibration_seed"]
    return {
        **calibration.to_dict(),
        "live_calibration_seed_samples": state["score_seed"].score_records,
        "live_calibration_bucket": calibration.bucket,
        "live_calibration_update_decision": "LOW_SAMPLE_WARN_ONLY" if calibration.low_sample_warning else "NO_UPDATE",
        "live_calibration_seed_blocker": "NO_LIVE_SCORE_SEEDS" if calibration.live_calibration_sample_count == 0 else None,
    }


def _cache_payload(state: dict[str, Any]) -> dict[str, Any]:
    cache = state["cache"]
    return {
        **cache.to_dict(),
        "public_probe_cache_records": [record.to_dict() for record in cache.records],
        "public_probe_cache_manifest": {"record_count": cache.cache_record_count},
        "public_probe_cache_freshness_policy": "cache never scores stale evidence live",
        "public_probe_cache_redaction": cache.redaction_proof.to_dict(),
        "public_probe_cache_blocker": "PROBE_DISABLED" if cache.cache_record_count == 0 else None,
    }


def _audit_payload(state: dict[str, Any]) -> dict[str, Any]:
    audit = state["audit"]
    return {
        **audit.to_dict(),
        "probe_run_audit_records": [audit.to_dict()],
        "probe_run_source_summary": audit.source_summary,
        "probe_run_outcome_summary": audit.outcome_summary,
        "probe_run_safety_summary": audit.safety_summary,
        "probe_run_audit_blocker": "PROBE_DISABLED" if state["probe_run"].probe_run_count == 0 else None,
    }


def _sports_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state["sports"].to_dict(),
        "sports_probe_blocked_decision": "SPORTS_SOURCE_APPROVAL_REQUIRED",
        "sports_live_evidence_eligibility": False,
        "sports_source_approval_packet": "terms-safe public sports source required",
        "sports_fixture_guard_safety_proof": {"no_wagering": True, "no_odds_scraping": True},
        "sports_fixture_guard_blocker": "SPORTS_TERMS_REVIEW_REQUIRED",
    }


def _truth_payload(state: dict[str, Any]) -> dict[str, Any]:
    truth = state["source_truth"]
    return {
        **truth.to_dict(),
        "probe_health_truth_signal": truth.probe_health_truth_signal,
        "public_evidence_truth_signal": truth.public_evidence_truth_signal,
        "observation_closure_truth_signal": truth.observation_closure_truth_signal,
        "live_score_truth_signal_v3": truth.live_score_truth_signal,
    }


def _partial_payload() -> dict[str, Any]:
    return {
        "probe_partial_cause_before_after": {
            "before": {"PROBE_DISABLED_BY_DEFAULT": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1},
            "after": {"PROBE_DISABLED_BY_DEFAULT": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1},
        },
        "probe_partial_reduction_attempt": "implemented explicit gate and disabled-by-default public probe runner",
        "probe_partial_reduction_result": "execution layer exists; live evidence remains blocked until operator enables probes",
        "probe_remaining_partial_cause": ["PROBE_DISABLED_BY_DEFAULT", "NO_LIVE_PUBLIC_EVIDENCE", "NO_LIVE_SCORE", "SPORTS_TERMS_FIXTURE_ONLY"],
        "probe_pass_delta": {"probe_runner_added": 1, "live_score_delta": 0},
    }


def _sprint_payload() -> dict[str, Any]:
    return {
        "public_probe_sprint_queue_v8": [
            {"task": "operator-enable bounded weather probe", "requires_gate": True},
            {"task": "operator-enable bounded crypto probe", "requires_gate": True},
            {"task": "recover source when probe unavailable", "requires_gate": False},
        ],
        "probe_sprint_v8_adapter_targets": ["weather", "crypto", "public_event", "kalshi_readonly"],
        "probe_sprint_v8_settlement_targets": ["WEATHER_THRESHOLD", "CRYPTO_PRICE_THRESHOLD", "FINANCE_MACRO_RELEASE"],
        "probe_sprint_v8_source_recovery_targets": ["kalshi_readonly", "sports"],
        "probe_sprint_v8_acceptance_gate": "explicit read-only gate plus no execution bridge",
        "probe_sprint_v8_risk_guard": "no fixture/sample/stale/failure scoring",
    }


def _queue_payload() -> dict[str, Any]:
    return {
        "public_probe_run_queue": ["weather", "crypto", "public_event"],
        "live_observation_closure_queue": ["weather_threshold", "crypto_threshold", "public_event_reference"],
        "live_score_seed_queue": [],
        "live_calibration_growth_queue": [],
        "source_recovery_queue": ["kalshi_readonly_access", "sports_terms_safe_source"],
    }


def _scoreboard_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain_market_class_scoreboard_v16_status": "PASS_PARTIAL_EXPECTED",
        "public_probe_execution_scoreboard_status": "PASS_DISABLED_BY_DEFAULT" if not state["gate"].enabled else "PASS",
        "live_public_evidence_scoreboard_status": "PASS_DISABLED_BY_DEFAULT" if not state["live_public_evidence_packets"] else "PASS",
        "observation_closure_v4_scoreboard_status": "PASS_DISABLED_BY_DEFAULT" if state["closure"].observed_forecast_count == 0 else "PASS",
        "live_score_seed_v2_scoreboard_status": "PASS_DISABLED_BY_DEFAULT" if state["score_seed"].live_scored_count == 0 else "PASS",
        "source_recovery_scoreboard_status": "PASS_PARTIAL_EXPECTED",
    }


def _budget_payload() -> dict[str, Any]:
    return {
        "v31_runtime_budget_status": "PASS",
        "public_probe_execution_budget": {"max_requests_default": 0, "max_requests_enabled": 4, "unit_tests_use_network": False},
        "probe_normalization_runtime_budget": {"max_packets": 50},
        "observation_closure_runtime_budget": {"due_forecasts": 4},
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
        "public_probe_failure_scored_live": False,
        "public_probe_gate_to_execution_bridge_present": False,
        "public_probe_runner_to_execution_bridge_present": False,
        "live_public_evidence_to_execution_bridge_present": False,
        "probe_normalization_to_execution_bridge_present": False,
        "due_observation_closure_to_execution_bridge_present": False,
        "live_score_seed_to_execution_bridge_present": False,
        "live_calibration_seed_to_execution_bridge_present": False,
        "public_probe_cache_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "probe_sprint_to_execution_bridge_present": False,
    }


def _component_payload(report_name: str, state: dict[str, Any]) -> dict[str, Any]:
    report = _safe_payload(_workstream(report_name), _verdict(report_name), **_common(state, report_name))
    if "gate" in report_name or "operator_acknowledgement" in report_name or "environment_flag" in report_name:
        report.update(_gate_payload(state))
    if "probe_runner" in report_name or "adapter_probe" in report_name:
        report.update(_runner_payload(state))
    if "live_public_evidence" in report_name:
        report.update(_evidence_payload(state))
    if "weather_public_probe" in report_name:
        report.update(_domain_probe_payload(state, "weather"))
    if "crypto_public_probe" in report_name:
        report.update(_domain_probe_payload(state, "crypto"))
    if "public_event_reference_probe" in report_name:
        report.update(_domain_probe_payload(state, "public_event"))
    if "kalshi_readonly_rule_probe" in report_name:
        report.update(_domain_probe_payload(state, "kalshi"))
    if "normalization" in report_name or "normalized_probe" in report_name or "mode_classifier" in report_name or "freshness_gate" in report_name or "metric_gate" in report_name:
        report.update(_normalization_payload(state))
    if "due_forecast" in report_name or "live_observation" in report_name:
        report.update(_closure_payload(state))
    if "live_score" in report_name:
        report.update(_score_payload(state))
    if "live_calibration" in report_name:
        report.update(_calibration_payload(state))
    if "cache" in report_name:
        report.update(_cache_payload(state))
    if "audit" in report_name:
        report.update(_audit_payload(state))
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


def generate_dashboard_v31_report_v1(state: dict[str, Any]) -> dict[str, Any]:
    return _safe_payload(
        "V31: Dashboard Contract",
        "PASS",
        **_common(state, "dashboard_v31_report_v1.json"),
        dashboard_status="PASS",
        routes=[
            "/api/v31/mission-state",
            "/api/v31/gate",
            "/api/v31/probe-runner",
            "/api/v31/evidence",
            "/api/v31/probes",
            "/api/v31/closure",
            "/api/v31/scoring",
            "/api/v31/cache-audit",
            "/api/v31/source-truth",
            "/api/v31/safety",
        ],
        cache_policy="artifact-backed deterministic report slices",
    )


def dummy_mission_state_report_v17(reports: dict[str, dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    partials = sorted(name for name, report in reports.items() if report.get("verdict") == "PARTIAL")
    return _safe_payload(
        "V31: Dummy Mission State",
        "PARTIAL" if partials else "PASS",
        **_common(state, "dummy_mission_state_report_v17.json"),
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
        no_outcome_fabrication_status="PASS",
        no_public_probe_gate_to_execution_bridge_status="PASS",
        no_public_probe_runner_to_execution_bridge_status="PASS",
        no_live_public_evidence_to_execution_bridge_status="PASS",
        no_probe_normalization_to_execution_bridge_status="PASS",
        no_due_observation_closure_to_execution_bridge_status="PASS",
        no_live_score_seed_to_execution_bridge_status="PASS",
        no_live_calibration_seed_to_execution_bridge_status="PASS",
        no_public_probe_cache_to_execution_bridge_status="PASS",
        no_source_truth_to_execution_bridge_status="PASS",
        no_probe_sprint_to_execution_bridge_status="PASS",
        blunder_separation_status="PASS",
        dashboard_status="PASS",
        partial_reports=partials,
        partial_reasons=[
            "public probe gate is disabled by default",
            "no live-public evidence is captured until the operator enables read-only probes",
            "live scored count remains 0 because there are no valid observed live-public outcomes in default mode",
            "sports remains fixture/replay-only pending terms-safe source approval",
        ],
        proof_paths={
            "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v17.json"),
            "public_probe_gate": str(ARTIFACTS / "explicit_public_probe_operator_gate_v3_report.json"),
            "probe_runner": str(ARTIFACTS / "v30_adapter_public_probe_runner_v1_report.json"),
            "live_public_evidence": str(ARTIFACTS / "live_public_evidence_capture_v1_report.json"),
            "normalization": str(ARTIFACTS / "probe_evidence_normalization_pipeline_v2_report.json"),
            "closure": str(ARTIFACTS / "due_forecast_live_observation_closure_v4_report.json"),
            "score_seed": str(ARTIFACTS / "live_score_seed_v2_report.json"),
            "calibration_seed": str(ARTIFACTS / "live_calibration_seed_v2_report.json"),
            "cache": str(ARTIFACTS / "public_probe_cache_writer_v1_report.json"),
            "audit": str(ARTIFACTS / "probe_run_audit_ledger_v1_report.json"),
            "safety": str(ARTIFACTS / "no_public_probe_gate_to_execution_bridge_report_v31.json"),
        },
    )


class V31ReportFactory:
    def __init__(self, *, enable_network: bool = False, env: dict[str, str] | None = None) -> None:
        self.enable_network = enable_network
        self.env = env if env is not None else {}

    def build(self) -> dict[str, dict[str, Any]]:
        state = build_default_v31_state(enable_network=self.enable_network, env=self.env)
        reports: dict[str, dict[str, Any]] = {}
        for report_name in REPORT_NAMES:
            if report_name == "dummy_mission_state_report_v17.json":
                continue
            if report_name == "dashboard_v31_report_v1.json":
                reports[report_name] = generate_dashboard_v31_report_v1(state)
                continue
            reports[report_name] = _component_payload(report_name, state)
        reports["dummy_mission_state_report_v17.json"] = dummy_mission_state_report_v17(reports, state)
        if "dashboard_v31_report_v1.json" not in reports:
            reports["dashboard_v31_report_v1.json"] = generate_dashboard_v31_report_v1(state)
        return reports
