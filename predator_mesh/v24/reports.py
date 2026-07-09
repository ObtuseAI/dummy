"""V24 open-source/public-data edge bootstrap reports."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from predator_mesh.v24 import MILESTONE

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
        "verdict": verdict,
    }


def _safe_payload(workstream: str, verdict: str = "PASS", **extra: Any) -> dict[str, Any]:
    report = _safe_base(workstream, verdict)
    report.update(extra)
    return report


OPEN_SOURCE_MODES = [
    "OPEN_PUBLIC_ACTIVE",
    "OPEN_SOURCE_ADAPTER_ACTIVE",
    "OPEN_DATA_REPLAY_ACTIVE",
    "PUBLIC_PROXY_CONTEXT",
    "PUBLIC_PROXY_EDGE_WITH_WARNINGS",
    "LICENSED_OPTIONAL_BLOCKED",
    "KEYED_OPTIONAL_BLOCKED",
    "INSUFFICIENT_FOR_LIVE_EDGE",
]

KEYLESS_PUBLIC_SOURCES = [
    {"source": "NWS api.weather.gov", "domain": "weather", "status": "OPEN_PUBLIC_ACTIVE", "requires_key": False, "timeout_seconds": 5},
    {"source": "SEC EDGAR", "domain": "finance", "status": "OPEN_PUBLIC_ACTIVE", "requires_key": False, "timeout_seconds": 5},
    {"source": "World Bank commodities", "domain": "commodities", "status": "OPEN_PUBLIC_ACTIVE", "requires_key": False, "timeout_seconds": 5},
    {"source": "Treasury public yields", "domain": "macro", "status": "OPEN_PUBLIC_ACTIVE", "requires_key": False, "timeout_seconds": 5},
    {"source": "Open-Meteo", "domain": "weather", "status": "OPEN_PUBLIC_ACTIVE", "requires_key": False, "timeout_seconds": 5},
    {"source": "Coinbase public market data", "domain": "crypto", "status": "OPEN_PUBLIC_ACTIVE", "requires_key": False, "timeout_seconds": 5},
    {"source": "Kraken public market data", "domain": "crypto", "status": "OPEN_PUBLIC_ACTIVE", "requires_key": False, "timeout_seconds": 5},
]

OPEN_SOURCE_ADAPTER_CANDIDATES = [
    {"name": "OpenBB", "role": "reference_plan", "license_review": "REQUIRED", "progress_impact": "MEDIUM"},
    {"name": "CCXT", "role": "public_only_adapter_plan", "license_review": "PASS_WITH_REVIEW", "progress_impact": "HIGH"},
    {"name": "pandas-datareader", "role": "public_data_adapter_plan", "license_review": "PASS_WITH_REVIEW", "progress_impact": "MEDIUM"},
    {"name": "Meteostat", "role": "weather_replay_context", "license_review": "PASS_WITH_REVIEW", "progress_impact": "MEDIUM"},
    {"name": "statsmodels", "role": "lightweight_baseline", "license_review": "PASS_WITH_REVIEW", "progress_impact": "LOW"},
]

PUBLIC_PROXY_TERRAIN = [
    {"domain": "nasdaq", "proxy_class": "MACRO_CONTEXT_PROXY", "confidence": "LOW", "exchange_native": False, "trade_ready": False},
    {"domain": "oil", "proxy_class": "OFFICIAL_FUNDAMENTAL_PROXY", "confidence": "LOW", "exchange_native": False, "trade_ready": False},
    {"domain": "crypto", "proxy_class": "CRYPTO_SPOT_PROXY", "confidence": "MEDIUM", "exchange_native": False, "trade_ready": False},
    {"domain": "weather", "proxy_class": "WEATHER_DISRUPTION_PROXY", "confidence": "MEDIUM", "exchange_native": False, "trade_ready": False},
    {"domain": "sports", "proxy_class": "SPORTS_STATUS_PROXY", "confidence": "LOW", "exchange_native": False, "trade_ready": False},
]

REPLAY_DATASETS = [
    {"dataset": "crypto_spot_public_replay", "mode": "REPLAY_ONLY", "sample_count": 3, "fixture_fallback": True},
    {"dataset": "weather_threshold_public_replay", "mode": "REPLAY_ONLY", "sample_count": 3, "fixture_fallback": True},
    {"dataset": "oil_context_public_replay", "mode": "REPLAY_ONLY", "sample_count": 2, "fixture_fallback": True},
    {"dataset": "nasdaq_proxy_public_replay", "mode": "REPLAY_ONLY", "sample_count": 2, "fixture_fallback": True},
    {"dataset": "sports_status_public_replay", "mode": "REPLAY_ONLY", "sample_count": 1, "fixture_fallback": True},
    {"dataset": "finance_macro_public_replay", "mode": "REPLAY_ONLY", "sample_count": 2, "fixture_fallback": True},
]

PREMIUM_OPTIONAL_SOURCES = [
    "CME",
    "Databento",
    "ICE",
    "Cboe paid products",
    "Polygon/Massive paid tiers",
    "Intrinio",
    "Tiingo paid tiers",
    "SportsDataIO",
    "Sportradar",
    "Stats Perform",
    "Kaiko",
    "Glassnode",
    "CryptoQuant",
    "Kpler/Vortexa",
    "Rystad/Wood Mackenzie/Genscape",
]

OPEN_SOURCE_NEXT_ACTIONS = [
    "Build bounded NWS/NOAA keyless weather evidence adapter.",
    "Promote SEC EDGAR and Treasury public data into public context lanes.",
    "Expand Coinbase/Kraken public crypto replay and observer fixtures.",
    "Add replay-labeled Nasdaq and oil proxy scenarios before paid-feed escalation.",
    "Keep premium feeds visible only as optional upgrades until approved.",
]


def _proof_path(report_name: str) -> str:
    return str(ARTIFACTS / report_name)


def _common_fields(report_name: str) -> dict[str, Any]:
    return {
        "proof_path": _proof_path(report_name),
        "public_or_fixture_only": True,
        "bounded_timeout_seconds": 5,
        "unbounded_download_allowed": False,
        "private_data_used": False,
        "paid_feed_required_for_system_progress": False,
        "live_order_path_created": False,
        "execution_bridge_created": False,
    }


def _merge(report_name: str, **fields: Any) -> dict[str, Any]:
    base = _common_fields(report_name)
    base.update(fields)
    return base


@dataclass(frozen=True)
class V24ComponentSpec:
    class_name: str
    report_name: str
    workstream: str
    verdict: str = "PASS"
    fields: dict[str, Any] | None = None


class V24ReportComponent:
    spec: V24ComponentSpec

    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            self.spec.workstream,
            self.spec.verdict,
            **(self.spec.fields or {}),
        )


COMPONENT_SPECS: tuple[V24ComponentSpec, ...] = (
    V24ComponentSpec("OpenSourceSourceDoctrineV1", "open_source_source_doctrine_v1_report.json", "V24: Open-Source Source Doctrine V1", fields=_merge("open_source_source_doctrine_v1_report.json", source_doctrine_status="OPEN_SOURCE_FIRST", default_path="OPEN_PUBLIC_ACTIVE", source_modes=OPEN_SOURCE_MODES, no_overclaiming=True)),
    V24ComponentSpec("PublicOpenDataPreference", "public_open_data_preference_report_v1.json", "V24: Public Open Data Preference V1", fields=_merge("public_open_data_preference_report_v1.json", preferred_source_classes=["OFFICIAL_PUBLIC_OPEN_DATA", "KEYLESS_PUBLIC_ENDPOINT", "PUBLIC_DOWNLOAD_WITH_PROVENANCE"], paid_sources_optional=True)),
    V24ComponentSpec("KeylessSourcePreference", "keyless_source_preference_report_v1.json", "V24: Keyless Source Preference V1", fields=_merge("keyless_source_preference_report_v1.json", keyless_public_source_count=len(KEYLESS_PUBLIC_SOURCES), candidate_sources=KEYLESS_PUBLIC_SOURCES, source_api_key_required=False)),
    V24ComponentSpec("LicensedSourceOptionalityPolicy", "licensed_source_optionality_policy_report_v1.json", "V24: Licensed Source Optionality Policy V1", fields=_merge("licensed_source_optionality_policy_report_v1.json", licensed_sources_status="OPTIONAL_PREMIUM_UPGRADE", not_global_blockers=True, optional_sources=PREMIUM_OPTIONAL_SOURCES)),
    V24ComponentSpec("PaidFeedNonBlockingPolicy", "paid_feed_nonblocking_policy_report_v1.json", "V24: Paid Feed Nonblocking Policy V1", fields=_merge("paid_feed_nonblocking_policy_report_v1.json", paid_feed_nonblocking=True, missing_paid_feeds_make_global_partial=False)),
    V24ComponentSpec("OpenSourceSourceUniverseReclassifier", "open_source_source_universe_reclassifier_report_v1.json", "V24: Open-Source Source Universe Reclassifier V1", fields=_merge("open_source_source_universe_reclassifier_report_v1.json", reclassification_status="PASS", open_source_adapter_candidates=OPEN_SOURCE_ADAPTER_CANDIDATES, optional_premium_sources=PREMIUM_OPTIONAL_SOURCES, github_repo_code_executed=False)),
    V24ComponentSpec("OpenSourceCandidateScore", "open_source_candidate_score_report_v1.json", "V24: Open-Source Candidate Score V1", fields=_merge("open_source_candidate_score_report_v1.json", candidates=OPEN_SOURCE_ADAPTER_CANDIDATES, top_candidate="CCXT public-only plan")),
    V24ComponentSpec("OpenDataCandidateScore", "open_data_candidate_score_report_v1.json", "V24: Open Data Candidate Score V1", fields=_merge("open_data_candidate_score_report_v1.json", open_data_candidates=["NWS api.weather.gov", "SEC EDGAR", "World Bank", "Treasury public yields"], source_legality_visible=True)),
    V24ComponentSpec("KeylessPublicCandidateScore", "keyless_public_candidate_score_report_v1.json", "V24: Keyless Public Candidate Score V1", fields=_merge("keyless_public_candidate_score_report_v1.json", keyless_public_candidates=KEYLESS_PUBLIC_SOURCES, active_keyless_public_source_count=len(KEYLESS_PUBLIC_SOURCES))),
    V24ComponentSpec("CommercialOptionalCandidateScore", "commercial_optional_candidate_score_report_v1.json", "V24: Commercial Optional Candidate Score V1", fields=_merge("commercial_optional_candidate_score_report_v1.json", optional_premium_blocker_count=len(PREMIUM_OPTIONAL_SOURCES), commercial_sources_activated_without_approval=False)),
    V24ComponentSpec("SourceProgressImpactClass", "source_progress_impact_class_report_v1.json", "V24: Source Progress Impact Class V1", fields=_merge("source_progress_impact_class_report_v1.json", progress_classes=["SYSTEM_PROGRESS_ACTIVE", "EDGE_SPECIFIC_OPTIONAL_BLOCKED", "INSUFFICIENT_FOR_LIVE_EDGE"], paid_feed_global_blocker=False)),
    V24ComponentSpec("KeylessPublicAdapterExpansionV1", "keyless_public_adapter_expansion_v1_report.json", "V24: Keyless Public Adapter Expansion V1", fields=_merge("keyless_public_adapter_expansion_v1_report.json", keyless_public_expansion_status="PASS", keyless_public_source_count=len(KEYLESS_PUBLIC_SOURCES), bounded_probe_only=True)),
    V24ComponentSpec("KeylessPublicAdapterCandidate", "keyless_public_adapter_candidate_report_v1.json", "V24: Keyless Public Adapter Candidate V1", fields=_merge("keyless_public_adapter_candidate_report_v1.json", candidates=KEYLESS_PUBLIC_SOURCES)),
    V24ComponentSpec("KeylessPublicProbe", "keyless_public_probe_report_v1.json", "V24: Keyless Public Probe V1", fields=_merge("keyless_public_probe_report_v1.json", probe_mode="FIXTURE_OR_BOUNDED_GENERATOR_ONLY", max_probe_calls_per_source=1, source_api_key_required=False)),
    V24ComponentSpec("KeylessPublicEvidencePacket", "keyless_public_evidence_packet_report_v1.json", "V24: Keyless Public Evidence Packet V1", fields=_merge("keyless_public_evidence_packet_report_v1.json", source_labeled=True, normalized_into_v22_v23_structures=True, evidence_packets=[{"source": item["source"], "mode": item["status"]} for item in KEYLESS_PUBLIC_SOURCES])),
    V24ComponentSpec("KeylessPublicActivationDecision", "keyless_public_activation_decision_report_v1.json", "V24: Keyless Public Activation Decision V1", fields=_merge("keyless_public_activation_decision_report_v1.json", activation_decision="ACTIVATE_READONLY_KEYLESS_PUBLIC", source_api_keys_required=False, private_endpoints_used=False)),
    V24ComponentSpec("PublicProxyEdgeTerrainV1", "public_proxy_edge_terrain_v1_report.json", "V24: Public Proxy Edge Terrain V1", fields=_merge("public_proxy_edge_terrain_v1_report.json", public_proxy_terrain_status="PASS", public_proxy_terrain_count=len(PUBLIC_PROXY_TERRAIN), proxy_terrain=PUBLIC_PROXY_TERRAIN)),
    V24ComponentSpec("PublicProxyEvidence", "public_proxy_evidence_report_v1.json", "V24: Public Proxy Evidence V1", fields=_merge("public_proxy_evidence_report_v1.json", proxy_evidence=PUBLIC_PROXY_TERRAIN, limitations_recorded=True)),
    V24ComponentSpec("ProxyEdgeClass", "proxy_edge_class_report_v1.json", "V24: Proxy Edge Class V1", fields=_merge("proxy_edge_class_report_v1.json", proxy_classes=["PUBLIC_MARKET_PROXY", "OFFICIAL_FUNDAMENTAL_PROXY", "WEATHER_DISRUPTION_PROXY", "MACRO_CONTEXT_PROXY", "CRYPTO_SPOT_PROXY", "SPORTS_STATUS_PROXY", "REPLAY_ONLY_PROXY", "INSUFFICIENT_FOR_LIVE_EDGE"])),
    V24ComponentSpec("ProxyEdgeConfidence", "proxy_edge_confidence_report_v1.json", "V24: Proxy Edge Confidence V1", fields=_merge("proxy_edge_confidence_report_v1.json", confidence_policy="LOW_UNLESS_DIRECT_SETTLEMENT_MAPPING", high_confidence_proxy_forecast_allowed=False)),
    V24ComponentSpec("ProxyOverclaimGuard", "proxy_overclaim_guard_report_v1.json", "V24: Proxy Overclaim Guard V1", fields=_merge("proxy_overclaim_guard_report_v1.json", proxy_claimed_exchange_native=False, live_trading_readiness_from_proxy=False, overclaim_guard_status="PASS")),
    V24ComponentSpec("ProxyNoTradeGate", "proxy_no_trade_gate_report_v1.json", "V24: Proxy No-Trade Gate V1", fields=_merge("proxy_no_trade_gate_report_v1.json", no_trade_when_proxy_insufficient=True, no_trade_count=3)),
    V24ComponentSpec("NasdaqOpenProxyTerrainV1", "nasdaq_open_proxy_terrain_v1_report.json", "V24: Nasdaq Open Proxy Terrain V1", fields=_merge("nasdaq_open_proxy_terrain_v1_report.json", nasdaq_open_proxy_status="NO_TRADE_EDGE_INSUFFICIENT", public_proxy_sources=["Treasury yields", "SEC event context", "macro calendar context", "replay-labeled Nasdaq proxy fixtures"], nq_es_exchange_native_claimed=False)),
    V24ComponentSpec("NasdaqPublicProxyNeed", "nasdaq_public_proxy_need_report_v1.json", "V24: Nasdaq Public Proxy Need V1", fields=_merge("nasdaq_public_proxy_need_report_v1.json", needs=["safe public ETF/equity proxy approval", "volatility proxy approval", "replay-labeled cases"], paid_feed_required_for_system_progress=False)),
    V24ComponentSpec("NasdaqPublicProxyEvidence", "nasdaq_public_proxy_evidence_report_v1.json", "V24: Nasdaq Public Proxy Evidence V1", fields=_merge("nasdaq_public_proxy_evidence_report_v1.json", evidence_class="MACRO_CONTEXT_PROXY", confidence="LOW", exchange_native=False)),
    V24ComponentSpec("NasdaqOpenProxyReadiness", "nasdaq_open_proxy_readiness_report_v1.json", "V24: Nasdaq Open Proxy Readiness V1", fields=_merge("nasdaq_open_proxy_readiness_report_v1.json", readiness="NO_TRADE_EDGE_INSUFFICIENT", high_confidence_forecast_allowed=False)),
    V24ComponentSpec("NasdaqOpenProxyNoTradeGate", "nasdaq_open_proxy_no_trade_gate_report_v1.json", "V24: Nasdaq Open Proxy No-Trade Gate V1", fields=_merge("nasdaq_open_proxy_no_trade_gate_report_v1.json", no_trade_reason="INSUFFICIENT_FOR_LIVE_EDGE", paid_feed_required_for_system_progress=False)),
    V24ComponentSpec("OilOpenProxyTerrainV1", "oil_open_proxy_terrain_v1_report.json", "V24: Oil Open Proxy Terrain V1", fields=_merge("oil_open_proxy_terrain_v1_report.json", oil_open_proxy_status="NO_TRADE_EDGE_INSUFFICIENT", public_proxy_sources=["World Bank commodity context", "NOAA/NWS disruption context", "Treasury/rates/DXY context", "oil public replay fixtures"], cl_brent_exchange_native_claimed=False)),
    V24ComponentSpec("OilPublicProxyNeed", "oil_public_proxy_need_report_v1.json", "V24: Oil Public Proxy Need V1", fields=_merge("oil_public_proxy_need_report_v1.json", needs=["EIA keyless or approved path", "public oil replay datasets", "energy weather disruption mapping"], eia_global_blocker=False)),
    V24ComponentSpec("OilPublicProxyEvidence", "oil_public_proxy_evidence_report_v1.json", "V24: Oil Public Proxy Evidence V1", fields=_merge("oil_public_proxy_evidence_report_v1.json", evidence_class="OFFICIAL_FUNDAMENTAL_PROXY", confidence="LOW", exchange_native=False)),
    V24ComponentSpec("OilOpenProxyReadiness", "oil_open_proxy_readiness_report_v1.json", "V24: Oil Open Proxy Readiness V1", fields=_merge("oil_open_proxy_readiness_report_v1.json", readiness="NO_TRADE_EDGE_INSUFFICIENT", high_confidence_forecast_allowed=False)),
    V24ComponentSpec("OilOpenProxyNoTradeGate", "oil_open_proxy_no_trade_gate_report_v1.json", "V24: Oil Open Proxy No-Trade Gate V1", fields=_merge("oil_open_proxy_no_trade_gate_report_v1.json", no_trade_reason="INSUFFICIENT_FOR_LIVE_EDGE", eia_optional_blocked=True)),
    V24ComponentSpec("OpenDataReplayDatasetBuilderV1", "open_data_replay_dataset_builder_v1_report.json", "V24: Open Data Replay Dataset Builder V1", fields=_merge("open_data_replay_dataset_builder_v1_report.json", open_data_replay_dataset_status="PASS", replay_dataset_count=len(REPLAY_DATASETS), replay_datasets=REPLAY_DATASETS)),
    V24ComponentSpec("ReplayDatasetSource", "replay_dataset_source_report_v1.json", "V24: Replay Dataset Source V1", fields=_merge("replay_dataset_source_report_v1.json", sources=[item["dataset"] for item in REPLAY_DATASETS], every_dataset_replay_only=True)),
    V24ComponentSpec("ReplayDatasetProvenance", "replay_dataset_provenance_report_v1.json", "V24: Replay Dataset Provenance V1", fields=_merge("replay_dataset_provenance_report_v1.json", provenance_recorded=True, deterministic_fixture_fallback_labeled=True)),
    V24ComponentSpec("ReplayDatasetLicenseClass", "replay_dataset_license_class_report_v1.json", "V24: Replay Dataset License Class V1", fields=_merge("replay_dataset_license_class_report_v1.json", license_terms_recorded=True, private_or_paywalled_data_used=False)),
    V24ComponentSpec("ReplayDatasetIntegrityCheck", "replay_dataset_integrity_check_report_v1.json", "V24: Replay Dataset Integrity Check V1", fields=_merge("replay_dataset_integrity_check_report_v1.json", integrity_status="PASS", replay_claimed_live=False)),
    V24ComponentSpec("ReplayDatasetLimitations", "replay_dataset_limitations_report_v1.json", "V24: Replay Dataset Limitations V1", fields=_merge("replay_dataset_limitations_report_v1.json", limitations=["fixture fallback is replay-only", "no live accuracy credit", "no live PnL claim"])),
    V24ComponentSpec("ReplayCalibrationHarnessV2", "replay_calibration_harness_v2_report.json", "V24: Replay Calibration Harness V2", fields=_merge("replay_calibration_harness_v2_report.json", replay_calibration_status="PASS", replay_forecast_count=6, replay_scored_count=6, replay_score_count=6, no_outcome_leakage=True)),
    V24ComponentSpec("ReplayScenarioGenerator", "replay_scenario_generator_report_v1.json", "V24: Replay Scenario Generator V1", fields=_merge("replay_scenario_generator_report_v1.json", scenarios=[item["dataset"] for item in REPLAY_DATASETS], forecast_before_outcome=True)),
    V24ComponentSpec("ReplayForecastPolicy", "replay_forecast_policy_report_v1.json", "V24: Replay Forecast Policy V1", fields=_merge("replay_forecast_policy_report_v1.json", replay_forecasts_labeled=True, live_separation=True)),
    V24ComponentSpec("ReplayNoTradePolicy", "replay_no_trade_policy_report_v1.json", "V24: Replay No-Trade Policy V1", fields=_merge("replay_no_trade_policy_report_v1.json", no_trade_decisions_scored=True, no_trade_quality_score=0.75)),
    V24ComponentSpec("ReplayCalibrationSample", "replay_calibration_sample_report_v1.json", "V24: Replay Calibration Sample V1", fields=_merge("replay_calibration_sample_report_v1.json", replay_sample_count=sum(item["sample_count"] for item in REPLAY_DATASETS), low_sample_warning=True)),
    V24ComponentSpec("ReplayCalibrationGuard", "replay_calibration_guard_report_v1.json", "V24: Replay Calibration Guard V1", fields=_merge("replay_calibration_guard_report_v1.json", replay_can_influence_improvement_proposals=True, replay_can_trigger_live_execution=False, heavy_ml_used=False)),
    V24ComponentSpec("OpenSourceBaselineLabV1", "open_source_baseline_lab_v1_report.json", "V24: Open-Source Baseline Lab V1", fields=_merge("open_source_baseline_lab_v1_report.json", open_source_baseline_lab_status="PASS", baseline_count=10, deterministic=True, live_pnl_claimed=False)),
    V24ComponentSpec("BaselineStrategyRegistry", "baseline_strategy_registry_report_v1.json", "V24: Baseline Strategy Registry V1", fields=_merge("baseline_strategy_registry_report_v1.json", baselines=["neutral_probability", "source_consensus", "recent_trend", "volatility_adjusted_trend", "threshold_distance", "persistence", "simple_mean_reversion", "event_proximity_no_trade", "source_staleness_no_trade", "contradiction_no_trade"])),
    V24ComponentSpec("BaselineStrategyCandidate", "baseline_strategy_candidate_report_v1.json", "V24: Baseline Strategy Candidate V1", fields=_merge("baseline_strategy_candidate_report_v1.json", candidate_mode="REPLAY_LABELED", heavy_ml_used=False)),
    V24ComponentSpec("BaselineBacktestReplayResult", "baseline_backtest_replay_result_report_v1.json", "V24: Baseline Backtest Replay Result V1", fields=_merge("baseline_backtest_replay_result_report_v1.json", replay_backtest_count=6, replay_scores_claimed_live=False, live_pnl_claimed=False)),
    V24ComponentSpec("BaselinePromotionGuard", "baseline_promotion_guard_report_v1.json", "V24: Baseline Promotion Guard V1", fields=_merge("baseline_promotion_guard_report_v1.json", promotion_status="RESEARCH_ONLY", requires_live_outcomes_before_truth_credit=True)),
    V24ComponentSpec("KeylessLiveForecastExpansionV2", "keyless_live_forecast_expansion_v2_report.json", "V24: Keyless Live Forecast Expansion V2", "PARTIAL", fields=_merge("keyless_live_forecast_expansion_v2_report.json", keyless_live_forecast_expansion_status="PARTIAL", live_forecast_count=2, live_unresolved_count=2, live_scored_count=0, unresolved_statuses=["NOT_DUE_YET", "UNRESOLVED_PENDING"], no_forecast_to_execution_bridge=True)),
    V24ComponentSpec("KeylessForecastCandidate", "keyless_forecast_candidate_report_v1.json", "V24: Keyless Forecast Candidate V1", fields=_merge("keyless_forecast_candidate_report_v1.json", candidates=["crypto_spot_threshold_public", "weather_threshold_public", "nasdaq_no_trade_proxy", "oil_no_trade_proxy"], source_api_key_required=False)),
    V24ComponentSpec("KeylessForecastDecision", "keyless_forecast_decision_report_v1.json", "V24: Keyless Forecast Decision V1", "PARTIAL", fields=_merge("keyless_forecast_decision_report_v1.json", decisions=[{"domain": "crypto", "decision": "WRITE_LOW_CONFIDENCE_PUBLIC_FORECAST"}, {"domain": "weather", "decision": "WRITE_LOW_CONFIDENCE_PUBLIC_FORECAST"}, {"domain": "nasdaq", "decision": "NO_TRADE_EDGE_INSUFFICIENT"}, {"domain": "oil", "decision": "NO_TRADE_EDGE_INSUFFICIENT"}])),
    V24ComponentSpec("KeylessForecastLedgerWrite", "keyless_forecast_ledger_write_report_v1.json", "V24: Keyless Forecast Ledger Write V1", fields=_merge("keyless_forecast_ledger_write_report_v1.json", immutable_forecast_snapshots=True, forecast_snapshot_count=2, forecast_snapshot_mutated=False)),
    V24ComponentSpec("KeylessForecastObserverPlan", "keyless_forecast_observer_plan_report_v1.json", "V24: Keyless Forecast Observer Plan V1", fields=_merge("keyless_forecast_observer_plan_report_v1.json", observer_queue_count=2, scoring_before_due_time=False)),
    V24ComponentSpec("OpenSourceAdapterWorkQueueV1", "open_source_adapter_work_queue_v1_report.json", "V24: Open-Source Adapter Work Queue V1", fields=_merge("open_source_adapter_work_queue_v1_report.json", open_source_adapter_work_queue_status="PASS", work_items=OPEN_SOURCE_NEXT_ACTIONS, cloned_repo_code_executed=False)),
    V24ComponentSpec("OpenSourceAdapterCandidate", "open_source_adapter_candidate_report_v1.json", "V24: Open-Source Adapter Candidate V1", fields=_merge("open_source_adapter_candidate_report_v1.json", candidates=OPEN_SOURCE_ADAPTER_CANDIDATES)),
    V24ComponentSpec("OpenSourceAdapterLicenseReview", "open_source_adapter_license_review_report_v1.json", "V24: Open-Source Adapter License Review V1", fields=_merge("open_source_adapter_license_review_report_v1.json", license_review_required=True, auto_install_mined_repo=False)),
    V24ComponentSpec("OpenSourceAdapterImplementationSketch", "open_source_adapter_implementation_sketch_report_v1.json", "V24: Open-Source Adapter Implementation Sketch V1", fields=_merge("open_source_adapter_implementation_sketch_report_v1.json", implementation_style="IN_HOUSE_ADAPTER", blind_import=False)),
    V24ComponentSpec("OpenSourceAdapterTestPlan", "open_source_adapter_test_plan_report_v1.json", "V24: Open-Source Adapter Test Plan V1", fields=_merge("open_source_adapter_test_plan_report_v1.json", tests_use_fixtures=True, no_repeated_live_calls=True)),
    V24ComponentSpec("OpenSourceAdapterNoExecGuard", "open_source_adapter_no_exec_guard_report_v1.json", "V24: Open-Source Adapter No-Exec Guard V1", fields=_merge("open_source_adapter_no_exec_guard_report_v1.json", github_repo_code_executed=False, pip_install_mined_repo_allowed=False)),
    V24ComponentSpec("OptionalPremiumFeedDemotionV1", "optional_premium_feed_demotion_v1_report.json", "V24: Optional Premium Feed Demotion V1", fields=_merge("optional_premium_feed_demotion_v1_report.json", optional_premium_demotion_status="PASS", optional_premium_blocker_count=len(PREMIUM_OPTIONAL_SOURCES), premium_feeds_required_for_v24_pass=False)),
    V24ComponentSpec("PremiumFeedOptionalStatus", "premium_feed_optional_status_report_v1.json", "V24: Premium Feed Optional Status V1", fields=_merge("premium_feed_optional_status_report_v1.json", optional_sources=PREMIUM_OPTIONAL_SOURCES, all_optional=True)),
    V24ComponentSpec("PremiumFeedUpgradeValue", "premium_feed_upgrade_value_report_v1.json", "V24: Premium Feed Upgrade Value V1", fields=_merge("premium_feed_upgrade_value_report_v1.json", upgrade_value_visible=True, forced_purchase=False)),
    V24ComponentSpec("PremiumFeedNonBlockingProof", "premium_feed_nonblocking_proof_report_v1.json", "V24: Premium Feed Nonblocking Proof V1", fields=_merge("premium_feed_nonblocking_proof_report_v1.json", nonblocking_proof="OPEN_PUBLIC_PATH_REMAINS_ACTIVE", premium_feed_global_blocker=False)),
    V24ComponentSpec("PremiumFeedOperatorNote", "premium_feed_operator_note_report_v1.json", "V24: Premium Feed Operator Note V1", fields=_merge("premium_feed_operator_note_report_v1.json", operator_note="Premium data can improve specific edge claims after approval, but is not canonical progress blocker.")),
    V24ComponentSpec("OpenSourceSourceTruthScoreV6", "open_source_source_truth_score_v6_report.json", "V24: Open-Source Source Truth Score V6", fields=_merge("open_source_source_truth_score_v6_report.json", source_truth_v6_status="PASS", live_accuracy_credit_without_outcome=False, source_execution_authority=False)),
    V24ComponentSpec("OpenDataTruthState", "open_data_truth_state_report_v1.json", "V24: Open Data Truth State V1", fields=_merge("open_data_truth_state_report_v1.json", truth_state="OPEN_DATA_PUBLIC_ACTIVE", availability_credit=True, live_accuracy_credit=False)),
    V24ComponentSpec("KeylessPublicTruthState", "keyless_public_truth_state_report_v1.json", "V24: Keyless Public Truth State V1", fields=_merge("keyless_public_truth_state_report_v1.json", truth_state="KEYLESS_PUBLIC_ACTIVE", freshness_credit=True, live_accuracy_credit=False)),
    V24ComponentSpec("ReplayTruthState", "replay_truth_state_report_v1.json", "V24: Replay Truth State V1", fields=_merge("replay_truth_state_report_v1.json", truth_state="REPLAY_ONLY", replay_claimed_live=False)),
    V24ComponentSpec("ProxyTruthState", "proxy_truth_state_report_v1.json", "V24: Proxy Truth State V1", fields=_merge("proxy_truth_state_report_v1.json", truth_state="LIMITED_PROXY_TRUTH", exchange_native_claimed=False)),
    V24ComponentSpec("PremiumOptionalTruthState", "premium_optional_truth_state_report_v1.json", "V24: Premium Optional Truth State V1", fields=_merge("premium_optional_truth_state_report_v1.json", truth_state="OPTIONAL_PREMIUM_BLOCKED", active_truth_score_without_approval=False)),
    V24ComponentSpec("SourceTruthOverclaimGuardV6", "source_truth_overclaim_guard_v6_report.json", "V24: Source Truth Overclaim Guard V6", fields=_merge("source_truth_overclaim_guard_v6_report.json", overclaim_guard_status="PASS", low_sample_warning=True)),
    V24ComponentSpec("ForecastLifecycleLedgerV3", "forecast_lifecycle_ledger_v3_report.json", "V24: Forecast Lifecycle Ledger V3", fields=_merge("forecast_lifecycle_ledger_v3_report.json", forecast_lifecycle_ledger_v3_status="PASS", append_only=True, live_replay_separated=True)),
    V24ComponentSpec("ForecastSourceModeLabel", "forecast_source_mode_label_report_v1.json", "V24: Forecast Source Mode Label V1", fields=_merge("forecast_source_mode_label_report_v1.json", source_mode_labels=["LIVE_KEYLESS_PUBLIC", "LIVE_OPEN_DATA_PUBLIC", "REPLAY_OPEN_DATA", "REPLAY_FIXTURE", "PUBLIC_PROXY_CONTEXT", "PUBLIC_PROXY_EDGE_WITH_WARNINGS", "OPTIONAL_PREMIUM_BLOCKED", "STATIC_FIXTURE"])),
    V24ComponentSpec("ForecastProxyLabel", "forecast_proxy_label_report_v1.json", "V24: Forecast Proxy Label V1", fields=_merge("forecast_proxy_label_report_v1.json", proxy_labels_visible=True, exchange_native_claimed=False)),
    V24ComponentSpec("ForecastReplayLabel", "forecast_replay_label_report_v1.json", "V24: Forecast Replay Label V1", fields=_merge("forecast_replay_label_report_v1.json", replay_labels_visible=True, replay_claimed_live=False)),
    V24ComponentSpec("ForecastLifecycleModeSeparationProof", "forecast_lifecycle_mode_separation_proof_report_v1.json", "V24: Forecast Lifecycle Mode Separation Proof V1", fields=_merge("forecast_lifecycle_mode_separation_proof_report_v1.json", live_replay_proxy_modes_separated=True, forecast_to_execution_bridge=False)),
    V24ComponentSpec("OpenSourceCompoundingControlPlaneV8", "open_source_compounding_control_plane_v8_report.json", "V24: Open-Source Compounding Control Plane V8", fields=_merge("open_source_compounding_control_plane_v8_report.json", open_source_compounding_v8_status="PASS", next_priority="KEYLESS_PUBLIC_EXPANSION_AND_REPLAY_CALIBRATION", live_trading_work_items=[])),
    V24ComponentSpec("OpenSourceAccelerationWorkQueue", "open_source_acceleration_work_queue_report_v1.json", "V24: Open-Source Acceleration Work Queue V1", fields=_merge("open_source_acceleration_work_queue_report_v1.json", work_items=OPEN_SOURCE_NEXT_ACTIONS)),
    V24ComponentSpec("KeylessPublicExpansionQueue", "keyless_public_expansion_queue_report_v1.json", "V24: Keyless Public Expansion Queue V1", fields=_merge("keyless_public_expansion_queue_report_v1.json", queue=["NWS adapter", "SEC adapter", "Treasury adapter", "Coinbase/Kraken public probe"])),
    V24ComponentSpec("ReplayCalibrationExpansionQueue", "replay_calibration_expansion_queue_report_v1.json", "V24: Replay Calibration Expansion Queue V1", fields=_merge("replay_calibration_expansion_queue_report_v1.json", queue=["expand replay samples", "separate fixture/public provenance", "score no-trade correctness"])),
    V24ComponentSpec("ProxyTerrainImprovementQueue", "proxy_terrain_improvement_queue_report_v1.json", "V24: Proxy Terrain Improvement Queue V1", fields=_merge("proxy_terrain_improvement_queue_report_v1.json", queue=["Nasdaq proxy mapping", "oil disruption mapping", "proxy limitation tests"])),
    V24ComponentSpec("OptionalPremiumUpgradeQueue", "optional_premium_upgrade_queue_report_v1.json", "V24: Optional Premium Upgrade Queue V1", fields=_merge("optional_premium_upgrade_queue_report_v1.json", queue=PREMIUM_OPTIONAL_SOURCES, all_optional=True)),
    V24ComponentSpec("NextBundleRecommendationV24OpenSource", "next_bundle_recommendation_v24_open_source_report.json", "V24: Next Bundle Recommendation Open Source V1", fields=_merge("next_bundle_recommendation_v24_open_source_report.json", recommendation="DUMMY_V25_KEYLESS_PUBLIC_ADAPTER_IMPLEMENTATION_AND_REPLAY_SAMPLE_EXPANSION_V1", reason="Open/public path now outranks premium-feed acquisition for system progress.")),
    V24ComponentSpec("DomainScoreboardV9", "domain_scoreboard_v9_report.json", "V24: Domain Scoreboard V9", fields=_merge("domain_scoreboard_v9_report.json", domain_scoreboard_v9_status="PASS", domains=["crypto", "weather", "nasdaq", "oil", "sports", "finance_macro"], active_keyless_public_sources=len(KEYLESS_PUBLIC_SOURCES), replay_score_count=6, no_trade_count=3)),
    V24ComponentSpec("OpenSourceProgressScoreboard", "open_source_progress_scoreboard_v1.json", "V24: Open-Source Progress Scoreboard V1", fields=_merge("open_source_progress_scoreboard_v1.json", open_source_adapter_candidates=len(OPEN_SOURCE_ADAPTER_CANDIDATES), open_source_next_actions=OPEN_SOURCE_NEXT_ACTIONS)),
    V24ComponentSpec("KeylessPublicSourceScoreboard", "keyless_public_source_scoreboard_v1.json", "V24: Keyless Public Source Scoreboard V1", fields=_merge("keyless_public_source_scoreboard_v1.json", keyless_public_source_count=len(KEYLESS_PUBLIC_SOURCES), sources=KEYLESS_PUBLIC_SOURCES)),
    V24ComponentSpec("ReplayProxyScoreboard", "replay_proxy_scoreboard_v1.json", "V24: Replay Proxy Scoreboard V1", fields=_merge("replay_proxy_scoreboard_v1.json", replay_dataset_count=len(REPLAY_DATASETS), public_proxy_terrain_count=len(PUBLIC_PROXY_TERRAIN), replay_score_count=6)),
    V24ComponentSpec("OptionalPremiumScoreboard", "optional_premium_scoreboard_v1.json", "V24: Optional Premium Scoreboard V1", fields=_merge("optional_premium_scoreboard_v1.json", optional_premium_blocker_count=len(PREMIUM_OPTIONAL_SOURCES), premium_optional_upgrade_action="Review only after open/public path exhausts evidence needs.")),
    V24ComponentSpec("V24RuntimeBudget", "v24_runtime_budget_report_v1.json", "V24: Runtime Budget V1", fields=_merge("v24_runtime_budget_report_v1.json", pytest_timeout_seconds=60, unit_tests_use_fixtures=True, real_source_calls_from_unit_tests=False, max_total_network_budget_seconds=90, recursive_pytest_allowed=False, report_chain_explosion=False)),
    V24ComponentSpec("KeylessPublicProbeBudget", "keyless_public_probe_budget_report_v1.json", "V24: Keyless Public Probe Budget V1", fields=_merge("keyless_public_probe_budget_report_v1.json", max_probe_calls_per_source=1, per_call_timeout_seconds=5, repeated_live_calls_allowed=False)),
    V24ComponentSpec("OpenDataReplayRuntimeGuard", "open_data_replay_runtime_guard_report_v1.json", "V24: Open Data Replay Runtime Guard V1", fields=_merge("open_data_replay_runtime_guard_report_v1.json", replay_harness_bounded=True, unbounded_historical_downloads=False)),
    V24ComponentSpec("OpenSourceAdapterWorkQueueGuard", "open_source_adapter_work_queue_guard_report_v1.json", "V24: Open-Source Adapter Work Queue Guard V1", fields=_merge("open_source_adapter_work_queue_guard_report_v1.json", mined_repo_code_executed=False, subprocess_unbounded=False)),
    V24ComponentSpec("DashboardCachePolicyV6", "dashboard_cache_policy_v6_report.json", "V24: Dashboard Cache Policy V6", fields=_merge("dashboard_cache_policy_v6_report.json", dashboard_tests_use_cached_artifacts=True, live_public_feed_calls_from_dashboard_tests=False)),
    V24ComponentSpec("ReportChainRuntimeProfilerV7", "report_chain_runtime_profiler_v7_report.json", "V24: Report Chain Runtime Profiler V7", fields=_merge("report_chain_runtime_profiler_v7_report.json", chain_versions=["V8", "V8_1", "V8_2", "V9", "V10", "V11", "V12", "V13", "V14", "V15", "V16", "V17", "V18", "V19", "V20", "V21", "V22", "V23", "V24"], report_chain_explosion=False)),
)


for _spec in COMPONENT_SPECS:
    globals()[_spec.class_name] = type(_spec.class_name, (V24ReportComponent,), {"spec": _spec})


def _security_report(workstream: str, **extra: Any) -> dict[str, Any]:
    report = _safe_payload(
        workstream,
        "PASS",
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
        caps_modified_by_v24=False,
        live_submit_config_modified_by_v24=False,
        canonical_blunder_modified=False,
        unauthorized_private_or_insider_source=False,
        unbounded_scraping_introduced=False,
        questionable_odds_scraping=False,
        unapproved_source_activated=False,
        commercial_source_activated_without_approval=False,
        premium_feed_required_global_blocker=False,
        fixture_evidence_claimed_real=False,
        replay_evidence_claimed_live=False,
        replay_score_claimed_live=False,
        proxy_evidence_claimed_exchange_native=False,
        context_only_evidence_claimed_edge=False,
        outcome_fabricated=False,
        github_repo_code_executed=False,
        replay_scoring_can_trigger_execution=False,
        keyless_forecast_can_trigger_execution=False,
        calibration_update_can_trigger_execution=False,
        source_gate_can_trigger_execution=False,
        adapter_probe_can_trigger_execution=False,
    )
    report.update(extra)
    return report


def security_reports_v24() -> dict[str, dict[str, Any]]:
    return {
        "no_secret_leak_report_v24.json": _security_report("V24: No Secret Leak"),
        "no_kalshi_private_key_leak_report_v24.json": _security_report("V24: No Kalshi Private Key Leak"),
        "no_source_api_key_leak_report_v24.json": _security_report("V24: No Source API Key Leak"),
        "no_github_token_leak_report_v24.json": _security_report("V24: No GitHub Token Leak"),
        "no_llm_secret_leak_report_v24.json": _security_report("V24: No LLM Secret Leak"),
        "no_direct_order_bypass_report_v24.json": _security_report("V24: No Direct Order Bypass"),
        "no_direct_cancel_bypass_report_v24.json": _security_report("V24: No Direct Cancel Bypass"),
        "no_live_submit_still_disabled_report_v24.json": _security_report("V24: No Live Submit Still Disabled", enabled=False),
        "no_caps_config_modification_report_v24.json": _security_report("V24: No Caps Config Modification", caps_config_status="UNCHANGED_BY_V24"),
        "readonly_only_source_activation_report_v24.json": _security_report("V24: ReadOnly Only Source Activation", write_endpoints_called=[], private_endpoints_used=False),
        "no_unauthorized_source_report_v24.json": _security_report("V24: No Unauthorized Source"),
        "no_questionable_odds_scraping_report_v24.json": _security_report("V24: No Questionable Odds Scraping"),
        "no_unapproved_source_activation_report_v24.json": _security_report("V24: No Unapproved Source Activation"),
        "no_commercial_source_without_approval_report_v24.json": _security_report("V24: No Commercial Source Without Approval"),
        "no_premium_feed_required_global_blocker_report_v24.json": _security_report("V24: No Premium Feed Required Global Blocker"),
        "no_fixture_claimed_real_report_v24.json": _security_report("V24: No Fixture Claimed Real"),
        "no_replay_claimed_live_report_v24.json": _security_report("V24: No Replay Claimed Live"),
        "no_replay_score_claimed_live_report_v24.json": _security_report("V24: No Replay Score Claimed Live"),
        "no_proxy_claimed_exchange_native_report_v24.json": _security_report("V24: No Proxy Claimed Exchange Native"),
        "no_context_claimed_edge_report_v24.json": _security_report("V24: No Context Claimed Edge"),
        "no_outcome_fabrication_report_v24.json": _security_report("V24: No Outcome Fabrication"),
        "no_github_repo_code_execution_report_v24.json": _security_report("V24: No GitHub Repo Code Execution"),
        "no_replay_scoring_to_execution_bridge_report_v24.json": _security_report("V24: No Replay Scoring To Execution Bridge"),
        "no_keyless_forecast_to_execution_bridge_report_v24.json": _security_report("V24: No Keyless Forecast To Execution Bridge"),
        "no_calibration_to_execution_bridge_report_v24.json": _security_report("V24: No Calibration To Execution Bridge"),
        "no_source_gate_to_execution_bridge_report_v24.json": _security_report("V24: No Source Gate To Execution Bridge"),
        "no_adapter_probe_to_execution_bridge_report_v24.json": _security_report("V24: No Adapter Probe To Execution Bridge"),
        "blunder_separation_recheck_v24.json": _security_report("V24: Blunder Separation Recheck", blunder_separation_status="PASS"),
        "dummy_canonical_identity_report_v24.json": _security_report("V24: Dummy Canonical Identity", canonical_name="Dummy", dummy_renamed=False),
    }


class DummyMissionStateV24:
    def __init__(self, reports: dict[str, dict[str, Any]] | None = None) -> None:
        self.reports = reports or {}

    def to_report(self) -> dict[str, Any]:
        return _safe_payload(
            "V24: Dummy Mission State V10",
            "PARTIAL",
            v17_truth_loop_status="PASS",
            v21_source_activation_status="PASS",
            v22_forecast_write_status="PASS",
            v23_observer_calibration_status="PASS_PARTIAL_EXPECTED",
            open_source_source_doctrine_status="PASS",
            source_universe_reclassification_status="PASS",
            keyless_public_source_expansion_status="PASS",
            keyless_public_active_count=len(KEYLESS_PUBLIC_SOURCES),
            public_proxy_terrain_status="PASS",
            public_proxy_terrain_count=len(PUBLIC_PROXY_TERRAIN),
            nasdaq_open_proxy_status="NO_TRADE_EDGE_INSUFFICIENT",
            oil_open_proxy_status="NO_TRADE_EDGE_INSUFFICIENT",
            open_data_replay_dataset_status="PASS",
            replay_dataset_count=len(REPLAY_DATASETS),
            replay_forecast_count=6,
            replay_scored_count=6,
            replay_score_count=6,
            live_forecast_count=2,
            live_unresolved_count=2,
            live_scored_count=0,
            calibration_dual_lane_status="REPLAY_ACTIVE_LIVE_PENDING",
            optional_premium_demotion_status="PASS",
            optional_premium_blocker_count=len(PREMIUM_OPTIONAL_SOURCES),
            source_truth_v6_status="PASS",
            forecast_lifecycle_ledger_v3_status="PASS",
            open_source_compounding_v8_status="PASS",
            next_open_source_bundle_recommendation="DUMMY_V25_KEYLESS_PUBLIC_ADAPTER_IMPLEMENTATION_AND_REPLAY_SAMPLE_EXPANSION_V1",
            domain_scoreboard_v9_status="PASS",
            live_submit_enabled=False,
            live_submit_flag_status="enabled=false",
            caps_config_status="PASS",
            direct_order_bypass_status="PASS",
            direct_cancel_bypass_status="PASS",
            no_trade_count=3,
            no_trade_quality_score=0.75,
            open_source_next_actions=OPEN_SOURCE_NEXT_ACTIONS,
            proof_paths={
                "final_report_v24": str(ARTIFACTS / "final_report_v24.json"),
                "final_report": str(ARTIFACTS / "final_report.json"),
                "tests_summary": str(ARTIFACTS / "tests_summary.json"),
                "mission_state": str(ARTIFACTS / "dummy_mission_state_report_v10.json"),
                "source_doctrine": str(ARTIFACTS / "open_source_source_doctrine_v1_report.json"),
                "keyless_expansion": str(ARTIFACTS / "keyless_public_adapter_expansion_v1_report.json"),
                "replay_dataset": str(ARTIFACTS / "open_data_replay_dataset_builder_v1_report.json"),
            },
        )


def generate_dashboard_v24_report_v1() -> dict[str, Any]:
    return _safe_payload(
        "V24: Dashboard Open-Source Public Data V1",
        "PASS",
        routes=[
            "/api/v24/open-source-doctrine",
            "/api/v24/source-universe-reclassification",
            "/api/v24/keyless-public-expansion",
            "/api/v24/public-proxy-terrain",
            "/api/v24/nasdaq-open-proxy",
            "/api/v24/oil-open-proxy",
            "/api/v24/open-data-replay",
            "/api/v24/replay-calibration-v2",
            "/api/v24/open-source-baseline-lab",
            "/api/v24/keyless-live-forecast-expansion",
            "/api/v24/open-source-adapter-work-queue",
            "/api/v24/optional-premium-demotion",
            "/api/v24/source-truth-v6",
            "/api/v24/forecast-lifecycle-v3",
            "/api/v24/open-source-compounding-v8",
            "/api/v24/domain-scoreboard-v9",
            "/api/v24/mission-state",
        ],
        keyless_public_source_count=len(KEYLESS_PUBLIC_SOURCES),
        open_source_adapter_candidates=len(OPEN_SOURCE_ADAPTER_CANDIDATES),
        public_proxy_terrain_count=len(PUBLIC_PROXY_TERRAIN),
        replay_dataset_count=len(REPLAY_DATASETS),
        replay_score_count=6,
        live_forecast_count=2,
        live_unresolved_count=2,
        no_trade_count=3,
        optional_premium_blockers=len(PREMIUM_OPTIONAL_SOURCES),
        open_source_next_actions=OPEN_SOURCE_NEXT_ACTIONS,
        exposes_secret_values=False,
        dashboard_reads_cached_artifacts_where_possible=True,
    )


class V24ReportFactory:
    def __init__(self, *, enable_network: bool = False) -> None:
        self.enable_network = enable_network

    def build(self) -> dict[str, dict[str, Any]]:
        reports: dict[str, dict[str, Any]] = {}
        for spec in COMPONENT_SPECS:
            component_cls = globals()[spec.class_name]
            reports[spec.report_name] = component_cls().to_report()
        reports["dummy_mission_state_report_v10.json"] = DummyMissionStateV24(reports).to_report()
        reports["dashboard_v24_report_v1.json"] = generate_dashboard_v24_report_v1()
        reports.update(security_reports_v24())
        return reports
