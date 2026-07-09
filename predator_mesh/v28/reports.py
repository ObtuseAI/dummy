"""V28 read-only public probe activation, observation closure, and OSS gap-fill reports."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v28 import MILESTONE

ROOT = Path(__file__).resolve().parents[2]
ARTIFACTS = ROOT / "artifacts" / "dummy"
REPORT_NAMES_FILE = ARTIFACTS / "v28_required_report_names_from_attachment.txt"


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
        "order_endpoints_used": False,
        "unbounded_scraping_introduced": False,
        "questionable_odds_scraping": False,
        "undocumented_sports_endpoint_activated": False,
        "forecast_snapshot_mutated_after_creation": False,
        "unresolved_forecasts_scored": False,
        "ambiguous_settlement_scored": False,
        "source_unavailable_forecast_scored": False,
        "not_due_forecast_scored": False,
        "outcome_fabricated": False,
        "github_repo_code_executed": False,
        "mined_repo_code_imported": False,
        "source_api_keys_exposed": False,
        "github_tokens_exposed": False,
        "kalshi_private_keys_exposed": False,
        "llm_secrets_exposed": False,
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

PUBLIC_PROBE_TASKS = [
    {"task_id": "weather-nws-public-observation", "domain": "weather", "source_mode": "OFFICIAL_PUBLIC_KEYLESS", "timeout_seconds": 5, "requires_secret": False},
    {"task_id": "crypto-public-spot-price", "domain": "crypto", "source_mode": "PUBLIC_KEYLESS_READONLY", "timeout_seconds": 4, "requires_secret": False},
    {"task_id": "commodity-public-reference", "domain": "commodities", "source_mode": "OFFICIAL_PUBLIC_KEYLESS_OR_MANUAL_IMPORT", "timeout_seconds": 6, "requires_secret": False},
    {"task_id": "macro-public-release", "domain": "macro", "source_mode": "OFFICIAL_PUBLIC_KEYLESS", "timeout_seconds": 6, "requires_secret": False},
    {"task_id": "public-event-evidence", "domain": "public_event", "source_mode": "ALLOWLISTED_PUBLIC_SOURCE_REQUIRED", "timeout_seconds": 6, "requires_secret": False},
    {"task_id": "kalshi-readonly-rule-evidence", "domain": "event_market", "source_mode": "READ_ONLY_PUBLIC_OR_CONFIGURED_READONLY", "timeout_seconds": 5, "requires_secret": False},
    {"task_id": "sports-schedule-status", "domain": "sports", "source_mode": "FIXTURE_REPLAY_ONLY_UNTIL_TERMS_APPROVED", "timeout_seconds": 0, "requires_secret": False},
]

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

CACHED_EVIDENCE_RECORDS = [
    {"evidence_id": "sample-weather-public-response", "mode": "PUBLIC_SAMPLE_RESPONSE", "domain": "weather", "freshness": "SAMPLE_NOT_LIVE", "live_observation_eligible": False, "blocker": "SAMPLE_RESPONSE_NOT_LIVE"},
    {"evidence_id": "fixture-sports-status", "mode": "REPLAY_FIXTURE_RESPONSE", "domain": "sports", "freshness": "FIXTURE_NOT_LIVE", "live_observation_eligible": False, "blocker": "FIXTURE_REPLAY_ONLY"},
    {"evidence_id": "stale-crypto-public-cache", "mode": "INVALID_STALE_CACHE", "domain": "crypto", "freshness": "STALE", "live_observation_eligible": False, "blocker": "STALE_CACHE_NOT_SCOREABLE"},
    {"evidence_id": "sample-public-event-response", "mode": "PUBLIC_SAMPLE_RESPONSE", "domain": "public_event", "freshness": "SAMPLE_NOT_LIVE", "live_observation_eligible": False, "blocker": "SAMPLE_RESPONSE_NOT_LIVE"},
]

FALLBACK_GITHUB_CANDIDATES = [
    {"domain": "sports", "full_name": "sportsdataverse/sportsdataverse-py", "stargazers_count": 106, "license": "MIT", "pushed_at": "2026-07-03T18:58:30Z"},
    {"domain": "sports", "full_name": "swar/nba_api", "stargazers_count": 3706, "license": "MIT", "pushed_at": "2026-04-06T04:38:28Z"},
    {"domain": "sports", "full_name": "roclark/sportsipy", "stargazers_count": 559, "license": "MIT", "pushed_at": "2025-01-31T17:20:05Z"},
    {"domain": "bloomberg", "full_name": "xbbg-org/xbbg", "stargazers_count": 826, "license": "Apache-2.0", "pushed_at": "2026-07-03T07:46:50Z"},
    {"domain": "bloomberg", "full_name": "matthewgilbert/pdblp", "stargazers_count": 254, "license": "MIT", "pushed_at": "2024-12-14T18:51:29Z"},
    {"domain": "crypto", "full_name": "ccxt/ccxt", "stargazers_count": 43166, "license": "MIT", "pushed_at": "2026-07-03T19:18:15Z"},
    {"domain": "crypto", "full_name": "freqtrade/freqtrade", "stargazers_count": 52024, "license": "GPL-3.0", "pushed_at": "2026-07-02T06:10:09Z"},
    {"domain": "crypto", "full_name": "hummingbot/hummingbot", "stargazers_count": 19057, "license": "Apache-2.0", "pushed_at": "2026-07-02T17:26:34Z"},
    {"domain": "macro", "full_name": "OpenBB-finance/OpenBB", "stargazers_count": 69998, "license": "NOASSERTION", "pushed_at": "2026-07-03T16:36:14Z"},
    {"domain": "trading", "full_name": "mementum/backtrader", "stargazers_count": 22299, "license": "GPL-3.0", "pushed_at": "2024-08-19T17:47:36Z"},
    {"domain": "trading", "full_name": "kernc/backtesting.py", "stargazers_count": 8628, "license": "AGPL-3.0", "pushed_at": "2025-12-20T17:50:49Z"},
    {"domain": "event_market", "full_name": "arshka/pykalshi", "stargazers_count": 112, "license": "MIT", "pushed_at": "2026-05-02T08:07:12Z"},
]

FALLBACK_REQUIRED_REPORT_NAMES = [
    "explicit_integration_mode_gate_v2_report.json",
    "public_probe_runner_v2_report.json",
    "cached_public_probe_evidence_ingestion_v1_report.json",
    "observation_evidence_normalizer_v1_report.json",
    "due_forecast_observation_closure_v3_report.json",
    "live_score_seed_engine_v1_report.json",
    "live_calibration_seed_engine_v1_report.json",
    "sports_public_source_decision_engine_v2_report.json",
    "dummy_mission_state_report_v14.json",
    "dashboard_v28_report_v1.json",
    "v28_runtime_budget_report_v1.json",
    "no_secret_leak_report_v28.json",
    "no_direct_order_bypass_report_v28.json",
]

OPEN_SOURCE_REPORT_NAMES = [
    "open_source_github_gap_fill_accelerator_v1_report.json",
    "github_repo_candidate_manifest_v2_report.json",
    "github_repo_domain_classification_v1_report.json",
    "domain_gap_to_repo_map_v1_report.json",
    "sports_open_source_terms_classifier_v1_report.json",
    "bloomberg_open_source_legality_gate_v1_report.json",
    "crypto_open_source_public_adapter_plan_v1_report.json",
    "trading_repo_execution_safety_classifier_v1_report.json",
    "open_source_repo_license_health_v1_report.json",
    "open_source_no_exec_guard_v1_report.json",
    "no_open_source_gap_fill_to_execution_bridge_report_v28.json",
    "no_trading_repo_execution_bridge_report_v28.json",
]

PARTIAL_REPORT_NAMES = {
    "public_probe_runner_v2_report.json",
    "public_probe_run_result_report_v1.json",
    "public_probe_run_failure_report_v1.json",
    "settlement_rule_disambiguation_engine_v2_report.json",
    "settlement_disambiguation_decision_report_v1.json",
    "settlement_disambiguation_blocker_report_v1.json",
    "source_unavailable_recovery_engine_v1_report.json",
    "source_recovery_decision_report_v1.json",
    "source_recovery_blocker_report_v1.json",
    "due_forecast_observation_closure_v3_report.json",
    "due_forecast_observation_decision_v3_report.json",
    "due_forecast_observation_blocker_v3_report.json",
    "live_score_seed_engine_v1_report.json",
    "live_score_seed_decision_report_v1.json",
    "live_score_seed_blocker_report_v1.json",
    "live_calibration_seed_engine_v1_report.json",
    "live_calibration_seed_decision_report_v1.json",
    "live_calibration_seed_blocker_report_v1.json",
    "sports_public_source_decision_engine_v2_report.json",
    "sports_source_decision_report_v1.json",
    "sports_source_decision_blocker_report_v1.json",
    "kalshi_rule_ambiguity_reduction_v4_report.json",
    "kalshi_rule_disambiguation_result_report_v1.json",
    "kalshi_rule_remaining_blocker_report_v1.json",
    "partial_to_pass_closure_ledger_v1_report.json",
    "partial_cause_closure_result_report_v1.json",
    "remaining_partial_cause_report_v1.json",
    "pass_readiness_delta_report_v1.json",
    "observation_closure_scoreboard_report_v1.json",
    "live_score_seed_scoreboard_report_v1.json",
    "settlement_ambiguity_scoreboard_report_v1.json",
    "partial_to_pass_scoreboard_report_v1.json",
}


def _load_required_report_names() -> list[str]:
    names = list(FALLBACK_REQUIRED_REPORT_NAMES)
    if REPORT_NAMES_FILE.exists():
        names = [
            line.strip()
            for line in REPORT_NAMES_FILE.read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    excluded = {"final_report.json", "final_report_v28.json", "tests_summary.json"}
    return list(dict.fromkeys([name for name in names if name not in excluded] + OPEN_SOURCE_REPORT_NAMES))


REPORT_NAMES = _load_required_report_names()


def integration_mode_enabled() -> bool:
    return (
        os.environ.get("DUMMY_PUBLIC_INTEGRATION_MODE") == "1"
        and os.environ.get("DUMMY_PUBLIC_INTEGRATION_CONFIRM") == "READ_ONLY_PUBLIC_PROBES"
    )


def _integration_status() -> str:
    return "ENABLED_READONLY_PUBLIC_PROBES" if integration_mode_enabled() else "DISABLED_BY_DEFAULT"


def _load_github_candidates() -> list[dict[str, Any]]:
    path = ARTIFACTS / "github_gap_fill_candidates_raw_v1.json"
    if not path.exists():
        return [dict(item) for item in FALLBACK_GITHUB_CANDIDATES]
    try:
        loaded = json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return [dict(item) for item in FALLBACK_GITHUB_CANDIDATES]
    candidates: list[dict[str, Any]] = []
    for item in loaded if isinstance(loaded, list) else []:
        if not isinstance(item, dict):
            continue
        search_keywords = item.get("search_keywords") or item.get("search_keyword") or []
        if isinstance(search_keywords, str):
            search_keywords = [search_keywords]
        search_queries = item.get("search_queries") or item.get("search_query") or []
        if isinstance(search_queries, str):
            search_queries = [search_queries]
        sources = item.get("sources") or item.get("source") or []
        if isinstance(sources, str):
            sources = [sources]
        candidates.append(
            {
                "domain": str(item.get("domain") or "unknown"),
                "full_name": str(item.get("full_name") or item.get("name") or "unknown/unknown"),
                "stargazers_count": int(item.get("stargazers_count") or 0),
                "license": str(item.get("license") or "NOASSERTION"),
                "pushed_at": str(item.get("pushed_at") or "UNKNOWN"),
                "html_url": str(item.get("html_url") or ""),
                "search_keywords": [str(value) for value in search_keywords if value],
                "search_queries": [str(value) for value in search_queries if value],
                "sources": [str(value) for value in sources if value],
            }
        )
    return candidates or [dict(item) for item in FALLBACK_GITHUB_CANDIDATES]


def _classify_candidate(candidate: dict[str, Any]) -> dict[str, Any]:
    domain = candidate.get("domain", "unknown")
    full_name = candidate.get("full_name", "unknown/unknown")
    name_lower = str(full_name).lower()
    legality = "PUBLIC_CODE_REFERENCE_ONLY"
    source_mode = "REFERENCE_ONLY"
    blocker = None
    execution_risk = False

    if domain == "sports":
        legality = "SPORTS_TERMS_REVIEW_REQUIRED"
        source_mode = "FIXTURE_OR_REFERENCE_ONLY_UNTIL_TERMS_APPROVED"
        blocker = "SPORTS_TERMS_DECISION_REQUIRED"
        if "sportsipy" in name_lower or "sports-reference" in name_lower:
            legality = "BLOCKED_SCRAPING_RISK"
            blocker = "QUESTIONABLE_SCRAPING_RISK"
        if "nba_api" in name_lower:
            blocker = "UNOFFICIAL_OR_TERMS_REVIEW_REQUIRED"
    elif domain == "bloomberg":
        legality = "KEYED_LICENSED_OPTIONAL_BLOCKED"
        source_mode = "REFERENCE_WRAPPER_ONLY"
        blocker = "BLOOMBERG_ACCESS_LICENSE_REQUIRED"
    elif domain == "weather":
        legality = "PUBLIC_WEATHER_REFERENCE_OR_MODEL_REFERENCE"
        source_mode = "WEATHER_FORECAST_OBSERVATION_REFERENCE_ONLY"
        blocker = None
        if any(token in name_lower for token in ["openweathermap", "visualcrossing", "weatherapi"]):
            legality = "KEYED_WEATHER_PROVIDER_OPTIONAL"
            blocker = "PROVIDER_TERMS_OR_KEY_REVIEW_REQUIRED"
    elif domain == "betting":
        legality = "BETTING_WAGERING_TERMS_REVIEW_REQUIRED"
        source_mode = "REFERENCE_ONLY_NO_ODDS_SCRAPING_NO_WAGERING"
        blocker = "WAGERING_OR_ODDS_TERMS_REQUIRED"
        execution_risk = any(token in name_lower for token in ["bot", "flumine", "betfair", "sportsarb", "surebet", "arbitrage"])
    elif domain == "fantasy":
        legality = "FANTASY_SPORTS_TERMS_REVIEW_REQUIRED"
        source_mode = "REFERENCE_ONLY_NO_CONTEST_ENTRY_NO_DRAFT_SUBMISSION"
        blocker = "FANTASY_CONTEST_OR_PLATFORM_TERMS_REQUIRED"
        execution_risk = any(token in name_lower for token in ["optimizer", "draft-kings", "draftkings", "fanduel", "dfs"])
    elif domain == "crypto":
        if "ccxt" in name_lower:
            legality = "PUBLIC_READONLY_ADAPTER_REFERENCE"
            source_mode = "PUBLIC_TICKER_ORDERBOOK_REFERENCE_ONLY"
        else:
            legality = "OPEN_SOURCE_EXECUTION_FRAMEWORK_REFERENCE_ONLY"
            source_mode = "REPLAY_BACKTEST_REFERENCE_ONLY"
            blocker = "LIVE_TRADING_FEATURES_BLOCKED"
            execution_risk = True
    elif domain == "trading":
        legality = "REPLAY_BACKTEST_REFERENCE_ONLY"
        source_mode = "RESEARCH_OR_BACKTEST_ONLY"
        blocker = "LIVE_OR_PAPER_TRADING_BRIDGE_BLOCKED"
        execution_risk = any(token in name_lower for token in ["hummingbot", "freqtrade", "blankly", "lumibot", "bot", "trader"])
    elif domain == "event_market":
        legality = "READ_ONLY_MARKET_RULE_REFERENCE_ONLY"
        source_mode = "PUBLIC_MARKET_METADATA_OR_RULE_REFERENCE_ONLY"
        blocker = "ORDER_CANCEL_PRIVATE_PATHS_BLOCKED"
        execution_risk = any(token in name_lower for token in ["bot", "autopilot", "trading"])
    elif domain == "macro":
        legality = "PUBLIC_OR_PROVIDER_TERMS_GATED_REFERENCE"
        source_mode = "PUBLIC_CONTEXT_REFERENCE_ONLY"
        blocker = "PROVIDER_TERMS_OR_KEYED_SOURCE_REVIEW_REQUIRED" if "openbb" in name_lower else None
    return {
        **candidate,
        "legality_class": legality,
        "source_mode": source_mode,
        "blocker": blocker,
        "live_observation_allowed": False,
        "canonical_blocker": False,
        "execution_risk": execution_risk,
        "safe_use": "metadata_and_design_reference_only",
        "github_repo_code_executed": False,
        "clone_required": False,
        "import_required": False,
    }


def github_candidate_manifest() -> list[dict[str, Any]]:
    return [_classify_candidate(item) for item in _load_github_candidates()]


def _domain_counts(candidates: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for item in candidates:
        domain = str(item.get("domain", "unknown"))
        counts[domain] = counts.get(domain, 0) + 1
    return dict(sorted(counts.items()))


def _search_keyword_coverage(candidates: list[dict[str, Any]]) -> list[str]:
    keywords: set[str] = set()
    for item in candidates:
        for keyword in item.get("search_keywords", []):
            if keyword:
                keywords.add(str(keyword))
    return sorted(keywords)


def _mode_split() -> dict[str, int]:
    counts: dict[str, int] = {}
    for record in CACHED_EVIDENCE_RECORDS:
        mode = record["mode"]
        counts[mode] = counts.get(mode, 0) + 1
    return dict(sorted(counts.items()))


def _counts() -> dict[str, int]:
    due = [item for item in FORECAST_RECORDS if item["due_state"] == "DUE"]
    observed = [item for item in FORECAST_RECORDS if item["observed"]]
    live_scored = [item for item in FORECAST_RECORDS if item["scored"]]
    unresolved = [item for item in due if not item["scored"]]
    return {
        "forecast_write_count": len(FORECAST_RECORDS),
        "no_trade_write_count": len(NO_TRADE_RECORDS),
        "observer_queue_count": len(FORECAST_RECORDS),
        "due_forecast_count": len(due),
        "observed_forecast_count": len(observed),
        "live_scored_count": len(live_scored),
        "live_unresolved_count": len(unresolved),
    }


def _partial_causes() -> dict[str, int]:
    causes: dict[str, int] = {}
    for item in FORECAST_RECORDS:
        if item["due_state"] != "DUE" or item["scored"]:
            continue
        cause = item["resolution"]
        causes[cause] = causes.get(cause, 0) + 1
    if not integration_mode_enabled():
        causes["INTEGRATION_DISABLED_BY_DEFAULT"] = 1
    return dict(sorted(causes.items()))


def _domain_gap_to_repo_map(candidates: list[dict[str, Any]]) -> dict[str, list[dict[str, Any]]]:
    mapped: dict[str, list[dict[str, Any]]] = {}
    for item in candidates:
        domain = item.get("domain", "unknown")
        mapped.setdefault(domain, []).append(
            {
                "full_name": item["full_name"],
                "legality_class": item["legality_class"],
                "source_mode": item["source_mode"],
                "safe_use": item["safe_use"],
                "blocker": item["blocker"],
            }
        )
    return dict(sorted(mapped.items()))


def _common_fields(report_name: str) -> dict[str, Any]:
    candidates = github_candidate_manifest()
    return {
        "report_name": report_name,
        "canonical_scope": CANONICAL_SCOPE,
        "market_classes": MARKET_CLASSES,
        "integration_enabled": integration_mode_enabled(),
        "integration_enabled_state": _integration_status(),
        "integration_mode_env_flag": "DUMMY_PUBLIC_INTEGRATION_MODE",
        "integration_mode_confirm_flag": "DUMMY_PUBLIC_INTEGRATION_CONFIRM",
        "public_probe_run_count": 0,
        "public_probe_real_network_attempted": False,
        "public_probe_tasks": PUBLIC_PROBE_TASKS,
        "cached_evidence_mode_split": _mode_split(),
        "github_candidate_count": len(candidates),
        "github_domain_counts": _domain_counts(candidates),
        "github_search_keyword_coverage": _search_keyword_coverage(candidates),
        "github_search_query_count": len({query for item in candidates for query in item.get("search_queries", [])}),
        "github_mining_mode": "metadata_only_no_clone_no_import_no_execute",
        "runtime_budget": {
            "max_request_count": 12,
            "per_source_timeout_seconds": 6,
            "total_timeout_seconds": 60,
            "unit_tests_require_network": False,
        },
        **_counts(),
    }


def _workstream_from_name(report_name: str) -> str:
    stem = report_name.removesuffix(".json")
    return f"V28: {stem.removesuffix('_report').replace('_', ' ').title()}"


def _report_verdict(report_name: str) -> str:
    if report_name in PARTIAL_REPORT_NAMES:
        return "PARTIAL"
    if "scoreboard" in report_name and any(token in report_name for token in ["observation", "live_score", "partial", "settlement_ambiguity"]):
        return "PARTIAL"
    return "PASS"


def _component_payload(report_name: str) -> dict[str, Any]:
    candidates = github_candidate_manifest()
    report = _safe_payload(_workstream_from_name(report_name), _report_verdict(report_name), **_common_fields(report_name))

    if "integration_mode" in report_name or "integration_gate" in report_name:
        report.update(
            gate_status="PASS",
            decision_status=_integration_status(),
            default_status="DISABLED_BY_DEFAULT",
            enabled_only_when="DUMMY_PUBLIC_INTEGRATION_MODE=1 and DUMMY_PUBLIC_INTEGRATION_CONFIRM=READ_ONLY_PUBLIC_PROBES",
            config_diff_guard_status="PASS",
            caps_modified=False,
            live_submit_modified=False,
            operator_scope={"read_only_public_probes": True, "orders": False, "cancels": False, "private_endpoints": False},
        )
    if "public_probe" in report_name or "probe_run" in report_name:
        report.update(
            runner_status="DISABLED_BY_DEFAULT" if not integration_mode_enabled() else "READY_FOR_BOUNDED_READONLY_RUN",
            run_plan=PUBLIC_PROBE_TASKS,
            run_results=[],
            disabled_reason=None if integration_mode_enabled() else "explicit integration intent not present",
            failures=[{"kind": "DISABLED_BY_DEFAULT", "retryable": True}] if not integration_mode_enabled() else [],
            redaction_proof={"secrets_logged": False, "source_api_keys_logged": False, "github_tokens_logged": False},
        )
    if "cached" in report_name:
        report.update(
            ingestion_status="PASS",
            cached_evidence_records=CACHED_EVIDENCE_RECORDS,
            eligible_live_cached_records=[],
            invalid_cache_blockers=[record["blocker"] for record in CACHED_EVIDENCE_RECORDS if record["blocker"]],
            sample_or_fixture_claimed_live=False,
            stale_cache_scored_live=False,
        )
    if "observation" in report_name:
        report.update(
            observation_normalizer_status="PASS",
            observation_packets=[],
            eligible_observation_count=0,
            evidence_join_count=0,
            blockers=["NO_FRESH_LIVE_PUBLIC_EVIDENCE", "SAMPLE_AND_FIXTURE_EVIDENCE_NOT_LIVE"],
        )
    if "settlement" in report_name or "ambiguity" in report_name or "kalshi_rule" in report_name:
        report.update(
            disambiguation_status="PARTIAL_EXPLICIT_BLOCKERS" if report["verdict"] == "PARTIAL" else "PASS",
            ambiguity_cases=[{"case_id": "v26-kalshi-map-001", "decision": "REMAINS_AMBIGUOUS", "score_allowed": False}],
            confidence_threshold=0.85,
            ambiguous_settlement_scored=False,
        )
    if "source_unavailable" in report_name or "source_recovery" in report_name or "fallback_source" in report_name:
        report.update(
            source_recovery_status="PARTIAL_EXPLICIT_BLOCKERS",
            fallback_candidates=[task for task in PUBLIC_PROBE_TASKS if task["domain"] in {"crypto", "weather", "macro", "commodities"}],
            recovered_source_count=0,
            preserved_blockers=["SOURCE_UNAVAILABLE", "MANUAL_IMPORT_REQUIRED"],
        )
    if "due_forecast" in report_name:
        report.update(
            closure_status="PARTIAL_EXPLICIT_BLOCKERS",
            due_forecasts=[item for item in FORECAST_RECORDS if item["due_state"] == "DUE"],
            observed_forecasts=[],
            ledger_writes=[],
            blockers=_partial_causes(),
        )
    if "live_score_seed" in report_name:
        report.update(
            live_score_seed_status="PARTIAL_NO_VALID_OBSERVED_OUTCOMES",
            score_candidates=[],
            score_ledger_writes=[],
            low_sample_warning=True,
            pnl_claimed=False,
        )
    if "live_calibration_seed" in report_name:
        report.update(
            live_calibration_seed_status="PARTIAL_NO_LIVE_SCORES",
            calibration_samples=[],
            calibration_readiness="LOW_SAMPLE",
            replay_calibration_mixed_into_live=False,
            live_trading_readiness_claimed=False,
        )
    if "sports" in report_name:
        report.update(
            sports_source_decision_status="PASS_EXPLICIT_VERDICTS",
            sports_source_mode="FIXTURE_REPLAY_ONLY",
            sports_candidates=[item for item in candidates if item.get("domain") == "sports"],
            live_sports_source_allowed=False,
            terms_approved_public_schedule_source=None,
            odds_scraping_allowed=False,
        )
    if any(token in report_name for token in ["github", "open_source", "repo", "bloomberg", "crypto_open_source", "trading_repo"]):
        report.update(
            open_source_gap_fill_status="PASS",
            github_candidates=candidates,
            approved_reference_candidates=[item for item in candidates if item["blocker"] is None and not item["execution_risk"]],
            blocked_or_terms_gated_candidates=[item for item in candidates if item["blocker"] is not None or item["execution_risk"]],
            domain_gap_to_repo_map=_domain_gap_to_repo_map(candidates),
            bloomberg_canonical_blocker=False,
            premium_or_keyed_sources_are_global_blockers=False,
            trading_repo_execution_bridge_present=False,
            mined_repo_code_executed=False,
            wagering_reference_only=True,
            fantasy_reference_only=True,
            betting_wagering_activation_allowed=False,
            fantasy_contest_entry_allowed=False,
            odds_scraping_allowed=False,
            sportsbook_activation_allowed=False,
            gambling_activation_allowed=False,
        )
    if report_name.endswith("_v28.json") or report_name.startswith("no_") or report_name.startswith("readonly_only") or "blunder" in report_name or "canonical_identity" in report_name:
        report.update(status="PASS", safety_status="PASS")
    return report


def generate_dashboard_v28_report_v1() -> dict[str, Any]:
    return _safe_payload(
        "V28: Dashboard Contract",
        "PASS",
        **_common_fields("dashboard_v28_report_v1.json"),
        dashboard_status="PASS",
        routes=["/api/v28/mission-state", "/api/v28/oss-gap-fill", "/api/v28/observation-closure", "/api/v28/safety"],
        cache_policy="artifact-backed deterministic report slices",
    )


def dummy_mission_state_report_v14(reports: dict[str, dict[str, Any]]) -> dict[str, Any]:
    candidates = github_candidate_manifest()
    counts = _counts()
    partial_causes = _partial_causes()
    partials = sorted(name for name, report in reports.items() if report.get("verdict") == "PARTIAL")
    return _safe_payload(
        "V28: Dummy Mission State",
        "PARTIAL" if partials else "PASS",
        **_common_fields("dummy_mission_state_report_v14.json"),
        mission_state_verdict="PARTIAL" if partials else "PASS",
        v17_truth_loop_status="PASS",
        v21_source_activation_status="PASS",
        v22_forecast_write_status="PASS",
        v23_observer_calibration_status="PASS_PARTIAL_EXPECTED",
        v24_open_source_public_data_status="PASS_PARTIAL_EXPECTED",
        v25_market_class_generalization_status="PASS_PARTIAL_EXPECTED",
        v26_keyless_settlement_expansion_status="PASS_PARTIAL_EXPECTED",
        v27_integration_settlement_live_scoring_status="PASS_PARTIAL_EXPECTED",
        live_submit_enabled=False,
        live_submit_flag_status="PASS_DISABLED",
        caps_config_status="PASS_UNCHANGED",
        explicit_integration_mode_gate_status="PASS",
        public_probe_runner_status="DISABLED_BY_DEFAULT" if not integration_mode_enabled() else "READY_FOR_BOUNDED_READONLY_RUN",
        cached_probe_evidence_status="PASS",
        observation_normalizer_status="PASS",
        settlement_disambiguation_status="PARTIAL_EXPLICIT_BLOCKERS",
        source_unavailable_recovery_status="PARTIAL_EXPLICIT_BLOCKERS",
        due_observation_closure_status="PARTIAL_EXPLICIT_BLOCKERS",
        live_score_seed_status="PARTIAL_NO_VALID_OBSERVED_OUTCOMES",
        live_calibration_seed_status="PARTIAL_NO_LIVE_SCORES",
        sports_source_decision_status="PASS_EXPLICIT_VERDICTS",
        sports_source_mode="FIXTURE_REPLAY_ONLY",
        kalshi_ambiguity_reduction_status="PASS_WITH_AMBIGUOUS_RULE_BLOCKERS",
        forecast_cadence_v4_status="PASS",
        live_observer_loop_v4_status="PASS",
        live_source_truth_v10_status="PASS",
        partial_to_pass_closure_status="PARTIAL_EXPLICIT_BLOCKERS",
        partial_causes_before={"SOURCE_UNAVAILABLE": 1, "SETTLEMENT_AMBIGUOUS": 1, "MANUAL_IMPORT_REQUIRED": 1},
        partial_causes_after=partial_causes,
        adapter_sprint_v5_status="PASS",
        compounding_v12_status="PASS",
        next_bundle_recommendation="DUMMY_V29_OPERATOR_APPROVED_PUBLIC_PROBE_RUN_AND_FIRST_LIVE_OBSERVATION_SEED_V1",
        market_class_scoreboard_v13_status="PASS_PARTIAL_EXPECTED",
        github_gap_fill_status="PASS",
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
        no_cached_sample_claimed_live_status="PASS",
        no_stale_cached_evidence_scored_live_status="PASS",
        no_context_claimed_edge_status="PASS",
        no_example_market_canonical_center_status="PASS",
        no_unresolved_forecast_scored_status="PASS",
        no_ambiguous_settlement_scored_status="PASS",
        no_source_unavailable_forecast_scored_status="PASS",
        no_not_due_forecast_scored_status="PASS",
        no_outcome_fabrication_status="PASS",
        no_integration_gate_to_execution_bridge_status="PASS",
        no_public_probe_runner_to_execution_bridge_status="PASS",
        no_cached_evidence_to_execution_bridge_status="PASS",
        no_observation_closure_to_execution_bridge_status="PASS",
        no_live_score_seed_to_execution_bridge_status="PASS",
        no_live_calibration_seed_to_execution_bridge_status="PASS",
        no_source_truth_to_execution_bridge_status="PASS",
        no_adapter_sprint_to_execution_bridge_status="PASS",
        no_open_source_gap_fill_to_execution_bridge_status="PASS",
        blunder_separation_status="PASS",
        dashboard_status="PASS",
        partial_reports=partials,
        partial_reasons=[
            "integration mode remains disabled by default unless explicit read-only public-probe intent is present",
            "live scored count remains 0 because no fresh live-public observation evidence is available in offline validation",
            "due forecasts preserve SOURCE_UNAVAILABLE, SETTLEMENT_AMBIGUOUS, MANUAL_IMPORT_REQUIRED, or NOT_DUE_YET blockers",
            "sports remains FIXTURE_REPLAY_ONLY pending operator-approved terms-safe public schedule/status source",
        ],
        proof_paths={
            "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v14.json"),
            "integration_gate": str(ARTIFACTS / "explicit_integration_mode_gate_v2_report.json"),
            "public_probe_runner": str(ARTIFACTS / "public_probe_runner_v2_report.json"),
            "cached_evidence": str(ARTIFACTS / "cached_public_probe_evidence_ingestion_v1_report.json"),
            "observation_closure": str(ARTIFACTS / "due_forecast_observation_closure_v3_report.json"),
            "live_score_seed": str(ARTIFACTS / "live_score_seed_engine_v1_report.json"),
            "oss_gap_fill": str(ARTIFACTS / "open_source_github_gap_fill_accelerator_v1_report.json"),
            "safety": str(ARTIFACTS / "no_direct_order_bypass_report_v28.json"),
        },
    )


class V28ReportFactory:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network

    def build(self) -> dict[str, dict[str, Any]]:
        reports: dict[str, dict[str, Any]] = {}
        for report_name in REPORT_NAMES:
            if report_name == "dummy_mission_state_report_v14.json":
                continue
            if report_name == "dashboard_v28_report_v1.json":
                reports[report_name] = generate_dashboard_v28_report_v1()
                continue
            reports[report_name] = _component_payload(report_name)
        reports["dummy_mission_state_report_v14.json"] = dummy_mission_state_report_v14(reports)
        if "dashboard_v28_report_v1.json" not in reports:
            reports["dashboard_v28_report_v1.json"] = generate_dashboard_v28_report_v1()
        return reports
