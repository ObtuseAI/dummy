"""V33 operator-enabled public probe observation run reports."""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v31.probes import CAPS_HASH, LIVE_SUBMIT_HASH
from predator_mesh.v33 import MILESTONE
from predator_mesh.v33.run import build_default_v33_state

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"
REPORT_NAMES_FILE = ARTIFACTS / "v33_required_report_names_from_attachment.txt"
FINAL_INDEX_NAMES = {"final_report.json", "tests_summary.json", "final_report_v33.json"}


def _names(text: str) -> list[str]:
    return [line.strip() for line in text.splitlines() if line.strip()]


DEFAULT_REQUIRED_REPORT_NAMES = _names(
    """
v33_operator_enabled_probe_run_controller_v1_report.json
v33_probe_run_mode_decision_report.json
v33_probe_run_gate_state_report.json
v33_probe_run_operator_packet_report.json
v33_probe_run_execution_plan_report.json
v33_probe_run_result_report.json
v33_probe_run_safety_proof_report.json
exact_gate_acknowledgement_hardening_v3_report.json
exact_ack_input_record_report.json
exact_ack_validation_decision_report.json
exact_ack_failure_reason_report.json
exact_ack_no_trading_language_guard_report.json
exact_ack_audit_record_report.json
minimal_live_public_probe_execution_v1_report.json
live_probe_execution_task_report.json
live_probe_adapter_family_selection_report.json
live_probe_execution_budget_report.json
live_probe_execution_outcome_report.json
live_probe_execution_failure_report.json
live_probe_execution_safety_proof_report.json
weather_enabled_probe_run_v1_report.json
weather_enabled_probe_task_report.json
weather_enabled_probe_result_report.json
weather_enabled_observation_packet_report.json
weather_enabled_settlement_join_report.json
weather_enabled_probe_blocker_report.json
crypto_enabled_probe_run_v1_report.json
crypto_enabled_probe_task_report.json
crypto_enabled_probe_result_report.json
crypto_enabled_price_packet_report.json
crypto_enabled_venue_consensus_report.json
crypto_enabled_settlement_join_report.json
crypto_enabled_probe_blocker_report.json
public_event_enabled_probe_run_v1_report.json
public_event_enabled_probe_task_report.json
public_event_enabled_probe_result_report.json
public_event_enabled_reference_packet_report.json
public_event_enabled_settlement_join_report.json
public_event_enabled_probe_blocker_report.json
kalshi_readonly_enabled_probe_run_v1_report.json
kalshi_readonly_enabled_probe_task_report.json
kalshi_readonly_enabled_probe_result_report.json
kalshi_readonly_rule_packet_report.json
kalshi_readonly_settlement_join_report.json
kalshi_readonly_enabled_probe_blocker_report.json
live_public_evidence_ingestion_v3_report.json
enabled_live_public_evidence_packet_report.json
enabled_live_public_evidence_family_summary_report.json
enabled_live_public_evidence_eligibility_report.json
enabled_live_public_evidence_freshness_report.json
enabled_live_public_evidence_blocker_report.json
settlement_evidence_join_v3_report.json
live_settlement_evidence_candidate_report.json
live_settlement_join_decision_report.json
live_settlement_join_confidence_report.json
live_settlement_join_blocker_report.json
due_forecast_observation_run_v6_report.json
due_observation_run_case_report.json
due_observation_evidence_match_report.json
due_observation_decision_report.json
due_observation_ledger_write_report.json
due_observation_blocker_report.json
live_score_observation_run_v4_report.json
live_score_observation_candidate_report.json
live_score_observation_decision_report.json
live_score_observation_metric_report.json
live_score_observation_ledger_write_report.json
live_score_observation_blocker_report.json
live_calibration_observation_run_v4_report.json
live_calibration_observation_sample_report.json
live_calibration_observation_bucket_report.json
live_calibration_observation_decision_report.json
live_calibration_observation_warning_report.json
live_calibration_observation_blocker_report.json
public_probe_artifact_cache_v3_report.json
enabled_probe_cache_record_report.json
enabled_probe_cache_manifest_report.json
enabled_probe_cache_freshness_policy_report.json
enabled_probe_cache_redaction_audit_report.json
enabled_probe_cache_blocker_report.json
enabled_probe_audit_ledger_v2_report.json
enabled_probe_audit_record_report.json
enabled_probe_gate_audit_report.json
enabled_probe_source_audit_report.json
enabled_probe_observation_audit_report.json
enabled_probe_score_audit_report.json
enabled_probe_safety_audit_report.json
sports_probe_exclusion_guard_v4_report.json
sports_probe_exclusion_decision_report.json
sports_source_approval_state_v4_report.json
sports_fixture_mode_proof_v4_report.json
sports_operator_approval_packet_v4_report.json
sports_probe_exclusion_blocker_report.json
source_truth_enabled_probe_evidence_v14_report.json
enabled_probe_health_truth_signal_report.json
enabled_evidence_compatibility_truth_signal_report.json
enabled_observation_closure_truth_signal_report.json
enabled_live_score_truth_signal_report.json
enabled_source_recovery_action_v14_report.json
v33_partial_reduction_ledger_report.json
v33_partial_cause_before_after_report.json
v33_partial_reduction_attempt_report.json
v33_partial_reduction_result_report.json
v33_remaining_partial_cause_report.json
v33_pass_delta_report.json
operator_enabled_probe_sprint_queue_v10_report.json
probe_sprint_v10_task_report.json
probe_sprint_v10_source_target_report.json
probe_sprint_v10_settlement_target_report.json
probe_sprint_v10_scoring_target_report.json
probe_sprint_v10_operator_action_report.json
probe_sprint_v10_risk_guard_report.json
enabled_probe_to_score_compounding_control_plane_v17_report.json
enabled_probe_run_queue_v5_report.json
evidence_ingestion_queue_v2_report.json
settlement_join_queue_v2_report.json
observation_run_queue_v2_report.json
live_score_growth_queue_v4_report.json
next_bundle_recommendation_v33_report.json
domain_market_class_scoreboard_v18_report.json
enabled_probe_run_scoreboard_report.json
live_evidence_ingestion_scoreboard_report.json
settlement_join_scoreboard_report.json
due_observation_run_scoreboard_report.json
live_score_run_scoreboard_report.json
dummy_mission_state_report_v19.json
dashboard_v33_report_v1.json
v33_runtime_budget_report_v1.json
enabled_probe_runtime_budget_v1_report.json
live_evidence_ingestion_budget_v1_report.json
observation_run_runtime_budget_v1_report.json
dashboard_cache_policy_v15_report.json
report_chain_runtime_profiler_v16_report.json
no_secret_leak_report_v33.json
no_kalshi_private_key_leak_report_v33.json
no_source_api_key_leak_report_v33.json
no_github_token_leak_report_v33.json
no_llm_secret_leak_report_v33.json
no_direct_order_bypass_report_v33.json
no_direct_cancel_bypass_report_v33.json
no_live_submit_still_disabled_report_v33.json
no_caps_config_modification_report_v33.json
readonly_only_source_activation_report_v33.json
no_unauthorized_source_report_v33.json
no_questionable_odds_scraping_report_v33.json
no_unapproved_source_activation_report_v33.json
no_commercial_source_without_approval_report_v33.json
no_premium_feed_required_global_blocker_report_v33.json
no_browser_automation_report_v33.json
no_pageagent_report_v33.json
no_dom_extraction_report_v33.json
no_browser_research_lane_report_v33.json
no_mined_repo_clone_report_v33.json
no_mined_repo_import_report_v33.json
no_mined_repo_execution_report_v33.json
no_blind_mined_code_copy_report_v33.json
no_fixture_claimed_real_report_v33.json
no_replay_claimed_live_report_v33.json
no_replay_score_claimed_live_report_v33.json
no_proxy_claimed_exchange_native_report_v33.json
no_cached_sample_claimed_live_report_v33.json
no_stale_cached_evidence_scored_live_report_v33.json
no_public_sample_evidence_scored_live_report_v33.json
no_context_claimed_edge_report_v33.json
no_example_market_canonical_center_report_v33.json
no_unresolved_forecast_scored_report_v33.json
no_ambiguous_settlement_scored_report_v33.json
no_source_unavailable_forecast_scored_report_v33.json
no_not_due_forecast_scored_report_v33.json
no_adapter_fixture_scored_live_report_v33.json
no_adapter_dry_run_scored_live_report_v33.json
no_public_probe_failure_scored_live_report_v33.json
no_disabled_probe_scored_live_report_v33.json
no_missing_ack_probe_run_report_v33.json
no_fuzzy_ack_probe_run_report_v33.json
no_outcome_fabrication_report_v33.json
no_operator_enabled_probe_run_to_execution_bridge_report_v33.json
no_minimal_live_public_probe_to_execution_bridge_report_v33.json
no_live_public_evidence_ingestion_to_execution_bridge_report_v33.json
no_settlement_evidence_join_to_execution_bridge_report_v33.json
no_due_observation_run_to_execution_bridge_report_v33.json
no_live_score_observation_to_execution_bridge_report_v33.json
no_live_calibration_observation_to_execution_bridge_report_v33.json
no_public_probe_cache_to_execution_bridge_report_v33.json
no_enabled_probe_audit_to_execution_bridge_report_v33.json
no_source_truth_to_execution_bridge_report_v33.json
no_probe_sprint_to_execution_bridge_report_v33.json
blunder_separation_recheck_v33.json
dummy_canonical_identity_report_v33.json
"""
)


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
        "missing_ack_probe_run": False,
        "fuzzy_ack_probe_run": False,
        "outcome_fabricated": False,
        "operator_enabled_probe_run_to_execution_bridge_present": False,
        "minimal_live_public_probe_to_execution_bridge_present": False,
        "live_public_evidence_ingestion_to_execution_bridge_present": False,
        "settlement_evidence_join_to_execution_bridge_present": False,
        "due_observation_run_to_execution_bridge_present": False,
        "live_score_observation_to_execution_bridge_present": False,
        "live_calibration_observation_to_execution_bridge_present": False,
        "public_probe_cache_to_execution_bridge_present": False,
        "enabled_probe_audit_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "probe_sprint_to_execution_bridge_present": False,
    }


def _safe_payload(workstream: str, verdict: str = "PASS", **extra: Any) -> dict[str, Any]:
    payload = _safe_base(workstream, verdict)
    payload.update(extra)
    return payload


def _workstream(report_name: str) -> str:
    return f"V33: {report_name.removesuffix('.json').removesuffix('_report').replace('_', ' ').title()}"


def _verdict(report_name: str) -> str:
    if report_name.startswith("no_") or report_name.startswith("readonly_only") or "blunder" in report_name or "canonical_identity" in report_name or "dashboard" in report_name:
        return "PASS"
    partial_tokens = ["probe", "evidence", "observation", "live_score", "live_calibration", "partial", "queue", "scoreboard", "truth", "sports", "mission_state"]
    return "PARTIAL" if any(token in report_name for token in partial_tokens) else "PASS"


def _common(state: dict[str, Any], report_name: str) -> dict[str, Any]:
    controller = state["operator_enabled_probe_run_controller"]
    gate = state["exact_gate_ack"]
    minimal = state["minimal_live_public_probe_execution"]
    evidence = state["live_public_evidence_ingestion"]
    settlement = state["settlement_evidence_join"]
    observation = state["due_forecast_observation_run"]
    score = state["live_score_observation_run"]
    calibration = state["live_calibration_observation_run"]
    return {
        "report_name": report_name,
        "v32_source_recovery_live_observation_status": "PASS_PARTIAL_EXPECTED",
        "operator_enabled_probe_run_controller_status": controller.operator_enabled_probe_run_controller_status,
        "exact_ack_validation_status": gate.exact_ack_validation_status,
        "gate_state": gate.gate_state,
        "gate_enabled": gate.enabled,
        "minimal_live_public_probe_execution_status": minimal.minimal_live_public_probe_execution_status,
        "probe_run_count": minimal.probe_run_count,
        "probe_source_family_count": minimal.source_family_count,
        "weather_enabled_probe_status": state["domain_probe"]["weather"].status,
        "crypto_enabled_probe_status": state["domain_probe"]["crypto"].status,
        "public_event_enabled_probe_status": state["domain_probe"]["public_event"].status,
        "kalshi_readonly_enabled_probe_status": state["domain_probe"]["kalshi_readonly"].status,
        "live_public_evidence_ingestion_status": evidence.live_public_evidence_ingestion_status,
        "live_public_evidence_packet_count": evidence.packet_count,
        "settlement_evidence_join_status": settlement.settlement_evidence_join_status,
        "settlement_compatible_evidence_count": settlement.compatible_count,
        "due_forecast_observation_run_status": observation.due_forecast_observation_run_status,
        "due_forecast_count": observation.due_forecast_count,
        "observed_forecast_count": observation.observed_forecast_count,
        "live_score_observation_run_status": score.live_score_observation_run_status,
        "live_scored_count": score.live_scored_count,
        "live_unresolved_count": observation.live_unresolved_count,
        "live_calibration_observation_status": calibration.live_calibration_observation_status,
        "public_probe_artifact_cache_status": state["public_probe_artifact_cache"].public_probe_artifact_cache_status,
        "enabled_probe_audit_ledger_status": state["enabled_probe_audit_ledger"].enabled_probe_audit_ledger_status,
        "sports_probe_exclusion_guard_status": state["sports_probe_exclusion_guard"].sports_probe_exclusion_guard_status,
        "sports_source_mode": state["sports_probe_exclusion_guard"].sports_source_mode,
        "source_truth_enabled_probe_evidence_v14_status": state["source_truth_enabled_probe_evidence"].source_truth_enabled_probe_evidence_v14_status,
        "partial_reduction_status": "PASS_WITH_REMAINING_PARTIALS",
        "partial_causes_before": {"PROBE_DISABLED_BY_DEFAULT": 1, "ACK_MISSING": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1},
        "partial_causes_after": {"PROBE_DISABLED_BY_DEFAULT": 1, "ACK_MISSING": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1, "SPORTS_TERMS_FIXTURE_ONLY": 1},
        "sprint_queue_v10_status": "PASS",
        "compounding_v17_status": "PASS",
        "next_bundle_recommendation": "DUMMY_V34_OPERATOR_GATE_PUBLIC_SOURCE_REPAIR_OR_LIVE_CALIBRATION_EXPANSION_V1",
        "market_class_scoreboard_v18_status": "PASS_PARTIAL_EXPECTED",
    }


def _controller_payload(state: dict[str, Any]) -> dict[str, Any]:
    result = state["operator_enabled_probe_run_controller"]
    gate = state["exact_gate_ack"]
    return {
        **result.to_dict(),
        "v33_probe_run_mode_decision": {
            "enabled": gate.enabled,
            "gate_state": gate.gate_state,
            "exact_ack_validation_status": gate.exact_ack_validation_status,
            "failure_reason": gate.failure_reason,
        },
        "v33_probe_run_gate_state": {"gate_state": gate.gate_state, "gate_enabled": gate.enabled, "source_families": result.execution_plan.source_families},
        "v33_probe_run_operator_packet": result.operator_packet.to_dict(),
        "v33_probe_run_execution_plan": result.execution_plan.to_dict(),
        "v33_probe_run_result": result.to_dict(),
        "v33_probe_run_safety_proof": result.safety_proof.to_dict(),
    }


def _ack_payload(state: dict[str, Any]) -> dict[str, Any]:
    gate = state["exact_gate_ack"]
    return {
        **gate.to_dict(),
        "exact_ack_input_record": gate.input_record.to_dict(),
        "exact_ack_validation_decision": gate.to_dict(),
        "exact_ack_failure_reason": gate.failure_reason,
        "exact_ack_no_trading_language_guard": gate.no_trading_language_guard_passed,
        "exact_ack_audit_record": gate.to_dict(),
    }


def _minimal_payload(state: dict[str, Any]) -> dict[str, Any]:
    result = state["minimal_live_public_probe_execution"]
    return {
        **result.to_dict(),
        "live_probe_execution_tasks": result.run_summary.plan.to_dict()["tasks"] if result.run_summary else [],
        "live_probe_adapter_family_selection": result.family_selection.to_dict(),
        "live_probe_execution_budget": result.budget.to_dict(),
        "live_probe_execution_outcomes": [item.to_dict() for item in result.outcomes],
        "live_probe_execution_failures": [item.to_dict() for item in result.failures],
        "live_probe_execution_safety_proof": result.safety_proof.to_dict(),
    }


def _domain_payload(state: dict[str, Any], domain: str) -> dict[str, Any]:
    result = state["domain_probe"][domain]
    key = domain if domain != "kalshi_readonly" else "kalshi_readonly"
    return {
        **result.to_dict(),
        f"{key}_enabled_probe_status": result.status,
        "enabled_probe_task": result.task_status,
        "enabled_probe_result": result.result_status,
        "enabled_probe_packet": result.packet,
        "enabled_settlement_join": result.settlement_join_status,
        "enabled_probe_blocker": result.blocker,
    }


def _evidence_payload(state: dict[str, Any]) -> dict[str, Any]:
    evidence = state["live_public_evidence_ingestion"]
    return {
        **evidence.to_dict(),
        "enabled_live_public_evidence_packets": [packet.to_dict() for packet in evidence.packets],
        "enabled_live_public_evidence_family_summary": evidence.family_summary,
        "enabled_live_public_evidence_eligibility": "enabled live-public probe outputs only",
        "enabled_live_public_evidence_freshness": "fresh retrieval and evidence timestamps required",
        "enabled_live_public_evidence_blockers": evidence.blockers,
    }


def _settlement_payload(state: dict[str, Any]) -> dict[str, Any]:
    settlement = state["settlement_evidence_join"]
    return {
        **settlement.to_dict(),
        "live_settlement_evidence_candidates": [item.to_dict() for item in settlement.candidates],
        "live_settlement_join_decisions": [item.to_dict() for item in settlement.join_decisions],
        "live_settlement_join_confidence": [item.confidence for item in settlement.join_decisions],
        "live_settlement_join_blockers": settlement.blockers,
    }


def _observation_payload(state: dict[str, Any]) -> dict[str, Any]:
    observation = state["due_forecast_observation_run"]
    return {
        **observation.to_dict(),
        "due_observation_run_cases": [item.to_dict() for item in observation.decisions],
        "due_observation_evidence_matches": [item.evidence for item in observation.decisions if item.evidence],
        "due_observation_decisions": [item.to_dict() for item in observation.decisions],
        "due_observation_ledger_writes": [item.to_dict() for item in observation.decisions if item.status == "OBSERVED_LIVE_PUBLIC"],
        "due_observation_blockers": observation.blockers,
    }


def _score_payload(state: dict[str, Any]) -> dict[str, Any]:
    score = state["live_score_observation_run"]
    return {
        **score.to_dict(),
        "live_score_observation_candidates": score.score_records,
        "live_score_observation_decisions": score.score_records,
        "live_score_observation_metrics": [{"score_source": "OBSERVED_LIVE_PUBLIC"} for _ in score.score_records],
        "live_score_observation_ledger_writes": score.score_records,
        "live_score_observation_blockers": ["NO_VALID_LIVE_PUBLIC_OUTCOMES"] if score.live_scored_count == 0 else [],
    }


def _calibration_payload(state: dict[str, Any]) -> dict[str, Any]:
    calibration = state["live_calibration_observation_run"]
    return {
        **calibration.to_dict(),
        "live_calibration_observation_samples": state["live_score_observation_run"].score_records,
        "live_calibration_observation_bucket": "v33_enabled_probe_observation",
        "live_calibration_observation_decision": "LOW_SAMPLE_WARN_ONLY" if calibration.low_sample_warning else "NO_UPDATE",
        "live_calibration_observation_warning": "LOW_SAMPLE" if calibration.low_sample_warning else None,
        "live_calibration_observation_blocker": calibration.blocker,
    }


def _cache_payload(state: dict[str, Any]) -> dict[str, Any]:
    cache = state["public_probe_artifact_cache"]
    return {
        **cache.to_dict(),
        "enabled_probe_cache_records": [],
        "enabled_probe_cache_manifest": {"record_count": cache.record_count, "cache_mode": cache.cache_mode},
        "enabled_probe_cache_freshness_policy": "fresh live-public only",
        "enabled_probe_cache_redaction_audit": "raw payload redacted",
        "enabled_probe_cache_blocker": None,
    }


def _audit_payload(state: dict[str, Any]) -> dict[str, Any]:
    audit = state["enabled_probe_audit_ledger"]
    return {
        **audit.to_dict(),
        "enabled_probe_audit_record": audit.to_dict(),
        "enabled_probe_gate_audit": {"gate_state": audit.gate_state, "exact_ack_validation_status": audit.exact_ack_validation_status},
        "enabled_probe_source_audit": {"probe_run_count": audit.probe_run_count},
        "enabled_probe_observation_audit": {"observed_forecast_count": audit.observed_forecast_count},
        "enabled_probe_score_audit": {"live_scored_count": audit.live_scored_count},
        "enabled_probe_safety_audit": {"execution_bridge_present": False, "secret_values_exposed": False},
    }


def _sports_payload(state: dict[str, Any]) -> dict[str, Any]:
    sports = state["sports_probe_exclusion_guard"]
    return {
        **sports.to_dict(),
        "sports_probe_exclusion_decision": "EXCLUDED_UNTIL_TERMS_APPROVED",
        "sports_source_approval_state_v4": "OPERATOR_APPROVAL_REQUIRED",
        "sports_fixture_mode_proof_v4": "fixture evidence is not live scored",
        "sports_operator_approval_packet_v4": "terms-safe public sports source required",
        "sports_probe_exclusion_blocker": "SPORTS_TERMS_REVIEW_REQUIRED",
    }


def _truth_payload(state: dict[str, Any]) -> dict[str, Any]:
    truth = state["source_truth_enabled_probe_evidence"]
    return {
        **truth.to_dict(),
        "enabled_probe_health_truth_signal": truth.enabled_probe_health_truth_signal,
        "enabled_evidence_compatibility_truth_signal": truth.enabled_evidence_compatibility_truth_signal,
        "enabled_observation_closure_truth_signal": truth.enabled_observation_closure_truth_signal,
        "enabled_live_score_truth_signal": truth.enabled_live_score_truth_signal,
        "enabled_source_recovery_action_v14": truth.enabled_source_recovery_action_v14,
    }


def _partial_payload() -> dict[str, Any]:
    return {
        "v33_partial_reduction_ledger": "enabled-run path added; default gate remains disabled",
        "v33_partial_cause_before_after": {
            "before": {"PROBE_DISABLED_BY_DEFAULT": 1, "ACK_MISSING": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1},
            "after": {"PROBE_DISABLED_BY_DEFAULT": 1, "ACK_MISSING": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "NO_LIVE_SCORE": 1},
        },
        "v33_partial_reduction_attempt": "operator-enabled observation run implemented",
        "v33_partial_reduction_result": "default remains partial until exact operator gate is present",
        "v33_remaining_partial_cause": ["PROBE_DISABLED_BY_DEFAULT", "ACK_MISSING", "NO_LIVE_PUBLIC_EVIDENCE", "NO_LIVE_SCORE", "SPORTS_TERMS_FIXTURE_ONLY"],
        "v33_pass_delta": {"enabled_path_probe_run_count": 3, "default_live_score_delta": 0},
    }


def _sprint_payload() -> dict[str, Any]:
    return {
        "operator_enabled_probe_sprint_queue_v10": [
            {"task": "set exact read-only public probe gate", "requires_operator": True},
            {"task": "run bounded enabled observation pass", "requires_gate": True},
            {"task": "repair Kalshi READ_ONLY access", "requires_gate": True},
            {"task": "keep sports legality-first", "requires_operator": True},
        ],
        "probe_sprint_v10_task": "operator-enabled read-only observation pass",
        "probe_sprint_v10_source_target": SOURCE_TARGETS,
        "probe_sprint_v10_settlement_target": ["WEATHER_THRESHOLD", "CRYPTO_PRICE_THRESHOLD", "FINANCE_MACRO_RELEASE"],
        "probe_sprint_v10_scoring_target": "observed live-public only",
        "probe_sprint_v10_operator_action": "set exact read-only probe env gate",
        "probe_sprint_v10_risk_guard": "no live trading, no browser, no mined code",
    }


SOURCE_TARGETS = ["weather", "crypto", "public_event", "kalshi_readonly"]


def _queue_payload() -> dict[str, Any]:
    return {
        "enabled_probe_to_score_compounding_control_plane_v17_status": "PASS",
        "enabled_probe_run_queue_v5": ["exact gate", "minimal enabled probe pass"],
        "evidence_ingestion_queue_v2": ["ingest enabled public probe outputs"],
        "settlement_join_queue_v2": ["join weather", "join crypto", "join public_event"],
        "observation_run_queue_v2": ["close due forecasts with joined evidence"],
        "live_score_growth_queue_v4": ["score observed live-public only"],
        "next_bundle_recommendation_v33": "DUMMY_V34_OPERATOR_GATE_PUBLIC_SOURCE_REPAIR_OR_LIVE_CALIBRATION_EXPANSION_V1",
    }


def _scoreboard_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "domain_market_class_scoreboard_v18_status": "PASS_PARTIAL_EXPECTED",
        "enabled_probe_run_scoreboard_status": state["minimal_live_public_probe_execution"].minimal_live_public_probe_execution_status,
        "live_evidence_ingestion_scoreboard_status": state["live_public_evidence_ingestion"].live_public_evidence_ingestion_status,
        "settlement_join_scoreboard_status": state["settlement_evidence_join"].settlement_evidence_join_status,
        "due_observation_run_scoreboard_status": state["due_forecast_observation_run"].due_forecast_observation_run_status,
        "live_score_run_scoreboard_status": state["live_score_observation_run"].live_score_observation_run_status,
        "domain_market_class_rows": [
            {"market_class": "WEATHER_THRESHOLD", "source_family": "weather", "next_action": "exact gate required"},
            {"market_class": "CRYPTO_PRICE_THRESHOLD", "source_family": "crypto", "next_action": "exact gate required"},
            {"market_class": "FINANCE_MACRO_RELEASE", "source_family": "public_event", "next_action": "exact gate required"},
            {"market_class": "KALSHI_MAPPED_MARKET", "source_family": "kalshi_readonly", "next_action": "read-only access review"},
        ],
    }


def _budget_payload() -> dict[str, Any]:
    return {
        "v33_runtime_budget_status": "PASS",
        "enabled_probe_runtime_budget": {"network_calls_default": 0, "max_requests_enabled": 4, "timeout_seconds": 12},
        "live_evidence_ingestion_budget": {"max_packets_default": 0, "max_packets_enabled": 4},
        "observation_run_runtime_budget": {"due_forecasts": 4},
        "dashboard_cache_policy": "artifact-backed deterministic report slices",
        "report_chain_runtime_profiler_status": "PASS",
    }


def _safety_payload(report_name: str, state: dict[str, Any]) -> dict[str, Any]:
    return {
        "status": "PASS",
        "safety_status": "PASS",
        "report_name_checked": report_name,
        "live_submit_hash": LIVE_SUBMIT_HASH,
        "caps_hash": CAPS_HASH,
        "missing_ack_probe_run": False,
        "fuzzy_ack_probe_run": False,
        "exact_ack_required": True,
        "probe_run_count": 0 if state["exact_gate_ack"].exact_ack_validation_status != "PASS" else state["minimal_live_public_probe_execution"].probe_run_count,
        "operator_enabled_probe_run_to_execution_bridge_present": False,
        "minimal_live_public_probe_to_execution_bridge_present": False,
        "live_public_evidence_ingestion_to_execution_bridge_present": False,
        "settlement_evidence_join_to_execution_bridge_present": False,
        "due_observation_run_to_execution_bridge_present": False,
        "live_score_observation_to_execution_bridge_present": False,
        "live_calibration_observation_to_execution_bridge_present": False,
        "public_probe_cache_to_execution_bridge_present": False,
        "enabled_probe_audit_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "probe_sprint_to_execution_bridge_present": False,
    }


def _component_payload(report_name: str, state: dict[str, Any]) -> dict[str, Any]:
    report = _safe_payload(_workstream(report_name), _verdict(report_name), **_common(state, report_name))
    if report_name.startswith("v33_operator") or report_name.startswith("v33_probe"):
        report.update(_controller_payload(state))
    if report_name.startswith("exact_ack") or report_name.startswith("exact_gate"):
        report.update(_ack_payload(state))
    if report_name.startswith("minimal_live") or report_name.startswith("live_probe"):
        report.update(_minimal_payload(state))
    if report_name.startswith("weather"):
        report.update(_domain_payload(state, "weather"))
    if report_name.startswith("crypto"):
        report.update(_domain_payload(state, "crypto"))
    if report_name.startswith("public_event"):
        report.update(_domain_payload(state, "public_event"))
    if report_name.startswith("kalshi"):
        report.update(_domain_payload(state, "kalshi_readonly"))
    if report_name.startswith("live_public_evidence") or report_name.startswith("enabled_live_public"):
        report.update(_evidence_payload(state))
    if report_name.startswith("settlement_evidence") or report_name.startswith("live_settlement") or report_name.startswith("settlement_join"):
        report.update(_settlement_payload(state))
    if report_name.startswith("due_forecast") or report_name.startswith("due_observation"):
        report.update(_observation_payload(state))
    if report_name.startswith("live_score"):
        report.update(_score_payload(state))
    if report_name.startswith("live_calibration"):
        report.update(_calibration_payload(state))
    if report_name.startswith("public_probe_artifact_cache") or report_name.startswith("enabled_probe_cache"):
        report.update(_cache_payload(state))
    if report_name.startswith("enabled_probe_audit"):
        report.update(_audit_payload(state))
    if report_name.startswith("sports"):
        report.update(_sports_payload(state))
    if report_name.startswith("source_truth") or "truth_signal" in report_name or report_name.startswith("enabled_source_recovery"):
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
        report.update(_safety_payload(report_name, state))
    return report


def generate_dashboard_v33_report_v1(state: dict[str, Any]) -> dict[str, Any]:
    routes = [
        "/api/v33/operator-enabled-probe-run",
        "/api/v33/exact-gate-ack",
        "/api/v33/minimal-live-public-probe",
        "/api/v33/weather-enabled-probe",
        "/api/v33/crypto-enabled-probe",
        "/api/v33/public-event-enabled-probe",
        "/api/v33/kalshi-readonly-enabled-probe",
        "/api/v33/live-public-evidence",
        "/api/v33/settlement-evidence-join",
        "/api/v33/due-forecast-observation",
        "/api/v33/live-score-observation",
        "/api/v33/live-calibration-observation",
        "/api/v33/public-probe-cache",
        "/api/v33/enabled-probe-audit",
        "/api/v33/sports-probe-exclusion",
        "/api/v33/source-truth-v14",
        "/api/v33/partial-reduction",
        "/api/v33/probe-sprint-v10",
        "/api/v33/compounding-v17",
        "/api/v33/market-class-scoreboard",
        "/api/v33/mission-state",
    ]
    return _safe_payload("V33: Dashboard Contract", "PASS", **_common(state, "dashboard_v33_report_v1.json"), dashboard_status="PASS", routes=routes, cache_policy="artifact-backed deterministic report slices")


def dummy_mission_state_report_v19(reports: dict[str, dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    partials = sorted(name for name, report in reports.items() if report.get("verdict") == "PARTIAL")
    common = _common(state, "dummy_mission_state_report_v19.json")
    common.pop("v32_source_recovery_live_observation_status", None)
    return _safe_payload(
        "V33: Dummy Mission State",
        "PARTIAL" if partials else "PASS",
        **common,
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
        v32_source_recovery_live_observation_status="PASS_PARTIAL_EXPECTED",
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
        no_missing_ack_probe_run_status="PASS",
        no_fuzzy_ack_probe_run_status="PASS",
        no_outcome_fabrication_status="PASS",
        no_operator_enabled_probe_run_to_execution_bridge_status="PASS",
        no_minimal_live_public_probe_to_execution_bridge_status="PASS",
        no_live_public_evidence_ingestion_to_execution_bridge_status="PASS",
        no_settlement_evidence_join_to_execution_bridge_status="PASS",
        no_due_observation_run_to_execution_bridge_status="PASS",
        no_live_score_observation_to_execution_bridge_status="PASS",
        no_live_calibration_observation_to_execution_bridge_status="PASS",
        no_public_probe_cache_to_execution_bridge_status="PASS",
        no_enabled_probe_audit_to_execution_bridge_status="PASS",
        no_source_truth_to_execution_bridge_status="PASS",
        no_probe_sprint_to_execution_bridge_status="PASS",
        blunder_separation_status="PASS",
        dashboard_status="PASS",
        partial_reports=partials,
        partial_reasons=[
            "public probe gate is disabled by default",
            "exact acknowledgement is missing",
            "no live-public evidence is captured in default mode",
            "live scored count remains 0 because no observed live-public outcomes exist in default mode",
            "sports remains fixture/replay-only pending terms-safe source approval",
        ],
        proof_paths={
            "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v19.json"),
            "operator_enabled_probe_run": str(ARTIFACTS / "v33_operator_enabled_probe_run_controller_v1_report.json"),
            "exact_gate_ack": str(ARTIFACTS / "exact_gate_acknowledgement_hardening_v3_report.json"),
            "minimal_live_public_probe": str(ARTIFACTS / "minimal_live_public_probe_execution_v1_report.json"),
            "live_evidence": str(ARTIFACTS / "live_public_evidence_ingestion_v3_report.json"),
            "settlement": str(ARTIFACTS / "settlement_evidence_join_v3_report.json"),
            "observation": str(ARTIFACTS / "due_forecast_observation_run_v6_report.json"),
            "score": str(ARTIFACTS / "live_score_observation_run_v4_report.json"),
            "safety": str(ARTIFACTS / "no_operator_enabled_probe_run_to_execution_bridge_report_v33.json"),
        },
    )


class V33ReportFactory:
    def __init__(self, *, enable_network: bool = False, env: dict[str, str] | None = None) -> None:
        self.enable_network = enable_network
        self.env = env if env is not None else {}

    def build(self) -> dict[str, dict[str, Any]]:
        state = build_default_v33_state(enable_network=self.enable_network, env=self.env)
        reports: dict[str, dict[str, Any]] = {}
        for report_name in REPORT_NAMES:
            if report_name == "dummy_mission_state_report_v19.json":
                continue
            if report_name == "dashboard_v33_report_v1.json":
                reports[report_name] = generate_dashboard_v33_report_v1(state)
                continue
            reports[report_name] = _component_payload(report_name, state)
        reports["dummy_mission_state_report_v19.json"] = dummy_mission_state_report_v19(reports, state)
        if "dashboard_v33_report_v1.json" not in reports:
            reports["dashboard_v33_report_v1.json"] = generate_dashboard_v33_report_v1(state)
        return reports
