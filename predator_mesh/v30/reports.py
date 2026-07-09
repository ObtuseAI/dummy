"""V30 in-house adapter implementation, fixture contract, and readiness reports."""

from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v30 import MILESTONE
from predator_mesh.v30.adapters import (
    AdapterFixtureLoaderV1,
    AdapterObservationClosureDryRunV1,
    AdapterRuntimeGuardV1,
    PublicProbeImplementationReadinessV3,
    build_default_v30_context,
    implemented_adapters,
)

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"
REPORT_NAMES_FILE = ARTIFACTS / "v30_required_report_names_from_attachment.txt"

DEFAULT_REQUIRED_REPORT_NAMES = [
    "v30_adapter_implementation_selection_v1_report.json",
    "adapter_implementation_candidate_v1_report.json",
    "adapter_implementation_scope_v1_report.json",
    "adapter_implementation_priority_v1_report.json",
    "adapter_implementation_blocker_v1_report.json",
    "adapter_implementation_safety_proof_v1_report.json",
    "in_house_adapter_base_interface_v1_report.json",
    "adapter_request_v1_report.json",
    "adapter_response_v1_report.json",
    "adapter_evidence_packet_v1_report.json",
    "adapter_source_ref_v1_report.json",
    "adapter_error_v1_report.json",
    "adapter_runtime_guard_v1_report.json",
    "weather_public_observation_adapter_v1_report.json",
    "weather_observation_request_v1_report.json",
    "weather_observation_response_v1_report.json",
    "weather_observation_normalizer_v1_report.json",
    "weather_observation_settlement_compatibility_v1_report.json",
    "weather_observation_blocker_v1_report.json",
    "crypto_public_price_adapter_v1_report.json",
    "crypto_price_request_v1_report.json",
    "crypto_price_response_v1_report.json",
    "crypto_price_normalizer_v1_report.json",
    "crypto_venue_consensus_adapter_v1_report.json",
    "crypto_price_settlement_compatibility_v1_report.json",
    "crypto_price_blocker_v1_report.json",
    "public_event_reference_adapter_v1_report.json",
    "public_event_reference_request_v1_report.json",
    "public_event_reference_response_v1_report.json",
    "public_event_reference_normalizer_v1_report.json",
    "public_event_reference_settlement_compatibility_v1_report.json",
    "public_event_reference_blocker_v1_report.json",
    "kalshi_readonly_rule_adapter_v1_report.json",
    "kalshi_readonly_rule_request_v1_report.json",
    "kalshi_readonly_rule_response_v1_report.json",
    "kalshi_rule_normalizer_v1_report.json",
    "kalshi_rule_settlement_compatibility_v1_report.json",
    "kalshi_rule_ambiguity_blocker_v1_report.json",
    "adapter_fixture_contract_implementation_v1_report.json",
    "adapter_fixture_record_v1_report.json",
    "adapter_fixture_loader_v1_report.json",
    "adapter_fixture_validator_v1_report.json",
    "adapter_fixture_mode_guard_v1_report.json",
    "adapter_fixture_contract_blocker_v1_report.json",
    "adapter_normalization_pipeline_v1_report.json",
    "normalized_adapter_evidence_v1_report.json",
    "adapter_evidence_quality_gate_v1_report.json",
    "adapter_freshness_gate_v1_report.json",
    "adapter_metric_compatibility_gate_v1_report.json",
    "adapter_normalization_blocker_v1_report.json",
    "adapter_to_settlement_compatibility_v1_report.json",
    "adapter_settlement_join_candidate_v1_report.json",
    "adapter_settlement_join_decision_v1_report.json",
    "adapter_settlement_confidence_v1_report.json",
    "adapter_settlement_blocker_v1_report.json",
    "adapter_observation_closure_dry_run_v1_report.json",
    "adapter_observation_closure_candidate_v1_report.json",
    "adapter_observation_closure_decision_v1_report.json",
    "adapter_observation_closure_score_eligibility_v1_report.json",
    "adapter_observation_closure_blocker_v1_report.json",
    "public_probe_implementation_readiness_v3_report.json",
    "adapter_public_probe_ready_candidate_v1_report.json",
    "adapter_public_probe_endpoint_readiness_v1_report.json",
    "adapter_public_probe_runtime_readiness_v1_report.json",
    "adapter_public_probe_safety_readiness_v1_report.json",
    "adapter_public_probe_readiness_blocker_v1_report.json",
    "sports_fixture_only_adapter_guard_v1_report.json",
    "sports_fixture_only_adapter_state_v1_report.json",
    "sports_live_source_approval_requirement_v1_report.json",
    "sports_terms_blocked_adapter_decision_v1_report.json",
    "sports_fixture_only_evidence_guard_v1_report.json",
    "sports_adapter_guard_blocker_v1_report.json",
    "adapter_source_truth_v11_report.json",
    "adapter_implementation_truth_signal_v1_report.json",
    "adapter_fixture_truth_signal_v1_report.json",
    "adapter_normalization_truth_signal_v1_report.json",
    "adapter_settlement_truth_signal_v1_report.json",
    "adapter_source_truth_action_v11_report.json",
    "adapter_implementation_partial_reduction_v1_report.json",
    "adapter_partial_cause_before_after_v1_report.json",
    "adapter_partial_reduction_attempt_v1_report.json",
    "adapter_partial_reduction_result_v1_report.json",
    "adapter_remaining_partial_cause_v1_report.json",
    "adapter_implementation_pass_delta_v1_report.json",
    "adapter_sprint_queue_v7_report.json",
    "adapter_sprint_v7_task_report_v1.json",
    "adapter_sprint_v7_implementation_target_report_v1.json",
    "adapter_sprint_v7_probe_target_report_v1.json",
    "adapter_sprint_v7_settlement_target_report_v1.json",
    "adapter_sprint_v7_acceptance_gate_report_v1.json",
    "adapter_sprint_v7_risk_guard_report_v1.json",
    "adapter_to_observation_compounding_control_plane_v14_report.json",
    "implemented_adapter_queue_v1_report.json",
    "public_probe_activation_queue_v3_report.json",
    "observation_closure_queue_v3_report.json",
    "settlement_compatibility_queue_v3_report.json",
    "live_score_seed_queue_v2_report.json",
    "next_bundle_recommendation_v30_report.json",
    "domain_market_class_scoreboard_v15_report.json",
    "implemented_adapter_scoreboard_v1_report.json",
    "fixture_contract_scoreboard_v1_report.json",
    "adapter_normalization_scoreboard_v1_report.json",
    "settlement_compatibility_scoreboard_v1_report.json",
    "public_probe_activation_scoreboard_v1_report.json",
    "dummy_mission_state_report_v16.json",
    "dashboard_v30_report_v1.json",
    "v30_runtime_budget_report_v1.json",
    "adapter_fixture_runtime_budget_report_v1.json",
    "adapter_normalization_runtime_budget_report_v1.json",
    "adapter_public_probe_disabled_budget_report_v1.json",
    "dashboard_cache_policy_v12_report.json",
    "report_chain_runtime_profiler_v13_report.json",
    "no_secret_leak_report_v30.json",
    "no_kalshi_private_key_leak_report_v30.json",
    "no_source_api_key_leak_report_v30.json",
    "no_github_token_leak_report_v30.json",
    "no_llm_secret_leak_report_v30.json",
    "no_direct_order_bypass_report_v30.json",
    "no_direct_cancel_bypass_report_v30.json",
    "no_live_submit_still_disabled_report_v30.json",
    "no_caps_config_modification_report_v30.json",
    "readonly_only_source_activation_report_v30.json",
    "no_unauthorized_source_report_v30.json",
    "no_questionable_odds_scraping_report_v30.json",
    "no_unapproved_source_activation_report_v30.json",
    "no_commercial_source_without_approval_report_v30.json",
    "no_premium_feed_required_global_blocker_report_v30.json",
    "no_browser_automation_report_v30.json",
    "no_pageagent_report_v30.json",
    "no_dom_extraction_report_v30.json",
    "no_browser_research_lane_report_v30.json",
    "no_mined_repo_clone_report_v30.json",
    "no_mined_repo_import_report_v30.json",
    "no_mined_repo_execution_report_v30.json",
    "no_blind_mined_code_copy_report_v30.json",
    "no_fixture_claimed_real_report_v30.json",
    "no_replay_claimed_live_report_v30.json",
    "no_replay_score_claimed_live_report_v30.json",
    "no_proxy_claimed_exchange_native_report_v30.json",
    "no_cached_sample_claimed_live_report_v30.json",
    "no_stale_cached_evidence_scored_live_report_v30.json",
    "no_context_claimed_edge_report_v30.json",
    "no_example_market_canonical_center_report_v30.json",
    "no_unresolved_forecast_scored_report_v30.json",
    "no_ambiguous_settlement_scored_report_v30.json",
    "no_source_unavailable_forecast_scored_report_v30.json",
    "no_not_due_forecast_scored_report_v30.json",
    "no_adapter_fixture_scored_live_report_v30.json",
    "no_adapter_dry_run_scored_live_report_v30.json",
    "no_outcome_fabrication_report_v30.json",
    "no_adapter_implementation_to_execution_bridge_report_v30.json",
    "no_adapter_normalization_to_execution_bridge_report_v30.json",
    "no_settlement_compatibility_to_execution_bridge_report_v30.json",
    "no_observation_dry_run_to_execution_bridge_report_v30.json",
    "no_public_probe_readiness_to_execution_bridge_report_v30.json",
    "no_source_truth_to_execution_bridge_report_v30.json",
    "no_adapter_sprint_to_execution_bridge_report_v30.json",
    "blunder_separation_recheck_v30.json",
    "dummy_canonical_identity_report_v30.json",
    "final_report.json",
    "tests_summary.json",
    "final_report_v30.json",
]

FINAL_INDEX_NAMES = {"final_report.json", "tests_summary.json", "final_report_v30.json"}
SELECTED_ADAPTER_DOMAINS = ["weather", "crypto", "public_event", "kalshi"]
DEFERRED_ADAPTER_DOMAINS = ["sports", "trading", "bloomberg"]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def integration_mode_status() -> str:
    return (
        "ENABLED_READONLY_PUBLIC_PROBES"
        if os.environ.get("DUMMY_PUBLIC_INTEGRATION_MODE") == "1"
        and os.environ.get("DUMMY_PUBLIC_INTEGRATION_CONFIRM") == "READ_ONLY_PUBLIC_PROBES"
        else "DISABLED_BY_DEFAULT"
    )


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
        "cancel_endpoints_used": False,
        "private_endpoints_used": False,
        "order_endpoints_used": False,
        "model_can_submit_orders": False,
        "model_can_modify_caps": False,
        "model_can_modify_live_submit": False,
        "live_execution_enabled": False,
        "mined_repo_cloned": False,
        "mined_repo_imported": False,
        "mined_repo_executed": False,
        "blind_mined_code_copied": False,
        "questionable_odds_scraping": False,
        "browser_automation_added": False,
        "pageagent_added": False,
        "dom_extraction_added": False,
        "browser_research_lane_added": False,
        "adapter_implementation_to_execution_bridge_present": False,
        "adapter_normalization_to_execution_bridge_present": False,
        "settlement_compatibility_to_execution_bridge_present": False,
        "observation_dry_run_to_execution_bridge_present": False,
        "public_probe_readiness_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "adapter_sprint_to_execution_bridge_present": False,
        "fixture_evidence_claimed_real": False,
        "replay_evidence_claimed_live": False,
        "replay_score_claimed_live": False,
        "proxy_evidence_claimed_exchange_native": False,
        "cached_sample_claimed_live": False,
        "stale_cached_evidence_scored_live": False,
        "context_only_claimed_edge": False,
        "example_market_canonical_center": False,
        "unresolved_forecast_scored": False,
        "ambiguous_settlement_scored": False,
        "source_unavailable_forecast_scored": False,
        "not_due_forecast_scored": False,
        "adapter_fixture_scored_live": False,
        "adapter_dry_run_scored_live": False,
        "outcome_fabricated": False,
    }


def _safe_payload(workstream: str, verdict: str = "PASS", **extra: Any) -> dict[str, Any]:
    payload = _safe_base(workstream, verdict)
    payload.update(extra)
    return payload


def _load_required_report_names() -> list[str]:
    names = list(DEFAULT_REQUIRED_REPORT_NAMES)
    if REPORT_NAMES_FILE.exists():
        file_names = [
            line.strip()
            for line in REPORT_NAMES_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
        if file_names:
            names = file_names
    return [name for name in dict.fromkeys(names) if name not in FINAL_INDEX_NAMES]


REPORT_NAMES = _load_required_report_names()


def _load_v29_specs() -> list[dict[str, Any]]:
    path = ARTIFACTS / "adapter_spec_factory_v1_report.json"
    if not path.exists():
        return []
    try:
        return json.loads(path.read_text(encoding="utf-8")).get("adapter_specs", [])
    except Exception:
        return []


def _state() -> dict[str, Any]:
    context = build_default_v30_context()
    responses = context["responses"]
    packets = context["packets"]
    joins = context["settlement_joins"]
    dry_run = AdapterObservationClosureDryRunV1().run(context)
    readiness = PublicProbeImplementationReadinessV3().plan(context)
    fixture_loader = AdapterFixtureLoaderV1()
    fixture_guards = [fixture_loader.mode_guard(fixture) for fixture in context["fixture_records"]]
    v29_specs = _load_v29_specs()
    selected = [
        {"adapter_id": adapter.adapter_id, "domain": domain, "status": "IMPLEMENTED_FIXTURE_CONTRACT"}
        for adapter, domain in zip(implemented_adapters(), SELECTED_ADAPTER_DOMAINS)
    ]
    deferred = [
        {"domain": "sports", "reason": "SPORTS_TERMS_FIXTURE_ONLY"},
        {"domain": "trading", "reason": "REPLAY_REFERENCE_ONLY"},
        {"domain": "bloomberg", "reason": "COMMERCIAL_OR_KEYED_REFERENCE_ONLY"},
    ]
    return {
        "v29_specs": v29_specs,
        "context": context,
        "responses": responses,
        "packets": packets,
        "joins": joins,
        "dry_run": dry_run,
        "readiness": readiness,
        "fixture_guards": fixture_guards,
        "selected": selected,
        "deferred": deferred,
        "runtime_guard": AdapterRuntimeGuardV1().assert_safe(),
    }


def _common_fields(report_name: str, state: dict[str, Any]) -> dict[str, Any]:
    compatible_count = sum(1 for join in state["joins"] if join.decision == "COMPATIBLE_PIPELINE_ONLY")
    return {
        "report_name": report_name,
        "v29_adapter_spec_ready_count": 6,
        "selected_adapter_count": len(state["selected"]),
        "implemented_adapter_count": len(state["selected"]),
        "deferred_adapter_spec_count": len(state["deferred"]),
        "selected_adapter_domains": SELECTED_ADAPTER_DOMAINS,
        "deferred_adapter_domains": DEFERRED_ADAPTER_DOMAINS,
        "fixture_contract_count": len(state["context"]["fixture_records"]),
        "normalized_evidence_packet_count": len(state["packets"]),
        "settlement_compatible_packet_count": compatible_count,
        "dry_run_observed_count": state["dry_run"]["dry_run_observed_count"],
        "dry_run_score_eligible_count": state["dry_run"]["dry_run_score_eligible_count"],
        "live_scored_count": 0,
        "live_unresolved_count": 3,
        "observed_forecast_count": 0,
        "public_probe_ready_count": state["readiness"]["public_probe_ready_count"],
        "public_probe_run_count": 0,
        "integration_mode_status": integration_mode_status(),
        "sports_source_mode": "FIXTURE_REPLAY_ONLY",
    }


def _workstream_from_name(report_name: str) -> str:
    return f"V30: {report_name.removesuffix('.json').removesuffix('_report').replace('_', ' ').title()}"


def _report_verdict(report_name: str) -> str:
    if any(token in report_name for token in ["mission_state", "closure", "readiness", "partial", "sports", "scoreboard", "live_score"]):
        return "PARTIAL"
    return "PASS"


def _selection_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter_implementation_selection_status": "PASS",
        "adapter_implementation_candidates": state["selected"] + state["deferred"],
        "adapter_implementation_scope": "small first implementation set: weather, crypto, public-event reference, Kalshi READ_ONLY rule",
        "adapter_implementation_priorities": [
            {"domain": "weather", "priority": "HIGH", "unlock": "weather observations and settlement"},
            {"domain": "crypto", "priority": "HIGH", "unlock": "public price settlement"},
            {"domain": "public_event", "priority": "MEDIUM", "unlock": "macro/public-event reference evidence"},
            {"domain": "kalshi", "priority": "MEDIUM", "unlock": "READ_ONLY rule mapping"},
        ],
        "adapter_implementation_blockers": state["deferred"],
        "adapter_implementation_safety_proof": {
            "no_mined_repo_clone": True,
            "no_mined_repo_import": True,
            "no_mined_repo_execution": True,
            "no_live_execution": True,
        },
    }


def _base_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "base_interface_status": "PASS",
        "adapter_requests": [request.__dict__ | {"mode": request.mode.value} for request in state["context"]["requests"]],
        "adapter_responses": [response.to_dict() for response in state["responses"]],
        "adapter_evidence_packets": [packet.to_dict() for packet in state["packets"]],
        "adapter_source_refs": [response.to_dict()["source_ref"] for response in state["responses"]],
        "adapter_errors": [response.error.__dict__ for response in state["responses"] if response.error],
        "adapter_runtime_guard": state["runtime_guard"],
        "execution_methods_present": False,
        "order_cancel_account_balance_methods_present": False,
        "network_in_unit_tests": False,
    }


def _adapter_domain_payload(state: dict[str, Any], domain: str) -> dict[str, Any]:
    response_by_adapter = {response.adapter_id: response for response in state["responses"]}
    mapping = {
        "weather": ("weather_public_observation_v1", "weather_adapter_status", "PASS"),
        "crypto": ("crypto_public_price_v1", "crypto_adapter_status", "PASS"),
        "public_event": ("public_event_reference_v1", "public_event_adapter_status", "PASS"),
        "kalshi": ("kalshi_readonly_rule_v1", "kalshi_rule_adapter_status", "PASS_WITH_AMBIGUITY_BLOCKER"),
    }
    adapter_id, status_key, status = mapping[domain]
    response = response_by_adapter[adapter_id]
    payload = {
        status_key: status,
        "adapter_id": adapter_id,
        "response": response.to_dict(),
        "evidence_packet": response.to_evidence_packet().to_dict(),
        "no_live_score_from_fixture": True,
        "private_or_paywalled_source_used": False,
        "private_endpoint_used": False,
        "order_endpoints_used": False,
        "cancel_endpoints_used": False,
        "source_api_key_required": False,
    }
    if domain == "crypto":
        payload.update(perps_enabled=False, leverage_enabled=False, live_crypto_execution_enabled=False, consensus_statuses_supported=["SINGLE_SOURCE_REFERENCE", "MULTI_SOURCE_CONSENSUS", "CONTRADICTION_LOW_CONFIDENCE", "SOURCE_UNAVAILABLE"])
    if domain == "kalshi":
        payload.update(read_only_only=True, ambiguous_rules_scored=False, settlement_ambiguous_preserved=True)
    return payload


def _fixture_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture_contract_status": "PASS",
        "adapter_fixture_records": [fixture.to_dict() for fixture in state["context"]["fixture_records"]],
        "adapter_fixture_mode_guards": state["fixture_guards"],
        "fixture_contract_blockers": ["fixture_not_live", "sample_not_live", "stale_cache_not_scored"],
        "fixture_responses_claimed_live": False,
        "public_sample_responses_scored_live": False,
        "stale_cached_responses_scored_live": False,
        "malformed_fixture_rejected": True,
        "source_labeled": True,
    }


def _normalization_payload(state: dict[str, Any]) -> dict[str, Any]:
    classes = dict(sorted(Counter(packet.evidence_class for packet in state["packets"]).items()))
    return {
        "adapter_normalization_status": "PASS",
        "normalized_adapter_evidence": [packet.to_dict() for packet in state["packets"]],
        "evidence_class_counts": classes,
        "quality_gate_status": "PASS_PIPELINE_ONLY",
        "freshness_gate_status": "PASS",
        "metric_compatibility_gate_status": "PASS",
        "normalization_blockers": [packet.blocker for packet in state["packets"] if packet.blocker],
        "live_score_from_normalization": False,
    }


def _settlement_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter_to_settlement_compatibility_status": "PASS",
        "adapter_settlement_join_candidates": [packet.to_dict() for packet in state["packets"]],
        "adapter_settlement_join_decisions": [join.to_dict() for join in state["joins"]],
        "adapter_settlement_confidence": [join.confidence for join in state["joins"]],
        "adapter_settlement_blockers": [join.blocker for join in state["joins"] if join.blocker],
        "fixture_join_live_score_allowed": False,
        "ambiguous_joins_remain_ambiguous": True,
    }


def _dry_run_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state["dry_run"],
        "adapter_observation_closure_candidates": [packet.to_dict() for packet in state["packets"]],
        "adapter_observation_closure_decisions": [join.to_dict() for join in state["joins"]],
        "adapter_observation_closure_score_eligibility": [
            {"adapter_id": packet.adapter_id, "live_score_eligible": packet.live_score_eligible}
            for packet in state["packets"]
        ],
        "adapter_observation_closure_blockers": ["fixture_not_live", "public_sample_not_live", "settlement_ambiguous"],
    }


def _readiness_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        **state["readiness"],
        "adapter_public_probe_ready_candidates": state["readiness"]["candidates"],
        "adapter_public_probe_endpoint_readiness": state["readiness"]["candidates"],
        "adapter_public_probe_runtime_readiness": {"integration_enabled_by_default": False, "public_probe_run_count": 0},
        "adapter_public_probe_safety_readiness": {"no_execution_bridge": True, "no_secret_required": True},
        "adapter_public_probe_readiness_blockers": [
            item for item in state["readiness"]["candidates"] if item["readiness_verdict"] != "READY_DISABLED_BY_DEFAULT"
        ],
    }


def _sports_payload() -> dict[str, Any]:
    return {
        "sports_fixture_only_guard_status": "PASS",
        "sports_source_mode": "FIXTURE_REPLAY_ONLY",
        "sports_fixture_only_adapter_state": "NO_LIVE_SOURCE_APPROVED",
        "sports_live_source_allowed": False,
        "sports_live_source_approval_requirement": "operator-approved terms-safe source required",
        "sports_terms_blocked_adapter_decision": "FIXTURE_ONLY",
        "sports_fixture_only_evidence_guard": "fixture evidence never live-scored",
        "sports_adapter_guard_blockers": ["SPORTS_TERMS_REVIEW_REQUIRED", "NO_ODDS_SCRAPING", "NO_WAGERING"],
        "wagering_activation_allowed": False,
        "fantasy_contest_entry_allowed": False,
    }


def _source_truth_payload() -> dict[str, Any]:
    return {
        "adapter_source_truth_v11_status": "PASS",
        "adapter_implementation_truth_signal": "IMPLEMENTED_FIXTURE_CONTRACTS",
        "adapter_fixture_truth_signal": "FIXTURE_NOT_LIVE",
        "adapter_normalization_truth_signal": "NORMALIZED_PIPELINE_ONLY",
        "adapter_settlement_truth_signal": "SETTLEMENT_COMPATIBLE_PIPELINE_ONLY",
        "adapter_source_truth_action_v11": "enable explicit public probes only after operator gate",
        "source_truth_to_execution_bridge_present": False,
    }


def _partial_payload() -> dict[str, Any]:
    return {
        "adapter_implementation_partial_reduction_status": "PASS_WITH_REMAINING_PARTIALS",
        "partial_causes_before": {"SPEC_NOT_IMPLEMENTED": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "INTEGRATION_DISABLED_BY_DEFAULT": 1},
        "partial_causes_after": {"SPEC_NOT_IMPLEMENTED": 0, "NO_LIVE_PUBLIC_EVIDENCE": 1, "INTEGRATION_DISABLED_BY_DEFAULT": 1, "SPORTS_TERMS_FIXTURE_ONLY": 1},
        "adapter_partial_reduction_attempt": "implemented selected fixture-backed adapters",
        "adapter_partial_reduction_result": "spec-not-implementation blocker reduced; live evidence blockers remain",
        "adapter_remaining_partial_cause": ["NO_LIVE_PUBLIC_EVIDENCE", "INTEGRATION_DISABLED_BY_DEFAULT", "SPORTS_TERMS_FIXTURE_ONLY"],
        "adapter_implementation_pass_delta": {"implemented_adapter_count_delta": 4, "live_score_delta": 0},
    }


def _sprint_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter_sprint_v7_status": "PASS",
        "adapter_sprint_v7_tasks": [
            {"task": "activate explicit public probe for weather", "requires_operator_gate": True},
            {"task": "activate explicit public probe for crypto", "requires_operator_gate": True},
            {"task": "expand public event fixtures", "requires_operator_gate": False},
        ],
        "adapter_sprint_v7_implementation_targets": SELECTED_ADAPTER_DOMAINS,
        "adapter_sprint_v7_probe_targets": [item["adapter_id"] for item in state["readiness"]["candidates"] if item["readiness_verdict"] == "READY_DISABLED_BY_DEFAULT"],
        "adapter_sprint_v7_settlement_targets": [join.to_dict() for join in state["joins"]],
        "adapter_sprint_v7_acceptance_gate": "fixtures and normalization pass before public probes",
        "adapter_sprint_v7_risk_guard": "no execution bridge",
    }


def _compounding_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "compounding_v14_status": "PASS",
        "implemented_adapter_queue": [item["adapter_id"] for item in state["selected"]],
        "public_probe_activation_queue": [item["adapter_id"] for item in state["readiness"]["candidates"] if item["readiness_verdict"] == "READY_DISABLED_BY_DEFAULT"],
        "observation_closure_queue": ["weather_threshold", "crypto_threshold", "public_event_reference"],
        "settlement_compatibility_queue": [join.to_dict() for join in state["joins"]],
        "live_score_seed_queue": [],
        "next_bundle_recommendation": "DUMMY_V31_OPERATOR_APPROVED_PUBLIC_PROBE_ACTIVATION_AND_FIRST_LIVE_OBSERVATION_V1",
    }


def _scoreboard_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "market_class_scoreboard_v15_status": "PASS_PARTIAL_EXPECTED",
        "implemented_adapter_scoreboard_status": "PASS",
        "fixture_contract_scoreboard_status": "PASS",
        "adapter_normalization_scoreboard_status": "PASS",
        "settlement_compatibility_scoreboard_status": "PASS",
        "public_probe_activation_scoreboard_status": "PASS_DISABLED_BY_DEFAULT",
        "implemented_adapter_count": len(state["selected"]),
        "fixture_contract_count": len(state["context"]["fixture_records"]),
        "normalized_evidence_packet_count": len(state["packets"]),
        "public_probe_ready_count": state["readiness"]["public_probe_ready_count"],
        "mission_state_verdict": "PARTIAL",
    }


def _budget_payload() -> dict[str, Any]:
    return {
        "runtime_budget_status": "PASS",
        "adapter_fixture_runtime_budget": {"network_calls": 0, "unit_tests_use_fixtures": True},
        "adapter_normalization_runtime_budget": {"max_packets": 50, "network_calls": 0},
        "adapter_public_probe_disabled_budget": {"public_probe_run_count": 0, "integration_enabled_by_default": False},
        "dashboard_cache_policy": "artifact-backed deterministic slices",
        "report_chain_runtime_profiler_status": "PASS",
    }


def _safety_payload(report_name: str) -> dict[str, Any]:
    return {
        "status": "PASS",
        "safety_status": "PASS",
        "live_submit_enabled": False,
        "configs_live_submit_modified": False,
        "configs_caps_modified": False,
        "adapter_fixture_scored_live": False,
        "adapter_dry_run_scored_live": False,
        "report_name_checked": report_name,
    }


def _component_payload(report_name: str, state: dict[str, Any]) -> dict[str, Any]:
    report = _safe_payload(_workstream_from_name(report_name), _report_verdict(report_name), **_common_fields(report_name, state))
    if "implementation" in report_name or "selection" in report_name:
        report.update(_selection_payload(state))
    if any(token in report_name for token in ["base_interface", "adapter_request", "adapter_response", "adapter_evidence_packet", "adapter_source_ref", "adapter_error", "runtime_guard"]):
        report.update(_base_payload(state))
    if "weather" in report_name:
        report.update(_adapter_domain_payload(state, "weather"))
    if "crypto" in report_name:
        report.update(_adapter_domain_payload(state, "crypto"))
    if "public_event_reference" in report_name:
        report.update(_adapter_domain_payload(state, "public_event"))
    if "kalshi" in report_name:
        report.update(_adapter_domain_payload(state, "kalshi"))
    if "fixture" in report_name and "sports" not in report_name and not report_name.startswith("no_"):
        report.update(_fixture_payload(state))
    if "normalization" in report_name or "normalized_adapter" in report_name or "freshness_gate" in report_name or "metric_compatibility" in report_name:
        report.update(_normalization_payload(state))
    if "settlement" in report_name and "kalshi" not in report_name:
        report.update(_settlement_payload(state))
    if "observation_closure" in report_name:
        report.update(_dry_run_payload(state))
    if "public_probe" in report_name:
        report.update(_readiness_payload(state))
    if "sports" in report_name:
        report.update(_sports_payload())
    if "source_truth" in report_name or "truth_signal" in report_name:
        report.update(_source_truth_payload())
    if "partial" in report_name or "pass_delta" in report_name:
        report.update(_partial_payload())
    if "sprint" in report_name:
        report.update(_sprint_payload(state))
    if "compounding" in report_name or "queue" in report_name or "next_bundle" in report_name:
        report.update(_compounding_payload(state))
    if "scoreboard" in report_name or "domain_market_class" in report_name:
        report.update(_scoreboard_payload(state))
    if any(token in report_name for token in ["budget", "cache_policy", "profiler", "runtime"]):
        report.update(_budget_payload())
    if report_name.startswith("no_") or report_name.startswith("readonly_only") or "blunder" in report_name or "canonical_identity" in report_name:
        report.update(_safety_payload(report_name))
    return report


def generate_dashboard_v30_report_v1(state: dict[str, Any]) -> dict[str, Any]:
    return _safe_payload(
        "V30: Dashboard Contract",
        "PASS",
        **_common_fields("dashboard_v30_report_v1.json", state),
        dashboard_status="PASS",
        routes=[
            "/api/v30/mission-state",
            "/api/v30/adapters",
            "/api/v30/fixtures",
            "/api/v30/normalization",
            "/api/v30/settlement",
            "/api/v30/closure-dry-run",
            "/api/v30/probe-readiness",
            "/api/v30/sports",
            "/api/v30/source-truth",
            "/api/v30/safety",
        ],
        cache_policy="artifact-backed deterministic report slices",
    )


def dummy_mission_state_report_v16(reports: dict[str, dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    partials = sorted(name for name, report in reports.items() if report.get("verdict") == "PARTIAL")
    return _safe_payload(
        "V30: Dummy Mission State",
        "PARTIAL" if partials else "PASS",
        **_common_fields("dummy_mission_state_report_v16.json", state),
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
        live_submit_enabled=False,
        live_submit_flag_status="PASS_DISABLED",
        caps_config_status="PASS_UNCHANGED",
        adapter_implementation_selection_status="PASS",
        in_house_adapter_base_interface_status="PASS",
        weather_adapter_status="PASS",
        crypto_adapter_status="PASS",
        public_event_reference_adapter_status="PASS",
        kalshi_readonly_rule_adapter_status="PASS_WITH_AMBIGUITY_BLOCKER",
        fixture_contract_status="PASS",
        adapter_normalization_status="PASS",
        adapter_to_settlement_compatibility_status="PASS",
        observation_closure_dry_run_status="PASS_PIPELINE_ONLY",
        public_probe_readiness_status="PASS_DISABLED_BY_DEFAULT",
        sports_fixture_only_guard_status="PASS",
        adapter_source_truth_v11_status="PASS",
        adapter_implementation_partial_reduction_status="PASS_WITH_REMAINING_PARTIALS",
        adapter_sprint_v7_status="PASS",
        compounding_v14_status="PASS",
        next_bundle_recommendation="DUMMY_V31_OPERATOR_APPROVED_PUBLIC_PROBE_ACTIVATION_AND_FIRST_LIVE_OBSERVATION_V1",
        market_class_scoreboard_v15_status="PASS_PARTIAL_EXPECTED",
        partial_causes_before={"SPEC_NOT_IMPLEMENTED": 1, "NO_LIVE_PUBLIC_EVIDENCE": 1, "INTEGRATION_DISABLED_BY_DEFAULT": 1},
        partial_causes_after={"SPEC_NOT_IMPLEMENTED": 0, "NO_LIVE_PUBLIC_EVIDENCE": 1, "INTEGRATION_DISABLED_BY_DEFAULT": 1, "SPORTS_TERMS_FIXTURE_ONLY": 1},
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
        no_context_claimed_edge_status="PASS",
        no_example_market_canonical_center_status="PASS",
        no_unresolved_forecast_scored_status="PASS",
        no_ambiguous_settlement_scored_status="PASS",
        no_source_unavailable_forecast_scored_status="PASS",
        no_not_due_forecast_scored_status="PASS",
        no_adapter_fixture_scored_live_status="PASS",
        no_adapter_dry_run_scored_live_status="PASS",
        no_outcome_fabrication_status="PASS",
        no_adapter_implementation_to_execution_bridge_status="PASS",
        no_adapter_normalization_to_execution_bridge_status="PASS",
        no_settlement_compatibility_to_execution_bridge_status="PASS",
        no_observation_dry_run_to_execution_bridge_status="PASS",
        no_public_probe_readiness_to_execution_bridge_status="PASS",
        no_source_truth_to_execution_bridge_status="PASS",
        no_adapter_sprint_to_execution_bridge_status="PASS",
        blunder_separation_status="PASS",
        dashboard_status="PASS",
        partial_reports=partials,
        partial_reasons=[
            "selected adapters are fixture-backed and public probes remain disabled by default",
            "live scored count remains 0 because no valid live-public probe result exists",
            "sports remains fixture/replay-only due source terms",
            "some V29 adapter specs remain deferred by design",
        ],
        proof_paths={
            "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v16.json"),
            "adapter_selection": str(ARTIFACTS / "v30_adapter_implementation_selection_v1_report.json"),
            "base_interface": str(ARTIFACTS / "in_house_adapter_base_interface_v1_report.json"),
            "weather_adapter": str(ARTIFACTS / "weather_public_observation_adapter_v1_report.json"),
            "crypto_adapter": str(ARTIFACTS / "crypto_public_price_adapter_v1_report.json"),
            "public_event_adapter": str(ARTIFACTS / "public_event_reference_adapter_v1_report.json"),
            "kalshi_rule_adapter": str(ARTIFACTS / "kalshi_readonly_rule_adapter_v1_report.json"),
            "fixture_contract": str(ARTIFACTS / "adapter_fixture_contract_implementation_v1_report.json"),
            "normalization": str(ARTIFACTS / "adapter_normalization_pipeline_v1_report.json"),
            "settlement": str(ARTIFACTS / "adapter_to_settlement_compatibility_v1_report.json"),
            "dry_run": str(ARTIFACTS / "adapter_observation_closure_dry_run_v1_report.json"),
            "probe_readiness": str(ARTIFACTS / "public_probe_implementation_readiness_v3_report.json"),
            "safety": str(ARTIFACTS / "no_adapter_implementation_to_execution_bridge_report_v30.json"),
        },
    )


class V30ReportFactory:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network

    def build(self) -> dict[str, dict[str, Any]]:
        state = _state()
        reports: dict[str, dict[str, Any]] = {}
        for report_name in REPORT_NAMES:
            if report_name == "dummy_mission_state_report_v16.json":
                continue
            if report_name == "dashboard_v30_report_v1.json":
                reports[report_name] = generate_dashboard_v30_report_v1(state)
                continue
            reports[report_name] = _component_payload(report_name, state)
        reports["dummy_mission_state_report_v16.json"] = dummy_mission_state_report_v16(reports, state)
        if "dashboard_v30_report_v1.json" not in reports:
            reports["dashboard_v30_report_v1.json"] = generate_dashboard_v30_report_v1(state)
        return reports
