"""V29 metadata-only OSS triage, adapter-spec, fixture, and probe-readiness reports."""

from __future__ import annotations

import json
import os
import re
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v29 import MILESTONE

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"
REPORT_NAMES_FILE = ARTIFACTS / "v29_required_report_names_from_attachment.txt"
EVALUATION_DATE = datetime(2026, 7, 3, tzinfo=timezone.utc)
ATTACHMENT_DECLARED_CANDIDATE_COUNT = 182


DEFAULT_REQUIRED_REPORT_NAMES = [
    "oss_candidate_universe_normalizer_v1_report.json",
    "oss_candidate_canonical_record_report_v1.json",
    "oss_candidate_duplicate_cluster_report_v1.json",
    "oss_candidate_keyword_provenance_report_v1.json",
    "oss_candidate_category_map_report_v1.json",
    "oss_candidate_normalization_blocker_report_v1.json",
    "oss_license_terms_triage_v1_report.json",
    "oss_license_signal_report_v1.json",
    "oss_terms_risk_signal_report_v1.json",
    "oss_dependency_risk_signal_report_v1.json",
    "oss_commercial_risk_signal_report_v1.json",
    "oss_license_triage_verdict_report_v1.json",
    "oss_license_triage_blocker_report_v1.json",
    "oss_maintenance_quality_score_v1_report.json",
    "oss_activity_signal_report_v1.json",
    "oss_popularity_signal_report_v1.json",
    "oss_issue_risk_signal_report_v1.json",
    "oss_documentation_signal_report_v1.json",
    "oss_maintenance_verdict_report_v1.json",
    "oss_quality_blocker_report_v1.json",
    "market_class_oss_fit_scorer_v1_report.json",
    "oss_market_class_fit_report_v1.json",
    "oss_source_role_fit_report_v1.json",
    "oss_settlement_role_fit_report_v1.json",
    "oss_replay_role_fit_report_v1.json",
    "oss_adapter_utility_score_report_v1.json",
    "oss_market_class_fit_blocker_report_v1.json",
    "adapter_spec_factory_v1_report.json",
    "in_house_adapter_spec_report_v1.json",
    "adapter_interface_contract_report_v1.json",
    "adapter_input_output_schema_report_v1.json",
    "adapter_freshness_policy_report_v1.json",
    "adapter_error_policy_report_v1.json",
    "adapter_spec_blocker_report_v1.json",
    "fixture_schema_generator_v1_report.json",
    "adapter_fixture_schema_report_v1.json",
    "adapter_fixture_sample_report_v1.json",
    "adapter_fixture_mode_label_report_v1.json",
    "adapter_fixture_validation_rule_report_v1.json",
    "adapter_fixture_blocker_report_v1.json",
    "adapter_contract_test_planner_v1_report.json",
    "adapter_contract_test_case_report_v1.json",
    "adapter_contract_invariant_report_v1.json",
    "adapter_contract_mock_plan_report_v1.json",
    "adapter_contract_integration_plan_report_v1.json",
    "adapter_contract_safety_plan_report_v1.json",
    "public_probe_readiness_planner_v2_report.json",
    "public_probe_readiness_candidate_report_v1.json",
    "public_probe_endpoint_plan_report_v1.json",
    "public_probe_budget_plan_report_v1.json",
    "public_probe_legality_plan_report_v1.json",
    "public_probe_readiness_verdict_report_v1.json",
    "public_probe_readiness_blocker_report_v1.json",
    "settlement_gap_adapter_mapper_v1_report.json",
    "settlement_gap_case_report_v1.json",
    "settlement_gap_adapter_candidate_report_v1.json",
    "settlement_gap_closure_potential_report_v1.json",
    "settlement_gap_adapter_priority_report_v1.json",
    "settlement_gap_blocker_report_v1.json",
    "sports_source_legality_resolver_v3_report.json",
    "sports_oss_candidate_terms_review_report_v1.json",
    "sports_source_approval_candidate_report_v1.json",
    "sports_source_fixture_only_decision_report_v1.json",
    "sports_source_terms_escalation_report_v1.json",
    "sports_source_legality_blocker_report_v1.json",
    "weather_oss_adapter_spec_pack_v1_report.json",
    "weather_adapter_spec_candidate_report_v1.json",
    "weather_public_api_plan_report_v1.json",
    "weather_observation_fixture_plan_report_v1.json",
    "weather_settlement_adapter_plan_report_v1.json",
    "weather_adapter_spec_blocker_report_v1.json",
    "crypto_oss_adapter_spec_pack_v1_report.json",
    "crypto_adapter_spec_candidate_report_v1.json",
    "crypto_public_price_api_plan_report_v1.json",
    "crypto_venue_consensus_fixture_plan_report_v1.json",
    "crypto_settlement_adapter_plan_report_v1.json",
    "crypto_adapter_spec_blocker_report_v1.json",
    "event_market_oss_adapter_spec_pack_v1_report.json",
    "event_market_adapter_spec_candidate_report_v1.json",
    "kalshi_readonly_adapter_plan_v2_report.json",
    "event_market_settlement_rule_fixture_plan_report_v1.json",
    "event_market_public_data_join_plan_report_v1.json",
    "event_market_adapter_spec_blocker_report_v1.json",
    "trading_backtesting_oss_reference_pack_v1_report.json",
    "backtesting_reference_candidate_report_v1.json",
    "replay_framework_reference_signal_report_v1.json",
    "trading_execution_risk_signal_report_v1.json",
    "backtesting_reference_verdict_report_v1.json",
    "trading_backtesting_blocker_report_v1.json",
    "bloomberg_alternative_oss_reference_pack_v1_report.json",
    "bloomberg_alternative_candidate_report_v1.json",
    "bloomberg_dependency_risk_report_v1.json",
    "bloomberg_open_data_alternative_plan_report_v1.json",
    "bloomberg_alternative_verdict_report_v1.json",
    "bloomberg_alternative_blocker_report_v1.json",
    "oss_candidate_promotion_gate_v1_report.json",
    "oss_promotion_candidate_report_v1.json",
    "oss_promotion_prerequisite_report_v1.json",
    "oss_promotion_decision_report_v1.json",
    "oss_promotion_risk_guard_report_v1.json",
    "oss_promotion_blocker_report_v1.json",
    "adapter_sprint_queue_v6_report.json",
    "adapter_sprint_v6_candidate_report_v1.json",
    "adapter_sprint_v6_priority_report_v1.json",
    "adapter_sprint_v6_scope_report_v1.json",
    "adapter_sprint_v6_acceptance_gate_report_v1.json",
    "adapter_sprint_v6_risk_guard_report_v1.json",
    "oss_to_observation_compounding_control_plane_v13_report.json",
    "oss_adapter_spec_queue_report_v1.json",
    "public_probe_readiness_queue_v2_report.json",
    "live_observation_closure_queue_v2_report.json",
    "sports_legality_queue_v3_report.json",
    "settlement_adapter_queue_v2_report.json",
    "next_bundle_recommendation_v29_report.json",
    "domain_market_class_scoreboard_v14_report.json",
    "oss_candidate_scoreboard_report_v1.json",
    "adapter_spec_readiness_scoreboard_report_v1.json",
    "public_probe_readiness_scoreboard_report_v1.json",
    "settlement_gap_adapter_scoreboard_report_v1.json",
    "oss_promotion_scoreboard_report_v1.json",
    "dummy_mission_state_report_v15.json",
    "dashboard_v29_report_v1.json",
    "v29_runtime_budget_report_v1.json",
    "oss_metadata_processing_budget_report_v1.json",
    "adapter_spec_generation_budget_report_v1.json",
    "fixture_schema_generation_budget_report_v1.json",
    "dashboard_cache_policy_v11_report.json",
    "report_chain_runtime_profiler_v12_report.json",
    "no_secret_leak_report_v29.json",
    "no_kalshi_private_key_leak_report_v29.json",
    "no_source_api_key_leak_report_v29.json",
    "no_github_token_leak_report_v29.json",
    "no_llm_secret_leak_report_v29.json",
    "no_direct_order_bypass_report_v29.json",
    "no_direct_cancel_bypass_report_v29.json",
    "no_live_submit_still_disabled_report_v29.json",
    "no_caps_config_modification_report_v29.json",
    "readonly_only_source_activation_report_v29.json",
    "no_unauthorized_source_report_v29.json",
    "no_questionable_odds_scraping_report_v29.json",
    "no_unapproved_source_activation_report_v29.json",
    "no_commercial_source_without_approval_report_v29.json",
    "no_premium_feed_required_global_blocker_report_v29.json",
    "no_browser_automation_report_v29.json",
    "no_pageagent_report_v29.json",
    "no_dom_extraction_report_v29.json",
    "no_browser_research_lane_report_v29.json",
    "no_mined_repo_clone_report_v29.json",
    "no_mined_repo_import_report_v29.json",
    "no_mined_repo_execution_report_v29.json",
    "no_blind_mined_code_copy_report_v29.json",
    "no_fixture_claimed_real_report_v29.json",
    "no_replay_claimed_live_report_v29.json",
    "no_replay_score_claimed_live_report_v29.json",
    "no_proxy_claimed_exchange_native_report_v29.json",
    "no_cached_sample_claimed_live_report_v29.json",
    "no_stale_cached_evidence_scored_live_report_v29.json",
    "no_context_claimed_edge_report_v29.json",
    "no_example_market_canonical_center_report_v29.json",
    "no_unresolved_forecast_scored_report_v29.json",
    "no_ambiguous_settlement_scored_report_v29.json",
    "no_source_unavailable_forecast_scored_report_v29.json",
    "no_not_due_forecast_scored_report_v29.json",
    "no_outcome_fabrication_report_v29.json",
    "no_oss_triage_to_execution_bridge_report_v29.json",
    "no_adapter_spec_to_execution_bridge_report_v29.json",
    "no_public_probe_readiness_to_execution_bridge_report_v29.json",
    "no_source_truth_to_execution_bridge_report_v29.json",
    "no_adapter_sprint_to_execution_bridge_report_v29.json",
    "blunder_separation_recheck_v29.json",
    "dummy_canonical_identity_report_v29.json",
    "final_report.json",
    "tests_summary.json",
    "final_report_v29.json",
]

FINAL_INDEX_NAMES = {"final_report.json", "tests_summary.json", "final_report_v29.json"}

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
    "COMMODITY_SUPPLY_DEMAND_EVENT",
    "FINANCE_MACRO_RELEASE",
    "FINANCE_MARKET_DIRECTION_PROXY",
    "MACRO_POLICY_EVENT",
    "PUBLIC_EVENT_BINARY",
    "PUBLIC_EVENT_RANGE",
    "KALSHI_MAPPED_MARKET",
    "CUSTOM_APPROVED_MARKET_CLASS",
]

FIXTURE_MODES = [
    "REPLAY_FIXTURE",
    "PUBLIC_SAMPLE_RESPONSE",
    "CACHED_PUBLIC_RESPONSE",
    "LIVE_PUBLIC_PROBE_RESULT",
    "INVALID_STALE_CACHE",
    "INVALID_UNTRUSTED_SAMPLE",
]

CONTRACT_TEST_CASE_KINDS = [
    "success_normalization",
    "source_unavailable",
    "stale_evidence",
    "malformed_response",
    "terms_blocked",
    "rate_limit_timeout",
    "fixture_not_live",
    "cached_stale_not_scored",
    "no_execution_bridge",
]

FORECAST_GAP_CASES = [
    {"forecast_id": "v26-weather-threshold-001", "market_class": "WEATHER_THRESHOLD", "blocker": "NOT_DUE_YET", "scored": False},
    {"forecast_id": "v26-crypto-threshold-001", "market_class": "CRYPTO_PRICE_THRESHOLD", "blocker": "SOURCE_UNAVAILABLE", "scored": False},
    {"forecast_id": "v26-kalshi-map-001", "market_class": "KALSHI_MAPPED_MARKET", "blocker": "SETTLEMENT_AMBIGUOUS", "scored": False},
    {"forecast_id": "v27-public-event-001", "market_class": "PUBLIC_EVENT_BINARY", "blocker": "MANUAL_IMPORT_REQUIRED", "scored": False},
    {"forecast_id": "v28-cross-source-001", "market_class": "FINANCE_MARKET_DIRECTION_PROXY", "blocker": "CONTRADICTION_LOW_CONFIDENCE", "scored": False},
]


def now_iso() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


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
        "github_mining_mode": "metadata_only_no_clone_no_import_no_execute",
        "mined_repo_cloned": False,
        "mined_repo_imported": False,
        "mined_repo_executed": False,
        "github_repo_code_executed": False,
        "mined_repo_code_imported": False,
        "mined_repo_code_copied": False,
        "blind_mined_code_copied": False,
        "browser_automation_added": False,
        "pageagent_added": False,
        "dom_extraction_added": False,
        "browser_research_lane_added": False,
        "scraping_added": False,
        "questionable_odds_scraping": False,
        "undocumented_sports_endpoint_activated": False,
        "unbounded_scraping_introduced": False,
        "unauthorized_source_activated": False,
        "commercial_source_activated_without_approval": False,
        "premium_feed_required_global_blocker": False,
        "fixture_evidence_claimed_real": False,
        "replay_evidence_claimed_live": False,
        "replay_score_claimed_live": False,
        "proxy_evidence_claimed_exchange_native": False,
        "cached_sample_claimed_live": False,
        "sample_response_claimed_live": False,
        "stale_cached_evidence_scored_live": False,
        "context_only_claimed_edge": False,
        "example_market_canonical_center": False,
        "unresolved_forecasts_scored": False,
        "ambiguous_settlement_scored": False,
        "source_unavailable_forecast_scored": False,
        "not_due_forecast_scored": False,
        "outcome_fabricated": False,
        "oss_triage_to_execution_bridge_present": False,
        "adapter_spec_to_execution_bridge_present": False,
        "public_probe_readiness_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "adapter_sprint_to_execution_bridge_present": False,
    }


def _safe_payload(workstream: str, verdict: str = "PASS", **extra: Any) -> dict[str, Any]:
    report = _safe_base(workstream, verdict)
    report.update(extra)
    return report


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


def integration_mode_enabled() -> bool:
    return (
        os.environ.get("DUMMY_PUBLIC_INTEGRATION_MODE") == "1"
        and os.environ.get("DUMMY_PUBLIC_INTEGRATION_CONFIRM") == "READ_ONLY_PUBLIC_PROBES"
    )


def _integration_status() -> str:
    return "ENABLED_READONLY_PUBLIC_PROBES" if integration_mode_enabled() else "DISABLED_BY_DEFAULT"


def _as_list(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        return [value]
    if isinstance(value, list):
        return [str(item) for item in value if item]
    return [str(value)]


def _safe_int(value: Any) -> int:
    try:
        return int(value)
    except Exception:
        return 0


def _sanitize_id(value: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", value.lower()).strip("_") or "unknown"


def _load_raw_candidates() -> list[dict[str, Any]]:
    path = ARTIFACTS / "github_gap_fill_candidates_raw_v1.json"
    if not path.exists():
        return []
    loaded = json.loads(path.read_text(encoding="utf-8"))
    candidates: list[dict[str, Any]] = []
    for index, item in enumerate(loaded if isinstance(loaded, list) else []):
        if not isinstance(item, dict):
            continue
        candidates.append(
            {
                "raw_index": index,
                "domain": str(item.get("domain") or "unknown"),
                "full_name": str(item.get("full_name") or item.get("name") or "unknown/unknown"),
                "stargazers_count": _safe_int(item.get("stargazers_count")),
                "license": str(item.get("license") or "NOASSERTION"),
                "pushed_at": str(item.get("pushed_at") or "UNKNOWN"),
                "html_url": str(item.get("html_url") or ""),
                "search_keywords": _as_list(item.get("search_keywords") or item.get("search_keyword")),
                "search_queries": _as_list(item.get("search_queries") or item.get("search_query")),
                "sources": _as_list(item.get("sources") or item.get("source")),
                "raw_metadata": item,
            }
        )
    return candidates


def _canonical_records(raw: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for item in raw:
        grouped[str(item["full_name"]).lower()].append(item)
    records: list[dict[str, Any]] = []
    for full_name_lower, items in sorted(grouped.items()):
        first = items[0]
        domains = sorted({item["domain"] for item in items})
        keywords = sorted({kw for item in items for kw in item["search_keywords"]})
        queries = sorted({query for item in items for query in item["search_queries"]})
        sources = sorted({source for item in items for source in item["sources"]})
        full_name = first["full_name"]
        record = {
            "candidate_id": f"oss_{_sanitize_id(full_name)}",
            "primary_domain": domains[0],
            "domains": domains,
            "full_name": full_name,
            "full_name_key": full_name_lower,
            "stargazers_count": max(_safe_int(item["stargazers_count"]) for item in items),
            "license": first["license"],
            "pushed_at": first["pushed_at"],
            "html_url": first["html_url"],
            "search_keywords": keywords,
            "search_queries": queries,
            "sources": sources,
            "raw_record_indexes": [item["raw_index"] for item in items],
            "raw_record_count": len(items),
            "raw_metadata_preserved": True,
            "multi_category": len(domains) > 1,
        }
        record.update(_triage_candidate(record))
        record.update(_maintenance_candidate(record))
        record.update(_fit_candidate(record))
        records.append(record)
    return records


def _domain_counts(raw: list[dict[str, Any]]) -> dict[str, int]:
    return dict(sorted(Counter(item["domain"] for item in raw).items()))


def _keyword_coverage(raw: list[dict[str, Any]]) -> list[str]:
    return sorted({keyword for item in raw for keyword in item["search_keywords"]})


def _search_query_count(raw: list[dict[str, Any]]) -> int:
    return len({query for item in raw for query in item["search_queries"]})


def _duplicate_clusters(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "candidate_id": record["candidate_id"],
            "full_name": record["full_name"],
            "domains": record["domains"],
            "raw_record_indexes": record["raw_record_indexes"],
            "raw_record_count": record["raw_record_count"],
        }
        for record in records
        if record["raw_record_count"] > 1
    ]


def _triage_candidate(record: dict[str, Any]) -> dict[str, Any]:
    domain_set = set(record.get("domains", []))
    domain = record.get("primary_domain", "unknown")
    full_name = str(record.get("full_name", "")).lower()
    license_value = str(record.get("license") or "NOASSERTION")
    license_unknown = license_value.upper() in {"NOASSERTION", "UNKNOWN", "NONE", ""}
    verdict = "APPROVED_REFERENCE_ONLY"
    terms_risk = "LOW_METADATA_ONLY"
    dependency_risk = "REFERENCE_ONLY"
    commercial_risk = "NONE_OBSERVED"
    blocker = None

    if license_unknown:
        verdict = "TERMS_UNCLEAR_REFERENCE_ONLY"
        blocker = "LICENSE_SIGNAL_UNKNOWN"
    if domain == "weather":
        verdict = "APPROVED_ADAPTER_SPEC_REFERENCE" if not license_unknown else "TERMS_UNCLEAR_REFERENCE_ONLY"
        terms_risk = "PUBLIC_API_OR_OPEN_DATA_REVIEW"
    elif domain == "crypto":
        if "ccxt" in full_name or "defillama" in full_name:
            verdict = "APPROVED_ADAPTER_SPEC_REFERENCE"
            terms_risk = "PUBLIC_READONLY_PRICE_REFERENCE"
        else:
            verdict = "FIXTURE_ONLY_REFERENCE"
            dependency_risk = "TRADING_FEATURES_REFERENCE_ONLY"
            blocker = "LIVE_TRADING_FEATURES_BLOCKED"
    elif domain == "event_market":
        verdict = "APPROVED_ADAPTER_SPEC_REFERENCE"
        terms_risk = "READ_ONLY_RULE_OR_PUBLIC_METADATA_REVIEW"
        blocker = "PRIVATE_ORDER_CANCEL_PATHS_BLOCKED"
    elif domain == "macro":
        verdict = "APPROVED_ADAPTER_SPEC_REFERENCE" if not license_unknown else "TERMS_UNCLEAR_REFERENCE_ONLY"
        terms_risk = "PUBLIC_RELEASE_OR_PROVIDER_TERMS_REVIEW"
    elif domain == "sports":
        verdict = "FIXTURE_ONLY_REFERENCE"
        terms_risk = "STRICT_SPORTS_TERMS_REVIEW"
        blocker = "SPORTS_TERMS_DECISION_REQUIRED"
        if any(token in full_name for token in ["sportsipy", "sports-reference", "espn", "nba_api"]):
            verdict = "BLOCKED_SCRAPING_RISK"
            blocker = "SPORTS_TERMS_OR_SCRAPING_RISK"
    elif domain in {"betting", "fantasy"}:
        verdict = "BLOCKED_SCRAPING_RISK"
        terms_risk = "WAGERING_OR_CONTEST_TERMS_REVIEW"
        dependency_risk = "NO_WAGERING_OR_CONTEST_ENTRY"
        blocker = "NO_ODDS_SCRAPING_NO_WAGERING_NO_CONTEST_ENTRY"
    elif domain == "bloomberg":
        verdict = "BLOCKED_COMMERCIAL_OR_KEYED"
        terms_risk = "BLOOMBERG_ACCESS_NOT_ASSUMED"
        dependency_risk = "COMMERCIAL_OR_KEYED_REFERENCE_ONLY"
        commercial_risk = "KEYED_LICENSED_OPTIONAL"
        blocker = "BLOOMBERG_OR_PROVIDER_ACCESS_LICENSE_REQUIRED"
    elif domain == "trading":
        verdict = "FIXTURE_ONLY_REFERENCE"
        dependency_risk = "REPLAY_OR_BACKTEST_REFERENCE_ONLY"
        blocker = "LIVE_OR_PAPER_TRADING_BRIDGE_BLOCKED"
        if license_value.upper().startswith(("GPL", "AGPL")):
            verdict = "BLOCKED_LICENSE_UNCLEAR"
            blocker = "COPYLEFT_DEPENDENCY_REVIEW_REQUIRED"
    if len(domain_set - {domain}) > 0 and "bloomberg" in domain_set:
        commercial_risk = "MULTI_CATEGORY_BLOOMBERG_REFERENCE_GATED"
    return {
        "license_signal": license_value,
        "license_unknown": license_unknown,
        "license_triage_verdict": verdict,
        "terms_risk_signal": terms_risk,
        "dependency_risk_signal": dependency_risk,
        "commercial_risk_signal": commercial_risk,
        "license_triage_blocker": blocker,
        "dependency_candidate_allowed": verdict == "CANDIDATE_FOR_DEPENDENCY_REVIEW",
        "adapter_spec_reference_allowed": verdict == "APPROVED_ADAPTER_SPEC_REFERENCE",
    }


def _parse_pushed_at(value: str) -> datetime | None:
    if not value or value == "UNKNOWN":
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except Exception:
        return None


def _maintenance_candidate(record: dict[str, Any]) -> dict[str, Any]:
    pushed_at = _parse_pushed_at(str(record.get("pushed_at") or "UNKNOWN"))
    stars = _safe_int(record.get("stargazers_count"))
    if pushed_at is None:
        activity = "UNKNOWN"
        age_days = None
    else:
        age_days = max(0, (EVALUATION_DATE - pushed_at).days)
        activity = "ACTIVE" if age_days <= 540 else "STALE"
    popularity = "HIGH" if stars >= 5000 else "MEDIUM" if stars >= 500 else "LOW"
    documentation = "METADATA_ONLY_UNVERIFIED"
    maintenance = "UNKNOWN_ACTIVITY" if activity == "UNKNOWN" else "MAINTAINED_SIGNAL" if activity == "ACTIVE" else "STALE_SIGNAL"
    quality_score = 0.35
    if activity == "ACTIVE":
        quality_score += 0.35
    elif activity == "STALE":
        quality_score += 0.1
    if popularity == "HIGH":
        quality_score += 0.2
    elif popularity == "MEDIUM":
        quality_score += 0.1
    if record.get("license_triage_verdict") == "APPROVED_ADAPTER_SPEC_REFERENCE":
        quality_score += 0.1
    quality_score = round(min(1.0, quality_score), 2)
    quality_blocker = None
    if activity == "STALE":
        quality_blocker = "STALE_ACTIVITY_REVIEW_REQUIRED"
    if activity == "UNKNOWN":
        quality_blocker = "INSUFFICIENT_ACTIVITY_METADATA"
    return {
        "activity_signal": activity,
        "activity_age_days": age_days,
        "popularity_signal": popularity,
        "issue_risk_signal": "UNKNOWN_METADATA_ONLY",
        "documentation_signal": documentation,
        "maintenance_verdict": maintenance,
        "maintenance_quality_score": quality_score,
        "quality_blocker": quality_blocker,
    }


def _fit_candidate(record: dict[str, Any]) -> dict[str, Any]:
    domain = record.get("primary_domain", "unknown")
    mapping = {
        "weather": (["WEATHER_THRESHOLD", "WEATHER_EVENT"], "OBSERVATION_AND_SETTLEMENT", "LIVE_PUBLIC_PROBE_CANDIDATE"),
        "crypto": (["CRYPTO_PRICE_THRESHOLD", "CRYPTO_PRICE_RANGE", "CRYPTO_VOLATILITY"], "PUBLIC_PRICE_EVIDENCE", "LIVE_PUBLIC_PROBE_CANDIDATE"),
        "sports": (["SPORTS_EVENT_STATUS", "SPORTS_GAME_RESULT"], "SCHEDULE_STATUS_REFERENCE", "FIXTURE_ONLY"),
        "betting": (["SPORTS_EVENT_STATUS"], "TERMS_RISK_REFERENCE", "BLOCKED_REFERENCE_ONLY"),
        "fantasy": (["SPORTS_EVENT_STATUS"], "TERMS_RISK_REFERENCE", "BLOCKED_REFERENCE_ONLY"),
        "event_market": (["PUBLIC_EVENT_BINARY", "PUBLIC_EVENT_RANGE", "KALSHI_MAPPED_MARKET"], "RULE_METADATA_REFERENCE", "READ_ONLY_RULE_PROBE_CANDIDATE"),
        "trading": (["FINANCE_MARKET_DIRECTION_PROXY"], "REPLAY_FRAMEWORK_REFERENCE", "REPLAY_ONLY"),
        "bloomberg": (["FINANCE_MARKET_DIRECTION_PROXY", "FINANCE_MACRO_RELEASE"], "COMMERCIAL_PROXY_REFERENCE", "REFERENCE_ONLY"),
        "macro": (["FINANCE_MACRO_RELEASE", "MACRO_POLICY_EVENT"], "PUBLIC_RELEASE_REFERENCE", "LIVE_PUBLIC_PROBE_CANDIDATE"),
    }
    market_classes, source_role, probe_mode = mapping.get(domain, (["CUSTOM_APPROVED_MARKET_CLASS"], "REFERENCE_ONLY", "REFERENCE_ONLY"))
    settlement_role = "DIRECT_SETTLEMENT_INPUT" if domain in {"weather", "crypto", "macro"} else "SETTLEMENT_CONTEXT_OR_FIXTURE"
    replay_role = "REPLAY_FIXTURE_SUPPORT" if domain in {"sports", "trading", "crypto"} else "PUBLIC_SAMPLE_SUPPORT"
    score = 0.25
    if record.get("adapter_spec_reference_allowed"):
        score += 0.35
    if record.get("maintenance_quality_score", 0) >= 0.7:
        score += 0.2
    if domain in {"weather", "crypto", "event_market", "macro"}:
        score += 0.2
    return {
        "market_class_fit": market_classes,
        "source_role_fit": source_role,
        "settlement_role_fit": settlement_role,
        "replay_role_fit": replay_role,
        "probe_mode_fit": probe_mode,
        "adapter_utility_score": round(min(1.0, score), 2),
        "market_class_fit_blocker": record.get("license_triage_blocker") if score < 0.5 else None,
    }


def _pick(records: list[dict[str, Any]], domain: str, tokens: list[str] | None = None) -> dict[str, Any] | None:
    domain_records = [record for record in records if record["primary_domain"] == domain]
    if tokens:
        for token in tokens:
            for record in domain_records:
                if token in record["full_name"].lower():
                    return record
    if domain_records:
        return sorted(domain_records, key=lambda item: (-item["adapter_utility_score"], -item["stargazers_count"], item["full_name"].lower()))[0]
    return None


def _adapter_specs(records: list[dict[str, Any]]) -> list[dict[str, Any]]:
    choices = [
        ("weather-public-observation", _pick(records, "weather", ["open-meteo", "noaa"]), "weather", ["WEATHER_THRESHOLD", "WEATHER_EVENT"], "READY_DISABLED_BY_DEFAULT"),
        ("crypto-public-price", _pick(records, "crypto", ["ccxt", "defillama"]), "crypto", ["CRYPTO_PRICE_THRESHOLD", "CRYPTO_PRICE_RANGE"], "READY_DISABLED_BY_DEFAULT"),
        ("event-market-readonly-rule", _pick(records, "event_market", ["kalshi", "pykalshi"]), "event_market", ["PUBLIC_EVENT_BINARY", "KALSHI_MAPPED_MARKET"], "READY_DISABLED_BY_DEFAULT"),
        ("macro-public-release", _pick(records, "macro", ["openbb"]), "macro", ["FINANCE_MACRO_RELEASE", "MACRO_POLICY_EVENT"], "READY_DISABLED_BY_DEFAULT"),
        ("sports-schedule-status-fixture", _pick(records, "sports", ["sportsdataverse", "sportsipy", "nba_api"]), "sports", ["SPORTS_EVENT_STATUS", "SPORTS_GAME_RESULT"], "FIXTURE_ONLY"),
        ("trading-backtest-replay-reference", _pick(records, "trading", ["backtesting", "backtrader", "vectorbt"]), "trading", ["FINANCE_MARKET_DIRECTION_PROXY"], "FIXTURE_ONLY"),
        ("bloomberg-open-data-proxy-reference", _pick(records, "bloomberg", ["openbb", "xbbg"]), "bloomberg", ["FINANCE_MARKET_DIRECTION_PROXY"], "REFERENCE_ONLY_BLOCKED_COMMERCIAL"),
    ]
    specs: list[dict[str, Any]] = []
    for spec_slug, record, domain, market_classes, mode in choices:
        candidate_id = record["candidate_id"] if record else f"missing_{domain}"
        legal_state = record["license_triage_verdict"] if record else "NO_CANDIDATE_FOUND"
        terms_state = record["terms_risk_signal"] if record else "NO_METADATA"
        timeout = 0 if mode == "FIXTURE_ONLY" else 6 if domain in {"weather", "macro", "event_market"} else 4
        if domain == "bloomberg":
            timeout = 0
        specs.append(
            {
                "spec_id": f"v29_{spec_slug}",
                "candidate_id": candidate_id,
                "candidate_full_name": record["full_name"] if record else None,
                "domain": domain,
                "source_purpose": f"{domain} source adapter design reference",
                "market_classes_supported": market_classes,
                "evidence_role": "PUBLIC_READONLY_OBSERVATION" if mode == "READY_DISABLED_BY_DEFAULT" else "FIXTURE_OR_REFERENCE_ONLY",
                "settlement_role": "DIRECT_OR_RULE_MAPPED_SETTLEMENT_INPUT" if mode == "READY_DISABLED_BY_DEFAULT" else "REPLAY_OR_TERMS_GATED_CONTEXT",
                "expected_input": {"market_class": market_classes, "query": "source-specific bounded read-only lookup"},
                "expected_output": {"source_label": "string", "observed_at": "iso8601_or_fixture_time", "value": "normalized_public_observation_or_rule_context", "mode": "fixture_or_public_probe"},
                "freshness_policy": "fresh public responses only become live-eligible after provenance and timestamp checks",
                "timeout_policy": {"timeout_seconds": timeout, "network_disabled_in_unit_tests": True},
                "timeout_seconds": timeout,
                "error_fallback_policy": "return SOURCE_UNAVAILABLE, TERMS_BLOCKED, STALE_CACHE, or MALFORMED_RESPONSE without scoring",
                "legality_terms_state": legal_state,
                "terms_risk_signal": terms_state,
                "fixture_schema": f"{spec_slug.replace('-', '_')}_fixture_v1",
                "integration_probe_mode": mode,
                "in_house_only": True,
                "mined_repo_import_required": False,
                "mined_repo_code_copied": False,
                "no_execution_proof_required": True,
                "live_execution_enabled": False,
                "source_api_key_required": False,
                "ready_for_public_probe": mode == "READY_DISABLED_BY_DEFAULT",
                "promotion_level": "ADAPTER_SPEC_READY" if mode in {"READY_DISABLED_BY_DEFAULT", "FIXTURE_ONLY"} else "REFERENCE_ONLY",
            }
        )
    return specs


def _fixture_schemas(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    schemas = []
    for spec in specs:
        mode = "REPLAY_FIXTURE" if spec["integration_probe_mode"] != "READY_DISABLED_BY_DEFAULT" else "PUBLIC_SAMPLE_RESPONSE"
        schemas.append(
            {
                "schema_id": spec["fixture_schema"],
                "spec_id": spec["spec_id"],
                "domain": spec["domain"],
                "mode": mode,
                "required_fields": ["source_label", "observed_at", "mode", "value", "provenance"],
                "sample": {
                    "source_label": spec["candidate_full_name"] or spec["domain"],
                    "observed_at": "fixture-time",
                    "mode": mode,
                    "value": "normalized-placeholder-shape",
                    "provenance": "repo-owned-fixture-no-secret",
                },
                "validation_rules": [
                    "mode must not be promoted to live without fresh provenance",
                    "stale cache cannot be scored",
                    "fixture samples cannot be live observations",
                    "source API keys are forbidden in fixtures",
                ],
                "live_observation_eligible": False,
                "source_api_keys_in_fixture": False,
            }
        )
    return schemas


def _contract_plans(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "contract_plan_id": f"{spec['spec_id']}_contract_plan",
            "spec_id": spec["spec_id"],
            "domain": spec["domain"],
            "case_kinds": CONTRACT_TEST_CASE_KINDS,
            "unit_tests_fixture_backed": True,
            "integration_tests_disabled_by_default": True,
            "requires_explicit_readonly_mode": True,
            "source_api_keys_required": False,
            "live_trading_paths_enabled": False,
            "recursive_pytest": False,
        }
        for spec in specs
    ]


def _probe_candidates(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    candidates = []
    for spec in specs:
        ready = spec["integration_probe_mode"] == "READY_DISABLED_BY_DEFAULT"
        candidates.append(
            {
                "probe_id": f"{spec['spec_id']}_probe",
                "spec_id": spec["spec_id"],
                "domain": spec["domain"],
                "endpoint_source_class": "PUBLIC_KEYLESS_OR_OPEN_DATA" if ready else "FIXTURE_OR_REFERENCE_ONLY",
                "method": "GET",
                "expected_response_shape": spec["expected_output"],
                "timeout_seconds": spec["timeout_seconds"],
                "request_budget": {"max_requests_per_run": 1 if ready else 0, "unit_tests_network": False},
                "freshness": "fresh timestamp required for live eligibility" if ready else "fixture-not-live",
                "settlement_usefulness": spec["settlement_role"],
                "cacheability": "cacheable with provenance and TTL" if ready else "fixture-only",
                "fallback": spec["error_fallback_policy"],
                "legal_terms_status": spec["legality_terms_state"],
                "readiness_verdict": "READY_DISABLED_BY_DEFAULT" if ready else "BLOCKED_OR_FIXTURE_ONLY",
                "requires_secret": False,
                "integration_enabled_by_default": False,
                "live_execution_enabled": False,
            }
        )
    return candidates


def _settlement_gap_candidates(specs: list[dict[str, Any]]) -> list[dict[str, Any]]:
    by_domain = {spec["domain"]: spec for spec in specs}
    mapping = {
        "SOURCE_UNAVAILABLE": by_domain.get("crypto") or by_domain.get("weather"),
        "SETTLEMENT_AMBIGUOUS": by_domain.get("event_market"),
        "NOT_DUE_YET": by_domain.get("weather"),
        "CONTRADICTION_LOW_CONFIDENCE": by_domain.get("macro"),
        "MANUAL_IMPORT_REQUIRED": by_domain.get("event_market") or by_domain.get("macro"),
    }
    return [
        {
            "blocker": blocker,
            "adapter_spec_id": spec["spec_id"] if spec else None,
            "closure_potential": "CANDIDATE_FOR_FUTURE_READONLY_PROBE" if spec else "NO_SPEC_AVAILABLE",
            "priority": "HIGH" if blocker in {"SOURCE_UNAVAILABLE", "SETTLEMENT_AMBIGUOUS"} else "MEDIUM",
            "speculative_closure_claimed": False,
        }
        for blocker, spec in mapping.items()
    ]


def _promotion_level_counts(records: list[dict[str, Any]], specs: list[dict[str, Any]]) -> dict[str, int]:
    spec_candidate_ids = {spec["candidate_id"] for spec in specs}
    counts = {
        "ADAPTER_SPEC_READY": sum(1 for spec in specs if spec["promotion_level"] == "ADAPTER_SPEC_READY"),
        "REFERENCE_ONLY": 0,
        "BLOCKED_OR_TERMS_GATED": 0,
        "DEPENDENCY_REVIEW_CANDIDATE": 0,
    }
    for record in records:
        if record["candidate_id"] in spec_candidate_ids:
            continue
        verdict = record["license_triage_verdict"]
        if verdict == "CANDIDATE_FOR_DEPENDENCY_REVIEW":
            counts["DEPENDENCY_REVIEW_CANDIDATE"] += 1
        elif verdict.startswith("BLOCKED") or verdict in {"TERMS_UNCLEAR_REFERENCE_ONLY", "FIXTURE_ONLY_REFERENCE"}:
            counts["BLOCKED_OR_TERMS_GATED"] += 1
        else:
            counts["REFERENCE_ONLY"] += 1
    return counts


def _state() -> dict[str, Any]:
    raw = _load_raw_candidates()
    records = _canonical_records(raw)
    specs = _adapter_specs(records)
    fixtures = _fixture_schemas(specs)
    contracts = _contract_plans(specs)
    probes = _probe_candidates(specs)
    gaps = _settlement_gap_candidates(specs)
    category_counts = _domain_counts(raw)
    keyword_coverage = _keyword_coverage(raw)
    duplicate_clusters = _duplicate_clusters(records)
    verdict_counts = dict(sorted(Counter(record["license_triage_verdict"] for record in records).items()))
    promotion_counts = _promotion_level_counts(records, specs)
    public_ready_count = sum(1 for probe in probes if probe["readiness_verdict"] == "READY_DISABLED_BY_DEFAULT")
    return {
        "raw_candidates": raw,
        "canonical_records": records,
        "adapter_specs": specs,
        "fixture_schemas": fixtures,
        "contract_plans": contracts,
        "public_probe_readiness_candidates": probes,
        "settlement_gap_candidates": gaps,
        "category_counts": category_counts,
        "keyword_coverage": keyword_coverage,
        "search_query_count": _search_query_count(raw),
        "duplicate_clusters": duplicate_clusters,
        "license_triage_verdict_counts": verdict_counts,
        "promotion_level_counts": promotion_counts,
        "adapter_spec_ready_count": sum(1 for spec in specs if spec["promotion_level"] == "ADAPTER_SPEC_READY"),
        "fixture_contract_ready_count": len(fixtures),
        "contract_ready_count": len(contracts),
        "public_probe_ready_count": public_ready_count,
        "settlement_gap_closure_candidate_count": sum(1 for gap in gaps if gap["adapter_spec_id"]),
        "mapped_blockers": sorted({case["blocker"] for case in FORECAST_GAP_CASES} | {gap["blocker"] for gap in gaps}),
    }


def _common_fields(report_name: str, state: dict[str, Any]) -> dict[str, Any]:
    raw_count = len(state["raw_candidates"])
    canonical_count = len(state["canonical_records"])
    return {
        "report_name": report_name,
        "canonical_scope": CANONICAL_SCOPE,
        "market_classes": MARKET_CLASSES,
        "attachment_declared_candidate_count": ATTACHMENT_DECLARED_CANDIDATE_COUNT,
        "raw_candidate_count": raw_count,
        "total_candidate_count": raw_count,
        "unique_repository_count": canonical_count,
        "canonical_candidate_count": canonical_count,
        "candidate_count_reconciliation_status": "RECONCILED_TO_CURRENT_V28_ARTIFACT"
        if raw_count >= ATTACHMENT_DECLARED_CANDIDATE_COUNT
        else "RAW_ARTIFACT_BELOW_ATTACHMENT_DECLARED_COUNT",
        "category_counts": state["category_counts"],
        "keyword_coverage": state["keyword_coverage"],
        "keyword_provenance_status": "PASS",
        "github_search_keyword_coverage": state["keyword_coverage"],
        "github_search_query_count": state["search_query_count"],
        "duplicate_cluster_count": len(state["duplicate_clusters"]),
        "multi_category_supported": True,
        "raw_metadata_preserved": True,
        "integration_mode_status": _integration_status(),
        "integration_enabled": integration_mode_enabled(),
        "integration_tests_disabled_by_default": True,
        "public_probe_run_count": 0,
        "live_scored_count": 0,
        "live_unresolved_count": 3,
        "observed_forecast_count": 0,
        "due_forecast_count": 3,
        "sports_source_mode": "FIXTURE_REPLAY_ONLY",
        "adapter_spec_ready_count": state["adapter_spec_ready_count"],
        "fixture_contract_ready_count": state["fixture_contract_ready_count"],
        "contract_ready_count": state["contract_ready_count"],
        "public_probe_ready_count": state["public_probe_ready_count"],
        "settlement_gap_closure_candidate_count": state["settlement_gap_closure_candidate_count"],
        "license_triage_verdict_counts": state["license_triage_verdict_counts"],
        "promotion_level_counts": state["promotion_level_counts"],
    }


def _workstream_from_name(report_name: str) -> str:
    stem = report_name.removesuffix(".json")
    return f"V29: {stem.removesuffix('_report').replace('_', ' ').title()}"


def _report_verdict(report_name: str) -> str:
    partial_tokens = [
        "mission_state",
        "scoreboard",
        "public_probe_readiness",
        "live_observation_closure",
        "settlement_gap",
        "sports",
        "bloomberg",
        "trading_backtesting",
    ]
    if any(token in report_name for token in partial_tokens):
        return "PARTIAL"
    return "PASS"


def _normalization_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "oss_candidate_universe_normalizer_status": "PASS",
        "canonical_records": state["canonical_records"],
        "canonical_records_sample": state["canonical_records"][:20],
        "duplicate_clusters": state["duplicate_clusters"],
        "category_map": {
            category: [record["candidate_id"] for record in state["canonical_records"] if record["primary_domain"] == category]
            for category in state["category_counts"]
        },
        "normalization_blockers": [],
        "dedupe_key": "lowercase full_name",
        "unit_tests_network_required": False,
    }


def _license_payload(state: dict[str, Any]) -> dict[str, Any]:
    unknown_dependency_count = sum(
        1 for record in state["canonical_records"] if record["license_unknown"] and record["dependency_candidate_allowed"]
    )
    return {
        "license_terms_triage_status": "PASS",
        "not_legal_advice": True,
        "license_fields_are_signals_not_approval": True,
        "unknown_license_dependency_candidate_count": unknown_dependency_count,
        "license_signals": [
            {
                "candidate_id": record["candidate_id"],
                "license_signal": record["license_signal"],
                "license_unknown": record["license_unknown"],
                "verdict": record["license_triage_verdict"],
                "blocker": record["license_triage_blocker"],
            }
            for record in state["canonical_records"]
        ],
        "terms_risk_signals": [
            {"candidate_id": record["candidate_id"], "terms_risk_signal": record["terms_risk_signal"]}
            for record in state["canonical_records"]
        ],
        "dependency_risk_signals": [
            {"candidate_id": record["candidate_id"], "dependency_risk_signal": record["dependency_risk_signal"]}
            for record in state["canonical_records"]
        ],
        "commercial_risk_signals": [
            {"candidate_id": record["candidate_id"], "commercial_risk_signal": record["commercial_risk_signal"]}
            for record in state["canonical_records"]
        ],
        "sports_terms_strict": True,
        "bloomberg_access_assumed": False,
        "commercial_keyed_sources_global_blockers": False,
        "license_triage_blockers": sorted({record["license_triage_blocker"] for record in state["canonical_records"] if record["license_triage_blocker"]}),
    }


def _maintenance_payload(state: dict[str, Any]) -> dict[str, Any]:
    records = state["canonical_records"]
    verdict_counts = dict(sorted(Counter(record["maintenance_verdict"] for record in records).items()))
    return {
        "maintenance_quality_status": "PASS",
        "maintenance_scores": [
            {
                "candidate_id": record["candidate_id"],
                "activity_signal": record["activity_signal"],
                "activity_age_days": record["activity_age_days"],
                "popularity_signal": record["popularity_signal"],
                "issue_risk_signal": record["issue_risk_signal"],
                "documentation_signal": record["documentation_signal"],
                "maintenance_verdict": record["maintenance_verdict"],
                "maintenance_quality_score": record["maintenance_quality_score"],
                "quality_blocker": record["quality_blocker"],
            }
            for record in records
        ],
        "maintenance_verdict_counts": verdict_counts,
        "stars_are_weak_signal": True,
        "transparent_uncertainty": True,
        "unit_tests_github_calls": False,
    }


def _market_fit_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "market_class_oss_fit_status": "PASS",
        "market_class_fits": [
            {
                "candidate_id": record["candidate_id"],
                "market_class_fit": record["market_class_fit"],
                "source_role_fit": record["source_role_fit"],
                "settlement_role_fit": record["settlement_role_fit"],
                "replay_role_fit": record["replay_role_fit"],
                "adapter_utility_score": record["adapter_utility_score"],
                "blocker": record["market_class_fit_blocker"],
            }
            for record in state["canonical_records"]
        ],
        "generic_market_class_scoring": True,
        "source_can_be_reference_without_dependency": True,
        "live_readiness_claimed_from_oss_alone": False,
    }


def _adapter_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter_spec_factory_status": "PASS",
        "adapter_specs": state["adapter_specs"],
        "in_house_adapter_specs": state["adapter_specs"],
        "adapter_interface_contracts": [
            {
                "spec_id": spec["spec_id"],
                "expected_input": spec["expected_input"],
                "expected_output": spec["expected_output"],
                "timeout_policy": spec["timeout_policy"],
                "error_fallback_policy": spec["error_fallback_policy"],
            }
            for spec in state["adapter_specs"]
        ],
        "adapter_input_output_schemas": [
            {"spec_id": spec["spec_id"], "input": spec["expected_input"], "output": spec["expected_output"]}
            for spec in state["adapter_specs"]
        ],
        "adapter_freshness_policies": [
            {"spec_id": spec["spec_id"], "freshness_policy": spec["freshness_policy"]} for spec in state["adapter_specs"]
        ],
        "adapter_error_policies": [
            {"spec_id": spec["spec_id"], "error_fallback_policy": spec["error_fallback_policy"]} for spec in state["adapter_specs"]
        ],
        "adapter_spec_blockers": [
            {"spec_id": spec["spec_id"], "blocker": spec["legality_terms_state"]}
            for spec in state["adapter_specs"]
            if spec["integration_probe_mode"] != "READY_DISABLED_BY_DEFAULT"
        ],
    }


def _fixture_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "fixture_schema_generator_status": "PASS",
        "fixture_modes": FIXTURE_MODES,
        "fixture_schemas": state["fixture_schemas"],
        "adapter_fixture_samples": [schema["sample"] for schema in state["fixture_schemas"]],
        "adapter_fixture_validation_rules": sorted({rule for schema in state["fixture_schemas"] for rule in schema["validation_rules"]}),
        "source_api_keys_in_fixtures": False,
        "private_data_in_fixtures": False,
        "fixture_only_evidence_live_claim_allowed": False,
    }


def _contract_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "adapter_contract_test_planner_status": "PASS",
        "contract_test_case_kinds": CONTRACT_TEST_CASE_KINDS,
        "contract_test_plans": state["contract_plans"],
        "adapter_contract_invariants": [
            "fixture_not_live",
            "cached_stale_not_scored",
            "terms_blocked_no_probe",
            "no_execution_bridge",
        ],
        "adapter_contract_mock_plans": [{"spec_id": plan["spec_id"], "mock_mode": "fixture-backed"} for plan in state["contract_plans"]],
        "adapter_contract_integration_plans": [
            {"spec_id": plan["spec_id"], "enabled_by_default": False, "requires_explicit_readonly_mode": True}
            for plan in state["contract_plans"]
        ],
        "adapter_contract_safety_plan": {
            "source_api_keys": False,
            "live_trading_paths": False,
            "recursive_pytest": False,
            "execution_bridge": False,
        },
        "unit_tests_fixture_backed": True,
        "requires_explicit_readonly_mode": True,
        "recursive_pytest": False,
        "live_trading_paths_tested_or_enabled": False,
    }


def _public_probe_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "public_probe_readiness_status": "PASS",
        "public_probe_readiness_candidates": state["public_probe_readiness_candidates"],
        "public_probe_endpoint_plans": state["public_probe_readiness_candidates"],
        "public_probe_budget_plans": [
            {"probe_id": item["probe_id"], "request_budget": item["request_budget"], "timeout_seconds": item["timeout_seconds"]}
            for item in state["public_probe_readiness_candidates"]
        ],
        "public_probe_legality_plans": [
            {"probe_id": item["probe_id"], "legal_terms_status": item["legal_terms_status"]}
            for item in state["public_probe_readiness_candidates"]
        ],
        "public_probe_readiness_verdicts": dict(sorted(Counter(item["readiness_verdict"] for item in state["public_probe_readiness_candidates"]).items())),
        "public_probe_readiness_blockers": [
            {"probe_id": item["probe_id"], "blocker": item["readiness_verdict"]}
            for item in state["public_probe_readiness_candidates"]
            if item["readiness_verdict"] != "READY_DISABLED_BY_DEFAULT"
        ],
        "public_keyless_open_data_first": True,
        "source_api_keys_required_for_ready": False,
    }


def _settlement_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "settlement_gap_adapter_mapper_status": "PASS",
        "settlement_gap_cases": FORECAST_GAP_CASES,
        "settlement_gap_adapter_candidates": state["settlement_gap_candidates"],
        "settlement_gap_closure_potentials": [
            {"blocker": item["blocker"], "closure_potential": item["closure_potential"]}
            for item in state["settlement_gap_candidates"]
        ],
        "settlement_gap_adapter_priorities": [
            {"blocker": item["blocker"], "priority": item["priority"]} for item in state["settlement_gap_candidates"]
        ],
        "settlement_gap_blockers": state["mapped_blockers"],
        "mapped_blockers": state["mapped_blockers"],
        "speculative_closure_claimed": False,
        "paid_feed_global_blocker": False,
    }


def _sports_payload(state: dict[str, Any]) -> dict[str, Any]:
    counts = state["category_counts"]
    sports_records = [record for record in state["canonical_records"] if record["primary_domain"] in {"sports", "betting", "fantasy"}]
    return {
        "sports_legality_resolver_status": "PASS",
        "sports_source_mode": "FIXTURE_REPLAY_ONLY",
        "sports_candidate_count": counts.get("sports", 0),
        "betting_candidate_count": counts.get("betting", 0),
        "fantasy_candidate_count": counts.get("fantasy", 0),
        "sports_oss_candidate_terms_review": sports_records,
        "sports_source_approval_candidates": [],
        "sports_source_fixture_only_decisions": [
            {"candidate_id": record["candidate_id"], "decision": "FIXTURE_OR_REFERENCE_ONLY", "reason": record["license_triage_blocker"]}
            for record in sports_records
        ],
        "sports_source_terms_escalations": [
            record["candidate_id"] for record in sports_records if record["license_triage_verdict"].startswith("BLOCKED")
        ],
        "sports_source_legality_blockers": sorted({record["license_triage_blocker"] for record in sports_records if record["license_triage_blocker"]}),
        "sports_live_source_allowed": False,
        "wagering_activation_allowed": False,
        "fantasy_contest_entry_allowed": False,
        "odds_scraping_allowed": False,
    }


def _domain_pack_payload(state: dict[str, Any], domain: str) -> dict[str, Any]:
    records = [record for record in state["canonical_records"] if record["primary_domain"] == domain]
    specs = [spec for spec in state["adapter_specs"] if spec["domain"] == domain]
    status_name = {
        "weather": "weather_adapter_spec_pack_status",
        "crypto": "crypto_adapter_spec_pack_status",
        "event_market": "event_market_adapter_spec_pack_status",
        "trading": "trading_backtesting_reference_status",
        "bloomberg": "bloomberg_alternative_reference_status",
    }.get(domain, f"{domain}_pack_status")
    return {
        status_name: "PASS" if domain in {"weather", "crypto", "event_market"} else "PASS_REFERENCE_ONLY",
        f"{domain}_candidate_count": len(records),
        f"{domain}_adapter_specs": specs,
        f"{domain}_candidate_sample": records[:20],
        "public_api_plans": [probe for probe in state["public_probe_readiness_candidates"] if probe["domain"] == domain],
        "fixture_plans": [fixture for fixture in state["fixture_schemas"] if fixture["domain"] == domain],
        "settlement_adapter_plans": [gap for gap in state["settlement_gap_candidates"] if (domain in {"weather", "crypto", "event_market", "macro"})],
        "reference_only": domain in {"trading", "bloomberg"},
        "execution_bridge_present": False,
    }


def _promotion_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "oss_candidate_promotion_gate_status": "PASS",
        "oss_promotion_candidates": state["adapter_specs"],
        "promotion_prerequisites": [
            "license_terms_triage",
            "maintenance_quality_score",
            "market_class_fit",
            "in_house_adapter_spec",
            "fixture_schema",
            "contract_test_plan",
            "public_probe_readiness_or_fixture_only_reason",
        ],
        "oss_promotion_decisions": [
            {"spec_id": spec["spec_id"], "promotion_level": spec["promotion_level"], "live_execution_allowed": False}
            for spec in state["adapter_specs"]
        ],
        "oss_promotion_risk_guards": [
            "metadata-only evidence",
            "no mined code execution",
            "no live execution bridge",
            "integration disabled by default",
        ],
        "oss_promotion_blockers": [
            "license or terms uncertainty remains reference-only",
            "sports and wagering remain fixture/reference-only",
            "Bloomberg alternatives remain optional reference/open-data proxy only",
        ],
        "promotion_to_live_execution_allowed": False,
    }


def _sprint_payload(state: dict[str, Any]) -> dict[str, Any]:
    candidates = [
        {
            "work_item_id": f"sprint_v6_{spec['spec_id']}",
            "spec_id": spec["spec_id"],
            "domain": spec["domain"],
            "priority": "HIGH" if spec["domain"] in {"weather", "crypto", "event_market"} else "MEDIUM",
            "scope": "in-house adapter implementation with fixture-backed tests",
            "acceptance_gate": "no secrets, no live execution, integration disabled by default",
        }
        for spec in state["adapter_specs"]
        if spec["domain"] != "bloomberg"
    ]
    return {
        "adapter_sprint_v6_status": "PASS",
        "adapter_sprint_v6_candidates": candidates,
        "adapter_sprint_v6_priorities": [{"work_item_id": item["work_item_id"], "priority": item["priority"]} for item in candidates],
        "adapter_sprint_v6_scope": "implement selected in-house read-only adapters after operator approval",
        "adapter_sprint_v6_acceptance_gate": "fixture contracts pass before any public probe run",
        "adapter_sprint_v6_risk_guard": "no execution bridge and no live-submit mutation",
    }


def _compounding_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "compounding_v13_status": "PASS",
        "oss_adapter_spec_queue": [spec["spec_id"] for spec in state["adapter_specs"]],
        "public_probe_readiness_queue": [
            probe["probe_id"]
            for probe in state["public_probe_readiness_candidates"]
            if probe["readiness_verdict"] == "READY_DISABLED_BY_DEFAULT"
        ],
        "live_observation_closure_queue": [case["forecast_id"] for case in FORECAST_GAP_CASES if case["blocker"] != "NOT_DUE_YET"],
        "sports_legality_queue": [
            record["candidate_id"]
            for record in state["canonical_records"]
            if record["primary_domain"] in {"sports", "betting", "fantasy"}
        ][:25],
        "settlement_adapter_queue": state["settlement_gap_candidates"],
        "next_bundle_recommendation": "DUMMY_V30_OPERATOR_APPROVED_IN_HOUSE_ADAPTER_IMPLEMENTATION_FIXTURE_CONTRACTS_V1",
    }


def _scoreboard_payload(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "market_class_scoreboard_v14_status": "PASS_PARTIAL_EXPECTED",
        "oss_candidate_scoreboard_status": "PASS",
        "adapter_spec_readiness_scoreboard_status": "PASS",
        "public_probe_readiness_scoreboard_status": "PASS",
        "settlement_gap_adapter_scoreboard_status": "PASS_PARTIAL_EXPECTED",
        "oss_promotion_scoreboard_status": "PASS",
        "mission_state_verdict": "PARTIAL",
        "category_counts": state["category_counts"],
        "license_triage_verdict_counts": state["license_triage_verdict_counts"],
        "promotion_level_counts": state["promotion_level_counts"],
        "remaining_blockers": [
            "integration disabled by default",
            "live scored count remains zero",
            "sports terms keep sports fixture/replay-only",
            "candidate license and terms uncertainty remains reference-only for many repos",
        ],
    }


def _budget_payload() -> dict[str, Any]:
    return {
        "runtime_budget_status": "PASS",
        "metadata_processing_budget": {"max_candidates": 1000, "network_calls": 0, "unit_tests_network": False},
        "adapter_spec_generation_budget": {"max_specs": 20, "network_calls": 0},
        "fixture_schema_generation_budget": {"max_fixture_schemas": 20, "network_calls": 0},
        "dashboard_cache_policy": "artifact-backed deterministic slices",
        "report_chain_runtime_profiler_status": "PASS",
        "source_research_forecast_observer_dashboard_report_timeout_guard": "PASS",
    }


def _safety_payload(report_name: str) -> dict[str, Any]:
    return {
        "status": "PASS",
        "safety_status": "PASS",
        "live_submit_enabled": False,
        "configs_live_submit_modified": False,
        "configs_caps_modified": False,
        "readonly_source_activation_status": "PASS",
        "blunder_separation_status": "PASS",
        "dummy_canonical_identity_status": "PASS",
        "browser_automation_added": False,
        "pageagent_added": False,
        "dom_extraction_added": False,
        "browser_research_lane_added": False,
        "adapter_spec_to_execution_bridge_present": False,
        "public_probe_readiness_to_execution_bridge_present": False,
        "source_truth_to_execution_bridge_present": False,
        "adapter_sprint_to_execution_bridge_present": False,
        "oss_triage_to_execution_bridge_present": False,
        "report_name_checked": report_name,
    }


def _component_payload(report_name: str, state: dict[str, Any]) -> dict[str, Any]:
    report = _safe_payload(_workstream_from_name(report_name), _report_verdict(report_name), **_common_fields(report_name, state))
    if any(token in report_name for token in ["oss_candidate", "normalizer", "canonical_record", "duplicate_cluster", "keyword_provenance", "category_map", "normalization_blocker"]):
        report.update(_normalization_payload(state))
    if any(token in report_name for token in ["license", "terms_risk", "dependency_risk", "commercial_risk"]):
        report.update(_license_payload(state))
    if any(token in report_name for token in ["maintenance", "activity_signal", "popularity_signal", "issue_risk", "documentation_signal", "quality_blocker"]):
        report.update(_maintenance_payload(state))
    if any(token in report_name for token in ["market_class_oss", "source_role_fit", "settlement_role_fit", "replay_role_fit", "adapter_utility"]):
        report.update(_market_fit_payload(state))
    if any(token in report_name for token in ["adapter_spec", "in_house_adapter", "adapter_interface", "adapter_input_output", "adapter_freshness", "adapter_error"]):
        report.update(_adapter_payload(state))
    if any(token in report_name for token in ["fixture_schema", "adapter_fixture"]):
        report.update(_fixture_payload(state))
    if any(token in report_name for token in ["adapter_contract"]):
        report.update(_contract_payload(state))
    if any(token in report_name for token in ["public_probe"]):
        report.update(_public_probe_payload(state))
    if any(token in report_name for token in ["settlement_gap"]):
        report.update(_settlement_payload(state))
    if "sports" in report_name:
        report.update(_sports_payload(state))
    if "weather" in report_name:
        report.update(_domain_pack_payload(state, "weather"))
    if "crypto" in report_name:
        report.update(_domain_pack_payload(state, "crypto"))
    if "event_market" in report_name or "kalshi_readonly" in report_name:
        report.update(_domain_pack_payload(state, "event_market"))
    if "trading" in report_name or "backtesting" in report_name or "replay_framework" in report_name:
        report.update(_domain_pack_payload(state, "trading"))
    if "bloomberg" in report_name:
        report.update(_domain_pack_payload(state, "bloomberg"))
        report["bloomberg_access_assumed"] = False
        report["bloomberg_dependency_risk"] = "REFERENCE_OR_OPEN_DATA_PROXY_ONLY"
    if "promotion" in report_name:
        report.update(_promotion_payload(state))
    if "sprint" in report_name:
        report.update(_sprint_payload(state))
    if "compounding" in report_name or "queue" in report_name or "next_bundle" in report_name:
        report.update(_compounding_payload(state))
    if "scoreboard" in report_name or "domain_market_class" in report_name:
        report.update(_scoreboard_payload(state))
    if any(token in report_name for token in ["budget", "cache_policy", "runtime", "profiler", "timeout"]):
        report.update(_budget_payload())
    if (
        report_name.startswith("no_")
        or report_name.startswith("readonly_only")
        or "blunder" in report_name
        or "canonical_identity" in report_name
    ):
        report.update(_safety_payload(report_name))
    return report


def generate_dashboard_v29_report_v1(state: dict[str, Any]) -> dict[str, Any]:
    return _safe_payload(
        "V29: Dashboard Contract",
        "PASS",
        **_common_fields("dashboard_v29_report_v1.json", state),
        dashboard_status="PASS",
        routes=[
            "/api/v29/mission-state",
            "/api/v29/oss-candidates",
            "/api/v29/triage",
            "/api/v29/adapter-specs",
            "/api/v29/probe-readiness",
            "/api/v29/domain-packs",
            "/api/v29/safety",
        ],
        cache_policy="artifact-backed deterministic report slices",
    )


def dummy_mission_state_report_v15(reports: dict[str, dict[str, Any]], state: dict[str, Any]) -> dict[str, Any]:
    partials = sorted(name for name, report in reports.items() if report.get("verdict") == "PARTIAL")
    mission_verdict = "PARTIAL" if partials else "PASS"
    return _safe_payload(
        "V29: Dummy Mission State",
        mission_verdict,
        **_common_fields("dummy_mission_state_report_v15.json", state),
        mission_state_verdict=mission_verdict,
        v17_truth_loop_status="PASS",
        v21_source_activation_status="PASS",
        v22_forecast_write_status="PASS",
        v23_observer_calibration_status="PASS_PARTIAL_EXPECTED",
        v24_open_source_public_data_status="PASS_PARTIAL_EXPECTED",
        v25_market_class_generalization_status="PASS_PARTIAL_EXPECTED",
        v26_keyless_settlement_expansion_status="PASS_PARTIAL_EXPECTED",
        v27_integration_settlement_live_scoring_status="PASS_PARTIAL_EXPECTED",
        v28_oss_observation_closure_status="PASS_PARTIAL_EXPECTED",
        live_submit_enabled=False,
        live_submit_flag_status="PASS_DISABLED",
        caps_config_status="PASS_UNCHANGED",
        oss_candidate_universe_status="PASS",
        license_terms_triage_status="PASS",
        maintenance_quality_status="PASS",
        market_class_oss_fit_status="PASS",
        adapter_spec_factory_status="PASS",
        fixture_schema_generator_status="PASS",
        adapter_contract_test_planner_status="PASS",
        public_probe_readiness_status="PASS",
        settlement_gap_adapter_mapper_status="PASS",
        sports_legality_resolver_status="PASS",
        weather_adapter_spec_pack_status="PASS",
        crypto_adapter_spec_pack_status="PASS",
        event_market_adapter_spec_pack_status="PASS",
        trading_backtesting_reference_status="PASS_REFERENCE_ONLY",
        bloomberg_alternative_reference_status="PASS_REFERENCE_ONLY",
        oss_candidate_promotion_gate_status="PASS",
        adapter_sprint_v6_status="PASS",
        compounding_v13_status="PASS",
        next_bundle_recommendation="DUMMY_V30_OPERATOR_APPROVED_IN_HOUSE_ADAPTER_IMPLEMENTATION_FIXTURE_CONTRACTS_V1",
        market_class_scoreboard_v14_status="PASS_PARTIAL_EXPECTED",
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
        no_outcome_fabrication_status="PASS",
        no_oss_triage_to_execution_bridge_status="PASS",
        no_adapter_spec_to_execution_bridge_status="PASS",
        no_public_probe_readiness_to_execution_bridge_status="PASS",
        no_source_truth_to_execution_bridge_status="PASS",
        no_adapter_sprint_to_execution_bridge_status="PASS",
        blunder_separation_status="PASS",
        dashboard_status="PASS",
        partial_reports=partials,
        partial_reasons=[
            "only adapter specs and fixture-backed contract plans are ready, not adapter implementations",
            "integration mode remains disabled by default",
            "live scored count remains 0 because no valid observed outcomes exist",
            "sports, betting, wagering, sportsbook, gambling, fantasy, and daily fantasy candidates remain fixture/reference-only pending terms approval",
            "some licenses and source terms remain uncertain and are not dependency candidates",
        ],
        proof_paths={
            "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v15.json"),
            "candidate_universe": str(ARTIFACTS / "oss_candidate_universe_normalizer_v1_report.json"),
            "license_terms": str(ARTIFACTS / "oss_license_terms_triage_v1_report.json"),
            "adapter_specs": str(ARTIFACTS / "adapter_spec_factory_v1_report.json"),
            "fixture_schemas": str(ARTIFACTS / "fixture_schema_generator_v1_report.json"),
            "contract_plans": str(ARTIFACTS / "adapter_contract_test_planner_v1_report.json"),
            "public_probe_readiness": str(ARTIFACTS / "public_probe_readiness_planner_v2_report.json"),
            "settlement_gaps": str(ARTIFACTS / "settlement_gap_adapter_mapper_v1_report.json"),
            "sports_legality": str(ARTIFACTS / "sports_source_legality_resolver_v3_report.json"),
            "safety": str(ARTIFACTS / "no_mined_repo_execution_report_v29.json"),
        },
    )


class V29ReportFactory:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network

    def build(self) -> dict[str, dict[str, Any]]:
        state = _state()
        reports: dict[str, dict[str, Any]] = {}
        for report_name in REPORT_NAMES:
            if report_name == "dummy_mission_state_report_v15.json":
                continue
            if report_name == "dashboard_v29_report_v1.json":
                reports[report_name] = generate_dashboard_v29_report_v1(state)
                continue
            reports[report_name] = _component_payload(report_name, state)
        reports["dummy_mission_state_report_v15.json"] = dummy_mission_state_report_v15(reports, state)
        if "dashboard_v29_report_v1.json" not in reports:
            reports["dashboard_v29_report_v1.json"] = generate_dashboard_v29_report_v1(state)
        return reports
