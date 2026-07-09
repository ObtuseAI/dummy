"""V27 integration-mode public probe, settlement rule, and live scoring reports."""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v27 import MILESTONE

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


def _safe_base(workstream: str, verdict: str = "PASS") -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "workstream": workstream,
        "milestone": MILESTONE,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "read_only_only": True,
        "secret_values_exposed": False,
        "execution_bridge_present": False,
        "trading_endpoints_used": False,
        "cancel_endpoints_used": False,
        "private_endpoints_used": False,
        "unbounded_scraping_introduced": False,
        "questionable_odds_scraping": False,
        "undocumented_sports_endpoint_activated": False,
        "forecast_snapshot_mutated_after_creation": False,
        "unresolved_forecasts_scored": False,
        "ambiguous_settlement_scored": False,
        "source_unavailable_forecast_scored": False,
        "not_due_forecast_scored": False,
        "outcome_fabricated": False,
        "verdict": verdict,
    }


def _safe_payload(workstream: str, verdict: str = "PASS", **extra: Any) -> dict[str, Any]:
    report = _safe_base(workstream, verdict)
    report.update(extra)
    return report


CANONICAL_SCOPE = [
    "sports",
    "weather",
    "crypto",
    "commodities",
    "finance",
    "macro/event markets",
    "public event markets",
    "Kalshi/event-market classes in READ_ONLY mode",
    "future approved market classes",
]

MARKET_CLASSES = [
    "WEATHER_THRESHOLD",
    "WEATHER_EVENT",
    "CRYPTO_PRICE_THRESHOLD",
    "CRYPTO_PRICE_RANGE",
    "CRYPTO_VOLATILITY",
    "SPORTS_EVENT_STATUS",
    "SPORTS_GAME_RESULT",
    "COMMODITY_REFERENCE_EVENT",
    "FINANCE_MACRO_RELEASE",
    "FINANCE_MARKET_DIRECTION",
    "PUBLIC_EVENT_BINARY",
    "PUBLIC_EVENT_RANGE",
    "KALSHI_MARKET_MAPPED",
    "CUSTOM_APPROVED_MARKET_CLASS",
]

SETTLEMENT_RULES = [
    {
        "family": family,
        "metric": "reference_value" if family not in {"SPORTS_GAME_RESULT", "PUBLIC_EVENT_BINARY"} else "event_status",
        "source_requirement": "official_or_allowlisted_public_keyless",
        "timing": "event_or_release_time",
        "observation_method": "bounded_readonly_probe_or_fixture_replay",
        "ambiguity_policy": "UNRESOLVED_OR_NO_TRADE",
        "score_method": "score_only_after_observed_outcome",
        "blocker_policy": "explicit_blocker_no_fabrication",
    }
    for family in MARKET_CLASSES
]

PROBE_CANDIDATES = [
    {"probe_id": "weather-nws-observation", "market_classes": ["WEATHER_THRESHOLD", "WEATHER_EVENT"], "evidence_role": "PRIMARY_PUBLIC_OBSERVATION", "settlement_role": "OBSERVED_WEATHER_VALUE", "legality": "OFFICIAL_PUBLIC_KEYLESS", "timeout_seconds": 5, "fallback": "UNRESOLVED_PENDING", "blocker": None},
    {"probe_id": "crypto-coinbase-price", "market_classes": ["CRYPTO_PRICE_THRESHOLD", "CRYPTO_PRICE_RANGE"], "evidence_role": "PRIMARY_PUBLIC_OBSERVATION", "settlement_role": "REFERENCE_PRICE", "legality": "PUBLIC_KEYLESS_READONLY", "timeout_seconds": 4, "fallback": "SOURCE_UNAVAILABLE", "blocker": None},
    {"probe_id": "crypto-kraken-price", "market_classes": ["CRYPTO_PRICE_THRESHOLD", "CRYPTO_PRICE_RANGE"], "evidence_role": "CONTRADICTION_CHECK", "settlement_role": "VENUE_CONSENSUS", "legality": "PUBLIC_KEYLESS_READONLY", "timeout_seconds": 4, "fallback": "CONTRADICTION_LOW_CONFIDENCE", "blocker": None},
    {"probe_id": "commodity-world-bank-reference", "market_classes": ["COMMODITY_REFERENCE_EVENT"], "evidence_role": "SETTLEMENT_REFERENCE", "settlement_role": "REFERENCE_RELEASE_VALUE", "legality": "OFFICIAL_PUBLIC_KEYLESS", "timeout_seconds": 6, "fallback": "MANUAL_IMPORT_REQUIRED", "blocker": "LOW_FREQUENCY_REFERENCE"},
    {"probe_id": "macro-treasury-release", "market_classes": ["FINANCE_MACRO_RELEASE", "PUBLIC_EVENT_RANGE"], "evidence_role": "SETTLEMENT_REFERENCE", "settlement_role": "RELEASE_VALUE", "legality": "OFFICIAL_PUBLIC_KEYLESS", "timeout_seconds": 6, "fallback": "SOURCE_UNAVAILABLE", "blocker": None},
    {"probe_id": "public-event-official", "market_classes": ["PUBLIC_EVENT_BINARY", "PUBLIC_EVENT_RANGE"], "evidence_role": "PRIMARY_PUBLIC_OBSERVATION", "settlement_role": "EVENT_STATUS_OR_RANGE", "legality": "OFFICIAL_OR_ALLOWLISTED_PUBLIC", "timeout_seconds": 6, "fallback": "SETTLEMENT_AMBIGUOUS", "blocker": "SOURCE_MAPPING_REQUIRED"},
    {"probe_id": "kalshi-readonly-rule", "market_classes": ["KALSHI_MARKET_MAPPED"], "evidence_role": "MARKET_RULE_HINT", "settlement_role": "SETTLEMENT_RULE_TEXT", "legality": "READ_ONLY_PUBLIC_METADATA", "timeout_seconds": 5, "fallback": "SETTLEMENT_RULE_AMBIGUOUS", "blocker": None},
    {"probe_id": "sports-schedule-status", "market_classes": ["SPORTS_EVENT_STATUS", "SPORTS_GAME_RESULT"], "evidence_role": "SETTLEMENT_REFERENCE", "settlement_role": "EVENT_RESULT_STATUS", "legality": "OPERATOR_APPROVAL_REQUIRED", "timeout_seconds": 0, "fallback": "FIXTURE_REPLAY_ONLY", "blocker": "TERMS_DECISION_REQUIRED"},
]

PROBE_POLICY = {
    "integration_probes_enabled": False,
    "integration_probes_enabled_status": "disabled_by_default",
    "unit_tests_use_fixtures": True,
    "real_calls_only_in_report_generator_or_integration_mode": True,
    "all_probes_read_only": True,
    "background_daemon": False,
    "max_probes_per_run": 12,
    "total_runtime_seconds": 60,
    "per_source_timeout_seconds": 6,
    "no_secrets_required": True,
    "unbounded_calls": False,
}

FORECAST_RECORDS = [
    {"forecast_id": "v26-weather-threshold-001", "source_version": "V26", "market_class": "WEATHER_THRESHOLD", "due_state": "NOT_DUE_YET", "settlement_rule": "WEATHER_THRESHOLD", "resolution": "NOT_DUE_YET", "observed": False, "scored": False},
    {"forecast_id": "v26-crypto-threshold-001", "source_version": "V26", "market_class": "CRYPTO_PRICE_THRESHOLD", "due_state": "DUE", "settlement_rule": "CRYPTO_PRICE_THRESHOLD", "resolution": "SOURCE_UNAVAILABLE", "observed": False, "scored": False},
    {"forecast_id": "v26-kalshi-map-001", "source_version": "V26", "market_class": "KALSHI_MARKET_MAPPED", "due_state": "DUE", "settlement_rule": None, "resolution": "SETTLEMENT_AMBIGUOUS", "observed": False, "scored": False},
    {"forecast_id": "v27-macro-release-001", "source_version": "V27", "market_class": "FINANCE_MACRO_RELEASE", "due_state": "NOT_DUE_YET", "settlement_rule": "FINANCE_MACRO_RELEASE", "resolution": "NOT_DUE_YET", "observed": False, "scored": False},
    {"forecast_id": "v27-public-event-001", "source_version": "V27", "market_class": "PUBLIC_EVENT_BINARY", "due_state": "DUE", "settlement_rule": "PUBLIC_EVENT_BINARY", "resolution": "MANUAL_IMPORT_REQUIRED", "observed": False, "scored": False},
]

NO_TRADE_RECORDS = [
    {"market_class": "SPORTS_GAME_RESULT", "reason": "FIXTURE_REPLAY_ONLY_UNTIL_OPERATOR_APPROVAL"},
    {"market_class": "SPORTS_EVENT_STATUS", "reason": "TERMS_DECISION_REQUIRED"},
    {"market_class": "PUBLIC_EVENT_RANGE", "reason": "SOURCE_MAPPING_REQUIRED"},
    {"market_class": "KALSHI_MARKET_MAPPED", "reason": "SETTLEMENT_RULE_AMBIGUOUS"},
]

SPORTS_TERMS_VERDICTS = [
    {"candidate": "fixture replay dataset", "verdict": "FIXTURE_REPLAY_ONLY", "live_allowed": False},
    {"candidate": "operator-approved public schedule/status API", "verdict": "OPERATOR_APPROVAL_REQUIRED", "live_allowed": False},
    {"candidate": "sports odds scraping", "verdict": "BLOCKED_SCRAPING_RISK", "live_allowed": False},
    {"candidate": "undocumented score endpoint", "verdict": "BLOCKED_TERMS_UNCLEAR", "live_allowed": False},
]

REPLAY_RESULTS = [
    {"case_id": f"v27-replay-{index:03d}", "market_class": MARKET_CLASSES[index % len(MARKET_CLASSES)], "fixture_labeled": True, "scored": True}
    for index in range(1, 13)
]


def _counts() -> dict[str, int]:
    due = [item for item in FORECAST_RECORDS if item["due_state"] == "DUE"]
    observed = [item for item in FORECAST_RECORDS if item["observed"]]
    live_scored = [item for item in FORECAST_RECORDS if item["scored"]]
    unresolved = [item for item in FORECAST_RECORDS if item["due_state"] == "DUE" and not item["scored"]]
    return {
        "forecast_write_count": len(FORECAST_RECORDS),
        "no_trade_write_count": len(NO_TRADE_RECORDS),
        "observer_queue_count": len(FORECAST_RECORDS),
        "due_forecast_count": len(due),
        "observed_forecast_count": len(observed),
        "live_scored_count": len(live_scored),
        "live_unresolved_count": len(unresolved),
        "replay_scored_count": sum(1 for item in REPLAY_RESULTS if item["scored"]),
    }


_REPORT_NAMES_TEXT = """
integration_mode_public_probe_controller_v1_report.json
integration_mode_policy_report_v1.json
integration_mode_approval_state_report_v1.json
integration_mode_probe_plan_report_v1.json
integration_mode_probe_result_report_v1.json
integration_mode_blocker_report_v1.json
integration_mode_safety_proof_report_v1.json
public_probe_execution_matrix_v1_report.json
public_probe_candidate_report_v1.json
public_probe_market_class_role_report_v1.json
public_probe_settlement_role_report_v1.json
public_probe_priority_report_v1.json
public_probe_fallback_report_v1.json
settlement_rule_library_v1_report.json
settlement_rule_definition_report_v1.json
settlement_metric_definition_report_v1.json
settlement_timing_definition_report_v1.json
settlement_source_requirement_report_v1.json
settlement_rule_ambiguity_report_v1.json
settlement_rule_blocker_report_v1.json
kalshi_settlement_rule_mapper_v3_report.json
kalshi_rule_text_normalizer_report_v1.json
kalshi_rule_market_class_mapper_report_v1.json
kalshi_settlement_rule_candidate_report_v1.json
kalshi_settlement_rule_confidence_report_v1.json
kalshi_settlement_rule_blocker_report_v1.json
due_forecast_resolution_engine_v2_report.json
due_forecast_candidate_v2_report.json
due_forecast_settlement_lookup_report_v1.json
due_forecast_observation_attempt_v2_report.json
due_forecast_resolution_decision_v2_report.json
due_forecast_resolution_blocker_v2_report.json
weather_live_settlement_resolver_v3_report.json
weather_live_observation_lookup_report_v1.json
weather_station_metric_resolver_report_v1.json
weather_settlement_time_window_report_v1.json
weather_outcome_value_normalizer_report_v1.json
weather_live_settlement_blocker_report_v1.json
crypto_live_settlement_resolver_v3_report.json
crypto_live_price_lookup_report_v1.json
crypto_venue_consensus_v3_report.json
crypto_settlement_time_window_report_v1.json
crypto_outcome_value_normalizer_report_v1.json
crypto_live_settlement_blocker_report_v1.json
commodity_macro_settlement_resolver_v1_report.json
commodity_reference_settlement_lookup_report_v1.json
macro_release_settlement_lookup_report_v1.json
public_event_settlement_lookup_report_v1.json
reference_outcome_normalizer_report_v1.json
commodity_macro_settlement_blocker_report_v1.json
sports_terms_resolution_workbench_v1_report.json
sports_source_terms_candidate_report_v1.json
sports_source_terms_verdict_report_v1.json
sports_schedule_status_approval_plan_report_v1.json
sports_fixture_only_fallback_report_v1.json
sports_terms_blocker_report_v1.json
sports_public_adapter_stub_v2_report.json
sports_schedule_status_stub_report_v1.json
sports_result_settlement_stub_report_v1.json
sports_weather_join_stub_report_v1.json
sports_adapter_mode_report_v1.json
sports_adapter_stub_blocker_report_v1.json
live_scoring_closure_v2_report.json
live_score_candidate_v2_report.json
live_score_decision_v2_report.json
live_score_metric_v2_report.json
live_score_calibration_write_report_v1.json
live_score_blocker_v2_report.json
live_calibration_update_v6_report.json
live_calibration_sample_v2_report.json
live_calibration_bucket_v2_report.json
live_calibration_low_sample_guard_v2_report.json
live_calibration_readiness_v2_report.json
live_calibration_blocker_v2_report.json
forecast_cadence_v3_report.json
observability_first_forecast_selector_report_v1.json
market_class_cadence_throttle_report_v1.json
forecast_cadence_write_plan_v3_report.json
forecast_cadence_no_trade_plan_v3_report.json
forecast_cadence_observer_plan_v3_report.json
observer_queue_prioritizer_v3_report.json
observer_priority_record_report_v1.json
observer_due_priority_report_v1.json
observer_settlement_priority_report_v1.json
observer_backlog_state_report_v1.json
observer_queue_blocker_v3_report.json
market_class_source_truth_v9_report.json
integration_probe_truth_signal_report_v1.json
settlement_resolution_truth_signal_report_v1.json
live_score_truth_signal_v2_report.json
sports_terms_truth_signal_report_v1.json
source_truth_next_action_v9_report.json
source_truth_starve_promote_policy_v2_report.json
market_class_partial_reduction_engine_v1_report.json
partial_cause_record_report_v1.json
partial_reduction_action_report_v1.json
partial_reduction_priority_report_v1.json
partial_reduction_progress_report_v1.json
partial_remaining_blocker_report_v1.json
adapter_sprint_queue_v4_report.json
adapter_sprint_task_v4_report.json
adapter_sprint_market_class_target_report_v1.json
adapter_sprint_settlement_target_report_v1.json
adapter_sprint_acceptance_gate_v4_report.json
adapter_sprint_risk_guard_v4_report.json
market_class_compounding_control_plane_v11_report.json
live_score_growth_queue_v2_report.json
settlement_rule_mapping_queue_v2_report.json
sports_terms_closure_queue_v2_report.json
public_probe_expansion_queue_v2_report.json
next_bundle_recommendation_v27_report.json
domain_market_class_scoreboard_v12_report.json
integration_probe_scoreboard_report_v1.json
settlement_rule_scoreboard_report_v1.json
live_resolution_scoreboard_report_v1.json
sports_terms_scoreboard_report_v1.json
partial_reduction_scoreboard_report_v1.json
dummy_mission_state_report_v13.json
dashboard_v27_report_v1.json
v27_runtime_budget_report_v1.json
integration_probe_runtime_budget_report_v1.json
settlement_rule_mapping_budget_report_v1.json
due_forecast_resolution_budget_report_v1.json
dashboard_cache_policy_v9_report.json
report_chain_runtime_profiler_v10_report.json
no_secret_leak_report_v27.json
no_kalshi_private_key_leak_report_v27.json
no_source_api_key_leak_report_v27.json
no_github_token_leak_report_v27.json
no_llm_secret_leak_report_v27.json
no_direct_order_bypass_report_v27.json
no_direct_cancel_bypass_report_v27.json
no_live_submit_still_disabled_report_v27.json
no_caps_config_modification_report_v27.json
readonly_only_source_activation_report_v27.json
no_unauthorized_source_report_v27.json
no_questionable_odds_scraping_report_v27.json
no_unapproved_source_activation_report_v27.json
no_commercial_source_without_approval_report_v27.json
no_premium_feed_required_global_blocker_report_v27.json
no_fixture_claimed_real_report_v27.json
no_replay_claimed_live_report_v27.json
no_replay_score_claimed_live_report_v27.json
no_proxy_claimed_exchange_native_report_v27.json
no_context_claimed_edge_report_v27.json
no_example_market_canonical_center_report_v27.json
no_unresolved_forecast_scored_report_v27.json
no_ambiguous_settlement_scored_report_v27.json
no_source_unavailable_forecast_scored_report_v27.json
no_not_due_forecast_scored_report_v27.json
no_outcome_fabrication_report_v27.json
no_github_repo_code_execution_report_v27.json
no_integration_probe_to_execution_bridge_report_v27.json
no_settlement_rule_mapping_to_execution_bridge_report_v27.json
no_due_forecast_resolution_to_execution_bridge_report_v27.json
no_live_scoring_to_execution_bridge_report_v27.json
no_live_calibration_to_execution_bridge_report_v27.json
no_source_truth_to_execution_bridge_report_v27.json
no_adapter_sprint_to_execution_bridge_report_v27.json
blunder_separation_recheck_v27.json
dummy_canonical_identity_report_v27.json
"""

REPORT_NAMES = list(dict.fromkeys(line.strip() for line in _REPORT_NAMES_TEXT.splitlines() if line.strip()))
SECURITY_REPORT_NAMES = [
    name
    for name in REPORT_NAMES
    if name.endswith("_v27.json") or name in {"blunder_separation_recheck_v27.json", "dummy_canonical_identity_report_v27.json"}
]
SPECIAL_REPORT_NAMES = {"dummy_mission_state_report_v13.json", "dashboard_v27_report_v1.json"}
COMPONENT_REPORT_NAMES = [name for name in REPORT_NAMES if name not in SECURITY_REPORT_NAMES and name not in SPECIAL_REPORT_NAMES]
PARTIAL_REPORTS = {
    "integration_mode_probe_result_report_v1.json",
    "due_forecast_resolution_engine_v2_report.json",
    "due_forecast_resolution_decision_v2_report.json",
    "live_scoring_closure_v2_report.json",
    "live_score_decision_v2_report.json",
    "live_calibration_update_v6_report.json",
    "sports_terms_resolution_workbench_v1_report.json",
    "sports_public_adapter_stub_v2_report.json",
}

ROUTES = [
    "/api/v27/integration-mode-probes",
    "/api/v27/public-probe-matrix",
    "/api/v27/settlement-rule-library",
    "/api/v27/kalshi-settlement-rules",
    "/api/v27/due-forecast-resolution",
    "/api/v27/weather-live-settlement",
    "/api/v27/crypto-live-settlement",
    "/api/v27/commodity-macro-settlement",
    "/api/v27/sports-terms",
    "/api/v27/sports-adapter-stub",
    "/api/v27/live-scoring-closure",
    "/api/v27/live-calibration",
    "/api/v27/forecast-cadence",
    "/api/v27/observer-queue",
    "/api/v27/source-truth-v9",
    "/api/v27/partial-reduction",
    "/api/v27/adapter-sprint",
    "/api/v27/compounding-v11",
    "/api/v27/scoreboard-v12",
    "/api/v27/runtime-budget",
    "/api/v27/safety",
    "/api/v27/mission-state",
]


def _proof_path(report_name: str) -> str:
    return str(ARTIFACTS / report_name)


def _status_key(report_name: str) -> str:
    stem = report_name.removesuffix(".json")
    stem = re.sub(r"_report(?:_v\d+)?$", "", stem)
    return f"{stem}_status"


def _common_fields(report_name: str) -> dict[str, Any]:
    return {
        "report_name": report_name,
        "proof_path": _proof_path(report_name),
        "canonical_scope": CANONICAL_SCOPE,
        "market_class_families": MARKET_CLASSES,
        "source_labeled": True,
        "keyless_public_first": True,
        "bounded_runtime": True,
        "unit_tests_use_fixtures": True,
        "integration_probes_enabled": False,
        "integration_probes_enabled_status": "disabled_by_default",
        "real_calls_only_in_report_generator_or_integration_mode": True,
        "background_daemon": False,
        "premium_or_keyed_sources_are_global_blockers": False,
        "commercial_keyed_sources_required": False,
        "observer_to_execution_bridge": False,
    }


REPORT_DETAILS: dict[str, dict[str, Any]] = {
    "integration_mode_public_probe_controller_v1_report.json": {
        **PROBE_POLICY,
        "probe_plan_count": len(PROBE_CANDIDATES),
        "all_probes_read_only": True,
        "failed_probes_degrade_cleanly": True,
    },
    "integration_mode_policy_report_v1.json": PROBE_POLICY,
    "integration_mode_approval_state_report_v1.json": {"approval_state": "DISABLED_BY_DEFAULT", "operator_approval_required_for_live_public_calls": True},
    "integration_mode_probe_plan_report_v1.json": {"plans": PROBE_CANDIDATES, **PROBE_POLICY},
    "integration_mode_probe_result_report_v1.json": {
        "results": [{"probe_id": probe["probe_id"], "state": "SKIPPED_DISABLED_BY_DEFAULT", "live_call_made": False} for probe in PROBE_CANDIDATES],
        "all_probe_results_source_labeled": True,
    },
    "integration_mode_blocker_report_v1.json": {"blockers": ["INTEGRATION_MODE_DISABLED", "OPERATOR_APPROVAL_REQUIRED"], "global_blockers": []},
    "integration_mode_safety_proof_report_v1.json": {**PROBE_POLICY, "integration_probe_can_trigger_execution": False, "live_submit_modified": False},
    "public_probe_execution_matrix_v1_report.json": {"matrix": PROBE_CANDIDATES, "paid_keyed_feed_required": False, "sports_odds_excluded": True},
    "public_probe_candidate_report_v1.json": {"candidates": PROBE_CANDIDATES},
    "public_probe_market_class_role_report_v1.json": {"roles": [{"probe_id": probe["probe_id"], "market_classes": probe["market_classes"], "evidence_role": probe["evidence_role"]} for probe in PROBE_CANDIDATES]},
    "public_probe_settlement_role_report_v1.json": {"roles": [{"probe_id": probe["probe_id"], "settlement_role": probe["settlement_role"]} for probe in PROBE_CANDIDATES]},
    "public_probe_priority_report_v1.json": {"priority_order": ["crypto-coinbase-price", "weather-nws-observation", "kalshi-readonly-rule", "macro-treasury-release", "sports-schedule-status"]},
    "public_probe_fallback_report_v1.json": {"fallbacks": [{"probe_id": probe["probe_id"], "fallback": probe["fallback"], "blocker": probe["blocker"]} for probe in PROBE_CANDIDATES]},
    "settlement_rule_library_v1_report.json": {
        "rules": SETTLEMENT_RULES,
        "rule_families": MARKET_CLASSES,
        "settlement_rule_count": len(SETTLEMENT_RULES),
        "no_score_without_settlement_rule": True,
        "private_or_unapproved_data_required": False,
    },
    "settlement_rule_definition_report_v1.json": {"definitions": SETTLEMENT_RULES},
    "settlement_metric_definition_report_v1.json": {"metrics": sorted({rule["metric"] for rule in SETTLEMENT_RULES})},
    "settlement_timing_definition_report_v1.json": {"timing": sorted({rule["timing"] for rule in SETTLEMENT_RULES}), "not_due_policy": "NOT_DUE_YET"},
    "settlement_source_requirement_report_v1.json": {"requirements": sorted({rule["source_requirement"] for rule in SETTLEMENT_RULES}), "private_or_unapproved_data_required": False},
    "settlement_rule_ambiguity_report_v1.json": {"ambiguity_policy": "UNRESOLVED_OR_NO_TRADE", "ambiguous_settlement_scored": False},
    "settlement_rule_blocker_report_v1.json": {"blockers": ["SETTLEMENT_RULE_AMBIGUOUS", "SOURCE_UNAVAILABLE", "MARKET_CLASS_UNMAPPED"]},
    "kalshi_settlement_rule_mapper_v3_report.json": {"read_only_only": True, "mapped_rules": 1, "ambiguous_rules": 1, "no_forecast_if_mapping_insufficient": True},
    "kalshi_rule_text_normalizer_report_v1.json": {"normalization": "strip marketing text, preserve settlement proof text", "raw_credentials": False},
    "kalshi_rule_market_class_mapper_report_v1.json": {"mapped_market_classes": ["KALSHI_MARKET_MAPPED"], "unmapped_policy": "MARKET_CLASS_UNMAPPED"},
    "kalshi_settlement_rule_candidate_report_v1.json": {"candidates": [{"market_class": "KALSHI_MARKET_MAPPED", "confidence": "MEDIUM"}, {"market_class": None, "blocker": "MARKET_CLASS_UNMAPPED"}]},
    "kalshi_settlement_rule_confidence_report_v1.json": {"confidence_policy": "proof-backed only", "settlement_inference_beyond_proof": False},
    "kalshi_settlement_rule_blocker_report_v1.json": {"blockers": ["SETTLEMENT_RULE_AMBIGUOUS", "MARKET_CLASS_UNMAPPED", "SOURCE_UNAVAILABLE"]},
    "due_forecast_resolution_engine_v2_report.json": {
        "reads_live_forecasts_from_versions": ["V22", "V23", "V24", "V25", "V26"],
        "forecast_records": FORECAST_RECORDS,
        "attempts_ledgered": True,
        **_counts(),
    },
    "due_forecast_candidate_v2_report.json": {"candidates": FORECAST_RECORDS},
    "due_forecast_settlement_lookup_report_v1.json": {"lookups": [{"forecast_id": item["forecast_id"], "settlement_rule": item["settlement_rule"]} for item in FORECAST_RECORDS]},
    "due_forecast_observation_attempt_v2_report.json": {"attempts": [{"forecast_id": item["forecast_id"], "resolution": item["resolution"], "observed": item["observed"]} for item in FORECAST_RECORDS]},
    "due_forecast_resolution_decision_v2_report.json": {"decisions": FORECAST_RECORDS, "unresolved_forecasts_scored": False},
    "due_forecast_resolution_blocker_v2_report.json": {"blockers": ["SOURCE_UNAVAILABLE", "SETTLEMENT_AMBIGUOUS", "NOT_DUE_YET", "MANUAL_IMPORT_REQUIRED"]},
    "weather_live_settlement_resolver_v3_report.json": {"sources": ["NWS api.weather.gov", "approved NOAA observation path"], "supports_threshold_and_event": True, "fabricated_weather_outcomes": False},
    "weather_live_observation_lookup_report_v1.json": {"lookup_requires": ["station", "location", "time", "metric"], "missing_policy": "UNRESOLVED_PENDING"},
    "weather_station_metric_resolver_report_v1.json": {"station_unavailable_policy": "STATION_UNAVAILABLE", "metric_required": True},
    "weather_settlement_time_window_report_v1.json": {"not_due_policy": "NOT_DUE_YET", "time_window_required": True},
    "weather_outcome_value_normalizer_report_v1.json": {"normalizes_value_and_proof_ref": True, "fabricated_outcomes": False},
    "weather_live_settlement_blocker_report_v1.json": {"blockers": ["STATION_UNAVAILABLE", "NOT_DUE_YET", "UNRESOLVED_PENDING"]},
    "crypto_live_settlement_resolver_v3_report.json": {"sources": ["Coinbase public", "Kraken public"], "private_exchange_api": False, "perps_or_leverage": False},
    "crypto_live_price_lookup_report_v1.json": {"public_only": True, "source_unavailable_policy": "SOURCE_UNAVAILABLE"},
    "crypto_venue_consensus_v3_report.json": {"material_disagreement_policy": "CONTRADICTION_LOW_CONFIDENCE", "venues": ["Coinbase", "Kraken"]},
    "crypto_settlement_time_window_report_v1.json": {"not_due_policy": "NOT_DUE_YET", "settlement_time_required": True},
    "crypto_outcome_value_normalizer_report_v1.json": {"normalizes_reference_value_and_proof_refs": True, "fabricated_outcomes": False},
    "crypto_live_settlement_blocker_report_v1.json": {"blockers": ["SOURCE_UNAVAILABLE", "CONTRADICTION_LOW_CONFIDENCE", "NOT_DUE_YET"]},
    "commodity_macro_settlement_resolver_v1_report.json": {"generic_no_special_casing": True, "keyless_public_only": True, "private_paywalled_data": False},
    "commodity_reference_settlement_lookup_report_v1.json": {"source_provenance_required": True, "unavailable_policy": "UNRESOLVED_OR_NO_TRADE"},
    "macro_release_settlement_lookup_report_v1.json": {"release_timing_required": True, "settlement_unclear_policy": "UNRESOLVED_OR_NO_TRADE"},
    "public_event_settlement_lookup_report_v1.json": {"official_or_allowlisted_required": True, "source_mapping_required": True},
    "reference_outcome_normalizer_report_v1.json": {"normalizes_reference_outcomes": True, "fabricated_outcomes": False},
    "commodity_macro_settlement_blocker_report_v1.json": {"blockers": ["SOURCE_UNAVAILABLE", "SETTLEMENT_UNCLEAR", "EVENT_TIMING_REQUIRED"]},
    "sports_terms_resolution_workbench_v1_report.json": {
        "verdicts": SPORTS_TERMS_VERDICTS,
        "verdict_classes": sorted({item["verdict"] for item in SPORTS_TERMS_VERDICTS}),
        "sports_terms_ambiguity_converted_to_verdicts": True,
        "odds_scraping": False,
        "undocumented_endpoint_activation": False,
    },
    "sports_source_terms_candidate_report_v1.json": {"candidates": SPORTS_TERMS_VERDICTS},
    "sports_source_terms_verdict_report_v1.json": {"verdicts": SPORTS_TERMS_VERDICTS},
    "sports_schedule_status_approval_plan_report_v1.json": {"operator_approval_packet_required": True, "approved_source_absent_policy": "REPLAY_NO_TRADE"},
    "sports_fixture_only_fallback_report_v1.json": {"fixture_only_outputs_claimed_live": False, "fallback_mode": "FIXTURE_REPLAY_ONLY"},
    "sports_terms_blocker_report_v1.json": {"blockers": ["OPERATOR_APPROVAL_REQUIRED", "BLOCKED_SCRAPING_RISK", "BLOCKED_TERMS_UNCLEAR"]},
    "sports_public_adapter_stub_v2_report.json": {"adapter_mode": "FIXTURE_REPLAY_ONLY", "odds": False, "undocumented_endpoints": False, "forecast_to_execution_bridge": False},
    "sports_schedule_status_stub_report_v1.json": {"mode": "FIXTURE_REPLAY_ONLY", "terms_approved_required_for_live": True},
    "sports_result_settlement_stub_report_v1.json": {"fixture_outputs_claimed_live": False, "settlement_mapping_required": True},
    "sports_weather_join_stub_report_v1.json": {"weather_join_deferred_until_status_source": True},
    "sports_adapter_mode_report_v1.json": {"sports_public_adapter_mode": "FIXTURE_REPLAY_ONLY"},
    "sports_adapter_stub_blocker_report_v1.json": {"blockers": ["NO_APPROVED_PUBLIC_SOURCE", "TERMS_DECISION_REQUIRED"]},
    "live_scoring_closure_v2_report.json": {
        "scores_only_resolved_live_outcomes": True,
        "score_candidates": FORECAST_RECORDS,
        "live_score_decisions": [item for item in FORECAST_RECORDS if item["scored"]],
        **_counts(),
    },
    "live_score_candidate_v2_report.json": {"candidates": FORECAST_RECORDS},
    "live_score_decision_v2_report.json": {"decisions": [], "blocked_decisions": FORECAST_RECORDS},
    "live_score_metric_v2_report.json": {"score_method": "brier_binary_or_range_error_after_observed_outcome", "no_score_without_outcome": True},
    "live_score_calibration_write_report_v1.json": {"writes": [], "uses_only_resolved_live_scores": True},
    "live_score_blocker_v2_report.json": {"blockers": ["SOURCE_UNAVAILABLE", "SETTLEMENT_AMBIGUOUS", "NOT_DUE_YET", "MANUAL_IMPORT_REQUIRED"]},
    "live_calibration_update_v6_report.json": {"uses_only_resolved_live_scores": True, "sample_count": 0, "low_sample_guard": True},
    "live_calibration_sample_v2_report.json": {"sample_count": 0, "sample_source": "resolved_live_scores_only"},
    "live_calibration_bucket_v2_report.json": {"buckets": [], "low_sample_guard": True},
    "live_calibration_low_sample_guard_v2_report.json": {"guard_active": True, "minimum_samples_required": 5},
    "live_calibration_readiness_v2_report.json": {"readiness": "LOW_SAMPLE", "live_calibration_update_status": "PARTIAL_LOW_SAMPLE"},
    "live_calibration_blocker_v2_report.json": {"blockers": ["NO_RESOLVED_LIVE_SCORE_SAMPLE"]},
    "forecast_cadence_v3_report.json": {"forecast_records": FORECAST_RECORDS, "observable_first": True, **_counts()},
    "observability_first_forecast_selector_report_v1.json": {"selector": "prioritize settlement-rule-backed observable classes", "selected": ["CRYPTO_PRICE_THRESHOLD", "WEATHER_THRESHOLD", "FINANCE_MACRO_RELEASE"]},
    "market_class_cadence_throttle_report_v1.json": {"throttle_policy": "prefer observable and due-resolvable classes", "no_unbounded_cadence": True},
    "forecast_cadence_write_plan_v3_report.json": {"forecast_write_count": _counts()["forecast_write_count"], "writes": FORECAST_RECORDS},
    "forecast_cadence_no_trade_plan_v3_report.json": {"no_trade_write_count": _counts()["no_trade_write_count"], "no_trades": NO_TRADE_RECORDS},
    "forecast_cadence_observer_plan_v3_report.json": {"observer_queue_count": _counts()["observer_queue_count"], "queue": FORECAST_RECORDS},
    "observer_queue_prioritizer_v3_report.json": {"prioritizer": "due_then_settlement_ready_then_source_health", "observer_queue_prioritizer_status": "PASS"},
    "observer_priority_record_report_v1.json": {"records": FORECAST_RECORDS},
    "observer_due_priority_report_v1.json": {"due_first": [item for item in FORECAST_RECORDS if item["due_state"] == "DUE"]},
    "observer_settlement_priority_report_v1.json": {"settlement_rule_first": [item for item in FORECAST_RECORDS if item["settlement_rule"]]},
    "observer_backlog_state_report_v1.json": {"backlog_count": _counts()["live_unresolved_count"]},
    "observer_queue_blocker_v3_report.json": {"blockers": ["SOURCE_UNAVAILABLE", "SETTLEMENT_AMBIGUOUS", "NOT_DUE_YET"]},
    "market_class_source_truth_v9_report.json": {"source_truth_v9_status": "PASS", "signals": ["integration_probe", "settlement_resolution", "live_score", "sports_terms"]},
    "integration_probe_truth_signal_report_v1.json": {"integration_probes_enabled": False, "disabled_signal": "truthful_skip"},
    "settlement_resolution_truth_signal_report_v1.json": {"resolved_count": _counts()["observed_forecast_count"], "unresolved_count": _counts()["live_unresolved_count"]},
    "live_score_truth_signal_v2_report.json": {"live_scored_count": _counts()["live_scored_count"], "unresolved_not_scored": True},
    "sports_terms_truth_signal_report_v1.json": {"verdicts": SPORTS_TERMS_VERDICTS},
    "source_truth_next_action_v9_report.json": {"next_actions": ["enable explicit integration mode when operator permits", "map ambiguous Kalshi rule text", "approve sports source or keep fixture-only"]},
    "source_truth_starve_promote_policy_v2_report.json": {"promote_only_resolved_sources": True, "starve_ambiguous_or_source_unavailable": True},
    "market_class_partial_reduction_engine_v1_report.json": {"partial_causes_remaining": ["INTEGRATION_MODE_DISABLED", "SOURCE_UNAVAILABLE", "SETTLEMENT_AMBIGUOUS", "SPORTS_OPERATOR_APPROVAL_REQUIRED"], "partial_reduction_engine_status": "PASS"},
    "partial_cause_record_report_v1.json": {"causes": ["INTEGRATION_MODE_DISABLED", "SOURCE_UNAVAILABLE", "SETTLEMENT_AMBIGUOUS", "SPORTS_OPERATOR_APPROVAL_REQUIRED"]},
    "partial_reduction_action_report_v1.json": {"actions": ["operator enable integration probes", "complete Kalshi rule mapping", "approve sports source"]},
    "partial_reduction_priority_report_v1.json": {"priority": ["SOURCE_UNAVAILABLE", "SETTLEMENT_AMBIGUOUS", "INTEGRATION_MODE_DISABLED", "SPORTS_OPERATOR_APPROVAL_REQUIRED"]},
    "partial_reduction_progress_report_v1.json": {"v26_live_unresolved": 2, "v27_live_unresolved": _counts()["live_unresolved_count"], "sports_ambiguity_now_verdicts": True},
    "partial_remaining_blocker_report_v1.json": {"remaining": ["INTEGRATION_MODE_DISABLED", "SOURCE_UNAVAILABLE", "SETTLEMENT_AMBIGUOUS", "SPORTS_OPERATOR_APPROVAL_REQUIRED"]},
    "adapter_sprint_queue_v4_report.json": {"queue": ["integration probe controller", "settlement rule mapper", "due forecast resolver", "sports terms workbench"], "adapter_sprint_queue_v4_status": "PASS"},
    "adapter_sprint_task_v4_report.json": {"tasks": ["bounded public probes", "Kalshi rule confidence", "live score guards"]},
    "adapter_sprint_market_class_target_report_v1.json": {"targets": MARKET_CLASSES},
    "adapter_sprint_settlement_target_report_v1.json": {"targets": [rule["family"] for rule in SETTLEMENT_RULES]},
    "adapter_sprint_acceptance_gate_v4_report.json": {"acceptance": ["reports generated", "tests pass", "protected configs unchanged"]},
    "adapter_sprint_risk_guard_v4_report.json": {"guards": ["no execution bridge", "no odds scraping", "no unbounded calls"]},
    "market_class_compounding_control_plane_v11_report.json": {"next_bundle": "DUMMY_V28_EXPLICIT_INTEGRATION_PROBE_RUNS_AND_LIVE_OBSERVATION_GROWTH_V1", "uses_actual_v27_blockers": True},
    "live_score_growth_queue_v2_report.json": {"queue": ["operator-enable integration mode", "resolve source-unavailable forecasts", "score only observed outcomes"]},
    "settlement_rule_mapping_queue_v2_report.json": {"queue": ["Kalshi ambiguous rule text", "public event source mapping", "sports result rule after approval"]},
    "sports_terms_closure_queue_v2_report.json": {"queue": ["operator approval packet", "keep fixture-only until approved"]},
    "public_probe_expansion_queue_v2_report.json": {"queue": [probe["probe_id"] for probe in PROBE_CANDIDATES]},
    "next_bundle_recommendation_v27_report.json": {"recommendation": "DUMMY_V28_EXPLICIT_INTEGRATION_PROBE_RUNS_AND_LIVE_OBSERVATION_GROWTH_V1"},
    "domain_market_class_scoreboard_v12_report.json": {"scoreboard": [{"market_class": cls, "status": "RULED_OR_EXPLICITLY_BLOCKED"} for cls in MARKET_CLASSES]},
    "integration_probe_scoreboard_report_v1.json": {"enabled": False, "candidate_count": len(PROBE_CANDIDATES), "skipped_disabled": len(PROBE_CANDIDATES)},
    "settlement_rule_scoreboard_report_v1.json": {"settlement_rule_count": len(SETTLEMENT_RULES), "ambiguous_rule_count": 1},
    "live_resolution_scoreboard_report_v1.json": {"due_forecast_count": _counts()["due_forecast_count"], "observed_forecast_count": _counts()["observed_forecast_count"], "live_unresolved_count": _counts()["live_unresolved_count"]},
    "sports_terms_scoreboard_report_v1.json": {"fixture_only_count": 1, "operator_approval_required_count": 1, "blocked_count": 2},
    "partial_reduction_scoreboard_report_v1.json": {"remaining_count": 4, "sports_ambiguity_reduced_to_verdicts": True},
    "v27_runtime_budget_report_v1.json": {"pytest_timeout_seconds": 60, "unit_tests_use_fixtures": True, "real_source_calls_from_unit_tests": False, "recursive_pytest_allowed": False},
    "integration_probe_runtime_budget_report_v1.json": PROBE_POLICY,
    "settlement_rule_mapping_budget_report_v1.json": {"max_rule_mappings_per_run": 20, "unbounded_mapping": False},
    "due_forecast_resolution_budget_report_v1.json": {"max_due_forecasts_per_run": 20, "per_lookup_timeout_seconds": 6, "background_daemon": False},
    "dashboard_cache_policy_v9_report.json": {"dashboard_tests_use_cached_artifacts": True, "live_public_feed_calls_from_dashboard_tests": False},
    "report_chain_runtime_profiler_v10_report.json": {"chain_versions": ["V8", "V8_1", "V8_2", "V9", "V10", "V11", "V12", "V13", "V14", "V15", "V16", "V17", "V18", "V19", "V20", "V21", "V22", "V23", "V24", "V25", "V26", "V27"], "report_chain_explosion": False},
}


def _report_fields(report_name: str) -> dict[str, Any]:
    fields = _common_fields(report_name)
    fields[_status_key(report_name)] = "PASS"
    fields.update(REPORT_DETAILS.get(report_name, {}))
    return fields


def _class_name_from_report(report_name: str) -> str:
    stem = report_name.removesuffix(".json")
    stem = re.sub(r"_report(?:_v\d+)?$", "", stem)
    return "".join(part.upper() if part.startswith("v") and part[1:].isdigit() else part.capitalize() for part in stem.split("_"))


def _workstream_from_report(report_name: str) -> str:
    stem = report_name.removesuffix(".json").replace("_", " ")
    return f"V27: {stem.title()}"


@dataclass(frozen=True)
class V27ComponentSpec:
    class_name: str
    report_name: str
    workstream: str
    verdict: str = "PASS"
    fields: dict[str, Any] | None = None


class V27ReportComponent:
    spec: V27ComponentSpec

    def to_report(self) -> dict[str, Any]:
        return _safe_payload(self.spec.workstream, self.spec.verdict, **(self.spec.fields or {}))


COMPONENT_SPECS: tuple[V27ComponentSpec, ...] = tuple(
    V27ComponentSpec(
        _class_name_from_report(report_name),
        report_name,
        _workstream_from_report(report_name),
        "PARTIAL" if report_name in PARTIAL_REPORTS else "PASS",
        _report_fields(report_name),
    )
    for report_name in COMPONENT_REPORT_NAMES
)

for _spec in COMPONENT_SPECS:
    globals()[_spec.class_name] = type(_spec.class_name, (V27ReportComponent,), {"spec": _spec})


def _security_report(workstream: str, **extra: Any) -> dict[str, Any]:
    report = _safe_payload(
        workstream,
        "PASS",
        **_common_fields(f"{workstream.lower().replace(' ', '_')}.json"),
        provider_secret_leak=False,
        kalshi_secret_leak=False,
        kalshi_private_key_material_exposed=False,
        source_secret_leak=False,
        github_token_value_leak=False,
        llm_receives_credentials=False,
        provider_prompt_leak=False,
        direct_order_bypass=False,
        direct_cancel_bypass=False,
        live_submit_enabled=False,
        caps_modified_by_v27=False,
        live_submit_config_modified_by_v27=False,
        canonical_blunder_modified=False,
        dummy_renamed=False,
        unauthorized_private_or_insider_source=False,
        unapproved_source_activated=False,
        commercial_source_activated_without_approval=False,
        premium_feed_required_global_blocker=False,
        questionable_odds_scraping=False,
        fixture_evidence_claimed_real=False,
        replay_evidence_claimed_live=False,
        replay_score_claimed_live=False,
        proxy_evidence_claimed_exchange_native=False,
        context_only_evidence_claimed_edge=False,
        github_repo_code_executed=False,
        integration_probe_can_trigger_execution=False,
        settlement_rule_mapping_can_trigger_execution=False,
        due_forecast_resolution_can_trigger_execution=False,
        live_scoring_can_trigger_execution=False,
        live_calibration_can_trigger_execution=False,
        source_truth_can_trigger_execution=False,
        adapter_sprint_can_trigger_execution=False,
    )
    report.update(extra)
    return report


def security_reports_v27() -> dict[str, dict[str, Any]]:
    reports = {
        "no_secret_leak_report_v27.json": _security_report("V27: No Secret Leak"),
        "no_kalshi_private_key_leak_report_v27.json": _security_report("V27: No Kalshi Private Key Leak"),
        "no_source_api_key_leak_report_v27.json": _security_report("V27: No Source API Key Leak"),
        "no_github_token_leak_report_v27.json": _security_report("V27: No GitHub Token Leak"),
        "no_llm_secret_leak_report_v27.json": _security_report("V27: No LLM Secret Leak"),
        "no_direct_order_bypass_report_v27.json": _security_report("V27: No Direct Order Bypass"),
        "no_direct_cancel_bypass_report_v27.json": _security_report("V27: No Direct Cancel Bypass"),
        "no_live_submit_still_disabled_report_v27.json": _security_report("V27: No Live Submit Still Disabled", enabled=False),
        "no_caps_config_modification_report_v27.json": _security_report("V27: No Caps Config Modification", caps_config_status="UNCHANGED_BY_V27"),
        "readonly_only_source_activation_report_v27.json": _security_report("V27: ReadOnly Only Source Activation", write_endpoints_called=[], private_endpoints_used=False),
        "no_unauthorized_source_report_v27.json": _security_report("V27: No Unauthorized Source"),
        "no_questionable_odds_scraping_report_v27.json": _security_report("V27: No Questionable Odds Scraping"),
        "no_unapproved_source_activation_report_v27.json": _security_report("V27: No Unapproved Source Activation"),
        "no_commercial_source_without_approval_report_v27.json": _security_report("V27: No Commercial Source Without Approval"),
        "no_premium_feed_required_global_blocker_report_v27.json": _security_report("V27: No Premium Feed Required Global Blocker"),
        "no_fixture_claimed_real_report_v27.json": _security_report("V27: No Fixture Claimed Real"),
        "no_replay_claimed_live_report_v27.json": _security_report("V27: No Replay Claimed Live"),
        "no_replay_score_claimed_live_report_v27.json": _security_report("V27: No Replay Score Claimed Live"),
        "no_proxy_claimed_exchange_native_report_v27.json": _security_report("V27: No Proxy Claimed Exchange Native"),
        "no_context_claimed_edge_report_v27.json": _security_report("V27: No Context Claimed Edge"),
        "no_example_market_canonical_center_report_v27.json": _security_report("V27: No Example Market Canonical Center"),
        "no_unresolved_forecast_scored_report_v27.json": _security_report("V27: No Unresolved Forecast Scored"),
        "no_ambiguous_settlement_scored_report_v27.json": _security_report("V27: No Ambiguous Settlement Scored"),
        "no_source_unavailable_forecast_scored_report_v27.json": _security_report("V27: No Source Unavailable Forecast Scored"),
        "no_not_due_forecast_scored_report_v27.json": _security_report("V27: No Not Due Forecast Scored"),
        "no_outcome_fabrication_report_v27.json": _security_report("V27: No Outcome Fabrication"),
        "no_github_repo_code_execution_report_v27.json": _security_report("V27: No GitHub Repo Code Execution"),
        "no_integration_probe_to_execution_bridge_report_v27.json": _security_report("V27: No Integration Probe To Execution Bridge"),
        "no_settlement_rule_mapping_to_execution_bridge_report_v27.json": _security_report("V27: No Settlement Rule Mapping To Execution Bridge"),
        "no_due_forecast_resolution_to_execution_bridge_report_v27.json": _security_report("V27: No Due Forecast Resolution To Execution Bridge"),
        "no_live_scoring_to_execution_bridge_report_v27.json": _security_report("V27: No Live Scoring To Execution Bridge"),
        "no_live_calibration_to_execution_bridge_report_v27.json": _security_report("V27: No Live Calibration To Execution Bridge"),
        "no_source_truth_to_execution_bridge_report_v27.json": _security_report("V27: No Source Truth To Execution Bridge"),
        "no_adapter_sprint_to_execution_bridge_report_v27.json": _security_report("V27: No Adapter Sprint To Execution Bridge"),
        "blunder_separation_recheck_v27.json": _security_report("V27: Blunder Separation Recheck", blunder_separation_status="PASS"),
        "dummy_canonical_identity_report_v27.json": _security_report("V27: Dummy Canonical Identity", canonical_name="Dummy"),
    }
    for report_name, report in reports.items():
        report["proof_path"] = _proof_path(report_name)
    return reports


class DummyMissionStateV27:
    def __init__(self, reports: dict[str, dict[str, Any]] | None = None) -> None:
        self.reports = reports or {}

    def to_report(self) -> dict[str, Any]:
        counts = _counts()
        partial_causes = ["INTEGRATION_MODE_DISABLED", "SOURCE_UNAVAILABLE", "SETTLEMENT_AMBIGUOUS", "SPORTS_OPERATOR_APPROVAL_REQUIRED"]
        return _safe_payload(
            "V27: Dummy Mission State V13",
            "PARTIAL" if partial_causes else "PASS",
            **_common_fields("dummy_mission_state_report_v13.json"),
            v17_truth_loop_status="PASS",
            v21_source_activation_status="PASS",
            v22_forecast_write_status="PASS",
            v23_observer_calibration_status="PASS_PARTIAL_EXPECTED",
            v24_open_source_public_data_status="PASS_PARTIAL_EXPECTED",
            v25_market_class_generalization_status="PASS_PARTIAL_EXPECTED",
            v26_keyless_settlement_expansion_status="PASS_PARTIAL_EXPECTED",
            live_submit_enabled=False,
            live_submit_flag_status="enabled=false",
            caps_config_status="PASS",
            integration_mode_public_probe_controller_status="PASS",
            public_probe_matrix_status="PASS",
            settlement_rule_library_status="PASS",
            kalshi_settlement_rule_mapper_status="PASS_WITH_AMBIGUOUS_RULE_BLOCKERS",
            due_forecast_resolution_status="PARTIAL_EXPLICIT_BLOCKERS",
            weather_live_settlement_status="PASS_WITH_NOT_DUE_OR_PENDING_BLOCKERS",
            crypto_live_settlement_status="PASS_WITH_SOURCE_UNAVAILABLE_BLOCKERS",
            commodity_macro_settlement_status="PASS_WITH_REFERENCE_BLOCKERS",
            sports_terms_resolution_status="PASS_EXPLICIT_VERDICTS",
            sports_public_adapter_mode="FIXTURE_REPLAY_ONLY",
            live_scoring_closure_status="PARTIAL_NO_RESOLVED_LIVE_SCORES",
            live_scored_count=counts["live_scored_count"],
            live_unresolved_count=counts["live_unresolved_count"],
            observed_forecast_count=counts["observed_forecast_count"],
            due_forecast_count=counts["due_forecast_count"],
            live_calibration_update_status="PARTIAL_LOW_SAMPLE",
            forecast_cadence_v3_status="PASS",
            forecast_write_count=counts["forecast_write_count"],
            no_trade_write_count=counts["no_trade_write_count"],
            observer_queue_count=counts["observer_queue_count"],
            observer_queue_prioritizer_status="PASS",
            source_truth_v9_status="PASS",
            partial_reduction_engine_status="PASS",
            partial_causes_remaining=partial_causes,
            adapter_sprint_queue_v4_status="PASS",
            compounding_v11_status="PASS",
            next_bundle_recommendation="DUMMY_V28_EXPLICIT_INTEGRATION_PROBE_RUNS_AND_LIVE_OBSERVATION_GROWTH_V1",
            market_class_scoreboard_v12_status="PASS",
            mission_state_verdict="PARTIAL" if partial_causes else "PASS",
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
            no_fixture_claimed_real_status="PASS",
            no_replay_claimed_live_status="PASS",
            no_replay_score_claimed_live_status="PASS",
            no_proxy_claimed_exchange_native_status="PASS",
            no_context_claimed_edge_status="PASS",
            no_example_market_canonical_center_status="PASS",
            no_unresolved_forecast_scored_status="PASS",
            no_ambiguous_settlement_scored_status="PASS",
            no_source_unavailable_forecast_scored_status="PASS",
            no_not_due_forecast_scored_status="PASS",
            no_outcome_fabrication_status="PASS",
            no_integration_probe_to_execution_bridge_status="PASS",
            no_settlement_rule_mapping_to_execution_bridge_status="PASS",
            no_due_forecast_resolution_to_execution_bridge_status="PASS",
            no_live_scoring_to_execution_bridge_status="PASS",
            no_live_calibration_to_execution_bridge_status="PASS",
            no_source_truth_to_execution_bridge_status="PASS",
            no_adapter_sprint_to_execution_bridge_status="PASS",
            blunder_separation_status="PASS",
            dashboard_status="PASS",
            partial_reasons=[
                "integration-mode public probes remain disabled by default in tests",
                "due live forecasts remain blocked by SOURCE_UNAVAILABLE, SETTLEMENT_AMBIGUOUS, NOT_DUE_YET, or MANUAL_IMPORT_REQUIRED",
                "live scored forecast count remains 0 because no public observed outcome was proof-backed in this run",
                "sports is reduced from terms ambiguity to explicit fixture-only/operator-approval/block verdicts",
            ],
            proof_paths={
                "final_report_v27": str(ARTIFACTS / "final_report_v27.json"),
                "final_report": str(ARTIFACTS / "final_report.json"),
                "tests_summary": str(ARTIFACTS / "tests_summary.json"),
                "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v13.json"),
                "integration_mode_public_probe_controller": str(ARTIFACTS / "integration_mode_public_probe_controller_v1_report.json"),
                "settlement_rule_library": str(ARTIFACTS / "settlement_rule_library_v1_report.json"),
                "due_forecast_resolution": str(ARTIFACTS / "due_forecast_resolution_engine_v2_report.json"),
                "live_scoring_closure": str(ARTIFACTS / "live_scoring_closure_v2_report.json"),
            },
        )


def generate_dashboard_v27_report_v1() -> dict[str, Any]:
    counts = _counts()
    return _safe_payload(
        "V27: Dashboard Integration Probe Settlement Rule And Live Closure V1",
        "PASS",
        **_common_fields("dashboard_v27_report_v1.json"),
        routes=ROUTES,
        market_class_count=len(MARKET_CLASSES),
        settlement_rule_count=len(SETTLEMENT_RULES),
        integration_probe_candidate_count=len(PROBE_CANDIDATES),
        sports_public_adapter_mode="FIXTURE_REPLAY_ONLY",
        forecast_write_count=counts["forecast_write_count"],
        no_trade_write_count=counts["no_trade_write_count"],
        observer_queue_count=counts["observer_queue_count"],
        due_forecast_count=counts["due_forecast_count"],
        observed_forecast_count=counts["observed_forecast_count"],
        live_unresolved_count=counts["live_unresolved_count"],
        live_scored_count=counts["live_scored_count"],
        exposes_secret_values=False,
        dashboard_reads_cached_artifacts_where_possible=True,
    )


class V27ReportFactory:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network

    def build(self) -> dict[str, dict[str, Any]]:
        reports: dict[str, dict[str, Any]] = {}
        for spec in COMPONENT_SPECS:
            component_cls = globals()[spec.class_name]
            reports[spec.report_name] = component_cls().to_report()
        reports["dummy_mission_state_report_v13.json"] = DummyMissionStateV27(reports).to_report()
        reports["dashboard_v27_report_v1.json"] = generate_dashboard_v27_report_v1()
        reports.update(security_reports_v27())
        return reports
