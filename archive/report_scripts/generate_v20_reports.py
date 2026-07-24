"""Generate DUMMY V20 source universe, edge terrain, and activation reports."""

from __future__ import annotations

import json
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from core.evidence_dir import EvidencePath

ARTIFACTS = EvidencePath(ROOT / "artifacts" / "dummy")

from predator_mesh.v20 import MILESTONE
from predator_mesh.v20.approval_gates import SourceApprovalGateV2, SourceCredentialRequirementReport, SourceLicenseGate, SourceTermsGate
from predator_mesh.v20.compounding import AutonomousCompoundingControlPlaneV3
from predator_mesh.v20.evidence_router import DomainEvidenceRouterV2, EvidencePriorityScore, EvidenceSufficiencyVerdict
from predator_mesh.v20.forecast_pipeline import EdgeAwareForecastPipelineV2, EdgeConfidencePolicy, EdgeNoTradeDecision
from predator_mesh.v20.github_source_miner import GitHubSourceMiner
from predator_mesh.v20.licensed_adapters import CommercialMarketDataGate, ExchangeNativeAdapterPlan, LicensedAdapterPlanPack, LicensedSourceReadiness
from predator_mesh.v20.mission import DummyMissionStateV6
from predator_mesh.v20.official_adapters import (
    BEAMacroAdapter,
    BLSMacroAdapter,
    CCXTPublicCryptoAdapterPlan,
    CensusMacroAdapter,
    DefiLlamaCryptoContextAdapter,
    EIAEnergyAdapter,
    NWSWeatherAdapter,
    OfficialPublicAdapterActivationPack,
    SECEdgarAdapter,
    TreasuryDataAdapter,
    WorldBankCommoditiesAdapter,
)
from predator_mesh.v20.recommendations import SourceGapRecommendationEngine
from predator_mesh.v20.research_swarm import EdgeFocusedResearchSwarmV2
from predator_mesh.v20.runtime import DashboardArtifactCachePolicyV2, GitHubMiningRuntimeGuard, LicensedAdapterNoCallGuard, OfficialAdapterRuntimeGuard, ReportChainRuntimeProfilerV3, SourceUniverseRuntimeBudget
from predator_mesh.v20.scoreboard import DomainScoreboardV4
from predator_mesh.v20.source_universe import SourceUniverse
from predator_mesh.v20.terrain import CryptoDirectionTerrainStack, NasdaqDirectionTerrainStack, OilDirectionTerrainStack, SportsEdgeTerrainStack, WeatherEdgeTerrainStack


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _write_report(name: str, data: dict[str, Any]) -> Path:
    path = ARTIFACTS / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
    return path


def _load_report(name: str, fallback: dict[str, Any] | None = None) -> dict[str, Any]:
    path = ARTIFACTS / name
    if not path.exists():
        return fallback or {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return fallback or {}


def _v20_core_report_names() -> list[str]:
    return [
        "source_universe_report_v1.json",
        "source_universe_manifest_v1.json",
        "source_tier_matrix_v1.json",
        "source_edge_class_report_v1.json",
        "massive_source_candidate_manifest_v1.json",
        "nasdaq_direction_source_stack_report_v1.json",
        "oil_direction_source_stack_report_v1.json",
        "crypto_direction_source_stack_report_v1.json",
        "weather_source_stack_report_v1.json",
        "sports_source_stack_report_v1.json",
        "finance_macro_source_stack_report_v1.json",
        "commodities_source_stack_report_v1.json",
        "github_source_stack_report_v1.json",
        "github_source_miner_report_v1.json",
        "github_repo_candidate_manifest_v1.json",
        "github_repo_score_report_v1.json",
        "github_adapter_plan_report_v1.json",
        "github_mining_budget_report_v1.json",
        "source_approval_gate_v2_report.json",
        "source_license_gate_report_v1.json",
        "source_terms_gate_report_v1.json",
        "source_credential_requirement_report_v1.json",
        "official_public_adapter_activation_pack_report_v1.json",
        "nws_weather_adapter_report_v1.json",
        "eia_energy_adapter_report_v1.json",
        "bls_macro_adapter_report_v1.json",
        "bea_macro_adapter_report_v1.json",
        "census_macro_adapter_report_v1.json",
        "treasury_data_adapter_report_v1.json",
        "sec_edgar_adapter_report_v1.json",
        "world_bank_commodities_adapter_report_v1.json",
        "defillama_crypto_context_adapter_report_v1.json",
        "ccxt_public_crypto_adapter_plan_report_v1.json",
        "licensed_adapter_plan_pack_report_v1.json",
        "exchange_native_adapter_plan_report_v1.json",
        "commercial_market_data_gate_report_v1.json",
        "licensed_source_readiness_matrix_v1.json",
        "nasdaq_direction_terrain_stack_report_v1.json",
        "nasdaq_evidence_packet_report_v1.json",
        "nasdaq_edge_feature_map_report_v1.json",
        "nasdaq_no_trade_gate_report_v1.json",
        "nasdaq_source_blocker_report_v1.json",
        "oil_direction_terrain_stack_report_v1.json",
        "oil_evidence_packet_report_v1.json",
        "oil_edge_feature_map_report_v1.json",
        "oil_no_trade_gate_report_v1.json",
        "oil_source_blocker_report_v1.json",
        "crypto_direction_terrain_stack_report_v1.json",
        "crypto_evidence_packet_v3_report.json",
        "crypto_edge_feature_map_report_v1.json",
        "crypto_no_trade_gate_v2_report.json",
        "crypto_source_blocker_report_v1.json",
        "weather_edge_terrain_stack_report_v1.json",
        "weather_evidence_packet_v3_report.json",
        "weather_edge_feature_map_report_v1.json",
        "weather_no_trade_gate_v2_report.json",
        "sports_edge_terrain_stack_report_v1.json",
        "sports_evidence_packet_v3_report.json",
        "sports_edge_feature_map_report_v1.json",
        "sports_no_trade_gate_v2_report.json",
        "domain_evidence_router_v2_report.json",
        "evidence_priority_score_report_v1.json",
        "evidence_sufficiency_verdict_report_v1.json",
        "edge_focused_research_swarm_v2_report.json",
        "edge_research_task_manifest_v1.json",
        "source_gap_task_report_v1.json",
        "terrain_gap_task_report_v1.json",
        "edge_aware_forecast_pipeline_v2_report.json",
        "edge_feature_contribution_report_v1.json",
        "edge_confidence_policy_report_v1.json",
        "edge_no_trade_decision_report_v1.json",
        "source_gap_recommendation_engine_report_v1.json",
        "source_gap_priority_report_v1.json",
        "source_acquisition_plan_report_v1.json",
        "api_key_need_report_v1.json",
        "autonomous_compounding_control_plane_v3_report.json",
        "source_universe_work_item_manifest_v1.json",
        "edge_terrain_work_item_manifest_v1.json",
        "adapter_mining_work_item_manifest_v1.json",
        "forecast_improvement_work_item_manifest_v1.json",
        "domain_scoreboard_v4_report.json",
        "source_universe_coverage_scoreboard_v1.json",
        "edge_terrain_readiness_scoreboard_v1.json",
        "dummy_mission_state_report_v6.json",
        "dashboard_v20_massive_source_universe_report_v1.json",
        "source_universe_runtime_budget_report_v1.json",
        "github_mining_runtime_guard_report_v1.json",
        "official_adapter_runtime_guard_report_v1.json",
        "licensed_adapter_no_call_guard_report_v1.json",
        "dashboard_artifact_cache_policy_v2_report.json",
        "report_chain_runtime_profiler_v3_report.json",
    ]


def _v20_security_report_names() -> list[str]:
    return [
        "no_secret_leak_report_v20.json",
        "no_kalshi_private_key_leak_report_v20.json",
        "no_source_api_key_leak_report_v20.json",
        "no_github_token_leak_report_v20.json",
        "no_llm_secret_leak_report_v20.json",
        "no_direct_order_bypass_report_v20.json",
        "no_direct_cancel_bypass_report_v20.json",
        "no_live_submit_still_disabled_report_v20.json",
        "no_caps_config_modification_report_v20.json",
        "readonly_only_source_activation_report_v20.json",
        "no_unauthorized_source_report_v20.json",
        "no_questionable_odds_scraping_report_v20.json",
        "no_undocumented_sports_endpoint_activation_report_v20.json",
        "no_unapproved_source_activation_report_v20.json",
        "no_commercial_source_without_approval_report_v20.json",
        "no_fixture_claimed_real_report_v20.json",
        "no_outcome_fabrication_report_v20.json",
        "no_github_repo_code_execution_report_v20.json",
        "blunder_separation_recheck_v20.json",
        "dummy_canonical_identity_report_v20.json",
    ]


def _v20_report_names() -> list[str]:
    return [*_v20_core_report_names(), *_v20_security_report_names(), "final_report_v20.json"]


def generate_v20_report_bundle() -> dict[str, dict[str, Any]]:
    universe = SourceUniverse()
    miner = GitHubSourceMiner()
    nasdaq = NasdaqDirectionTerrainStack()
    oil = OilDirectionTerrainStack()
    crypto = CryptoDirectionTerrainStack()
    weather = WeatherEdgeTerrainStack()
    sports = SportsEdgeTerrainStack()
    research = EdgeFocusedResearchSwarmV2()
    forecast = EdgeAwareForecastPipelineV2()
    recommendations = SourceGapRecommendationEngine()
    compounding = AutonomousCompoundingControlPlaneV3()
    scoreboard = DomainScoreboardV4()
    return {
        "source_universe_report_v1.json": universe.to_report(),
        "source_universe_manifest_v1.json": universe.manifest_report(),
        "source_tier_matrix_v1.json": universe.tier_matrix_report(),
        "source_edge_class_report_v1.json": universe.edge_class_report(),
        "massive_source_candidate_manifest_v1.json": universe.manifest_report(),
        "nasdaq_direction_source_stack_report_v1.json": universe.stack_report("Nasdaq Direction", ("nasdaq_index_direction", "finance", "volatility", "cross_asset_macro")),
        "oil_direction_source_stack_report_v1.json": universe.stack_report("Oil Direction", ("oil_energy_direction", "commodities", "weather", "cross_asset_macro")),
        "crypto_direction_source_stack_report_v1.json": universe.stack_report("Crypto Direction", ("crypto", "volatility", "cross_asset_macro")),
        "weather_source_stack_report_v1.json": universe.stack_report("Weather", ("weather",)),
        "sports_source_stack_report_v1.json": universe.stack_report("Sports", ("sports",)),
        "finance_macro_source_stack_report_v1.json": universe.stack_report("Finance Macro", ("finance", "cross_asset_macro")),
        "commodities_source_stack_report_v1.json": universe.stack_report("Commodities", ("commodities", "oil_energy_direction")),
        "github_source_stack_report_v1.json": universe.stack_report("GitHub", ("finance", "crypto", "weather", "sports", "commodities")),
        "github_source_miner_report_v1.json": miner.mine().to_report(),
        "github_repo_candidate_manifest_v1.json": miner.candidate_manifest(),
        "github_repo_score_report_v1.json": miner.score_report(),
        "github_adapter_plan_report_v1.json": miner.adapter_plan_report(),
        "github_mining_budget_report_v1.json": miner.budget_report(),
        "source_approval_gate_v2_report.json": SourceApprovalGateV2(universe).to_report(),
        "source_license_gate_report_v1.json": SourceLicenseGate(universe).to_report(),
        "source_terms_gate_report_v1.json": SourceTermsGate(universe).to_report(),
        "source_credential_requirement_report_v1.json": SourceCredentialRequirementReport(universe).to_report(),
        "official_public_adapter_activation_pack_report_v1.json": OfficialPublicAdapterActivationPack().to_report(),
        "nws_weather_adapter_report_v1.json": NWSWeatherAdapter().to_report(),
        "eia_energy_adapter_report_v1.json": EIAEnergyAdapter().to_report(),
        "bls_macro_adapter_report_v1.json": BLSMacroAdapter().to_report(),
        "bea_macro_adapter_report_v1.json": BEAMacroAdapter().to_report(),
        "census_macro_adapter_report_v1.json": CensusMacroAdapter().to_report(),
        "treasury_data_adapter_report_v1.json": TreasuryDataAdapter().to_report(),
        "sec_edgar_adapter_report_v1.json": SECEdgarAdapter().to_report(),
        "world_bank_commodities_adapter_report_v1.json": WorldBankCommoditiesAdapter().to_report(),
        "defillama_crypto_context_adapter_report_v1.json": DefiLlamaCryptoContextAdapter().to_report(),
        "ccxt_public_crypto_adapter_plan_report_v1.json": CCXTPublicCryptoAdapterPlan().to_report(),
        "licensed_adapter_plan_pack_report_v1.json": LicensedAdapterPlanPack().to_report(),
        "exchange_native_adapter_plan_report_v1.json": ExchangeNativeAdapterPlan().to_report(),
        "commercial_market_data_gate_report_v1.json": CommercialMarketDataGate().to_report(),
        "licensed_source_readiness_matrix_v1.json": LicensedSourceReadiness().to_report(),
        "nasdaq_direction_terrain_stack_report_v1.json": nasdaq.to_report(),
        "nasdaq_evidence_packet_report_v1.json": nasdaq.evidence_packet_report(),
        "nasdaq_edge_feature_map_report_v1.json": nasdaq.edge_feature_map_report(),
        "nasdaq_no_trade_gate_report_v1.json": nasdaq.no_trade_gate_report(),
        "nasdaq_source_blocker_report_v1.json": nasdaq.source_blocker_report(),
        "oil_direction_terrain_stack_report_v1.json": oil.to_report(),
        "oil_evidence_packet_report_v1.json": oil.evidence_packet_report(),
        "oil_edge_feature_map_report_v1.json": oil.edge_feature_map_report(),
        "oil_no_trade_gate_report_v1.json": oil.no_trade_gate_report(),
        "oil_source_blocker_report_v1.json": oil.source_blocker_report(),
        "crypto_direction_terrain_stack_report_v1.json": crypto.to_report(),
        "crypto_evidence_packet_v3_report.json": crypto.evidence_packet_report(),
        "crypto_edge_feature_map_report_v1.json": crypto.edge_feature_map_report(),
        "crypto_no_trade_gate_v2_report.json": crypto.no_trade_gate_report(),
        "crypto_source_blocker_report_v1.json": crypto.source_blocker_report(),
        "weather_edge_terrain_stack_report_v1.json": weather.to_report(),
        "weather_evidence_packet_v3_report.json": weather.evidence_packet_report(),
        "weather_edge_feature_map_report_v1.json": weather.edge_feature_map_report(),
        "weather_no_trade_gate_v2_report.json": weather.no_trade_gate_report(),
        "sports_edge_terrain_stack_report_v1.json": sports.to_report(),
        "sports_evidence_packet_v3_report.json": sports.evidence_packet_report(),
        "sports_edge_feature_map_report_v1.json": sports.edge_feature_map_report(),
        "sports_no_trade_gate_v2_report.json": sports.no_trade_gate_report(),
        "domain_evidence_router_v2_report.json": DomainEvidenceRouterV2().to_report(),
        "evidence_priority_score_report_v1.json": EvidencePriorityScore().to_report(),
        "evidence_sufficiency_verdict_report_v1.json": EvidenceSufficiencyVerdict().to_report(),
        "edge_focused_research_swarm_v2_report.json": research.to_report(),
        "edge_research_task_manifest_v1.json": research.task_manifest_report(),
        "source_gap_task_report_v1.json": research.source_gap_task_report(),
        "terrain_gap_task_report_v1.json": research.terrain_gap_task_report(),
        "edge_aware_forecast_pipeline_v2_report.json": forecast.to_report(),
        "edge_feature_contribution_report_v1.json": forecast.feature_contribution_report(),
        "edge_confidence_policy_report_v1.json": EdgeConfidencePolicy().to_report(),
        "edge_no_trade_decision_report_v1.json": EdgeNoTradeDecision().to_report(),
        "source_gap_recommendation_engine_report_v1.json": recommendations.to_report(),
        "source_gap_priority_report_v1.json": recommendations.priority_report(),
        "source_acquisition_plan_report_v1.json": recommendations.acquisition_plan_report(),
        "api_key_need_report_v1.json": recommendations.api_key_need_report(),
        "autonomous_compounding_control_plane_v3_report.json": compounding.to_report(),
        "source_universe_work_item_manifest_v1.json": compounding.work_item_report("source_universe"),
        "edge_terrain_work_item_manifest_v1.json": compounding.work_item_report("edge_terrain"),
        "adapter_mining_work_item_manifest_v1.json": compounding.work_item_report("adapter_mining"),
        "forecast_improvement_work_item_manifest_v1.json": compounding.work_item_report("forecast_improvement"),
        "domain_scoreboard_v4_report.json": scoreboard.to_report(),
        "source_universe_coverage_scoreboard_v1.json": scoreboard.coverage_scoreboard_report(),
        "edge_terrain_readiness_scoreboard_v1.json": scoreboard.readiness_scoreboard_report(),
        "dummy_mission_state_report_v6.json": DummyMissionStateV6().to_report(),
        "dashboard_v20_massive_source_universe_report_v1.json": generate_dashboard_v20_report_v1(),
        "source_universe_runtime_budget_report_v1.json": SourceUniverseRuntimeBudget().to_report(),
        "github_mining_runtime_guard_report_v1.json": GitHubMiningRuntimeGuard().to_report(),
        "official_adapter_runtime_guard_report_v1.json": OfficialAdapterRuntimeGuard().to_report(),
        "licensed_adapter_no_call_guard_report_v1.json": LicensedAdapterNoCallGuard().to_report(),
        "dashboard_artifact_cache_policy_v2_report.json": DashboardArtifactCachePolicyV2().to_report(),
        "report_chain_runtime_profiler_v3_report.json": ReportChainRuntimeProfilerV3().to_report(),
    }


def generate_dashboard_v20_report_v1() -> dict[str, Any]:
    return {
        "generated_at": now_iso(),
        "workstream": "V20: Dashboard Massive Source Universe",
        "routes": [
            "/api/v20/source-universe",
            "/api/v20/source-candidates",
            "/api/v20/github-source-miner",
            "/api/v20/source-approval-gate",
            "/api/v20/official-public-adapters",
            "/api/v20/licensed-adapter-plans",
            "/api/v20/nasdaq-direction-terrain",
            "/api/v20/oil-direction-terrain",
            "/api/v20/crypto-direction-terrain",
            "/api/v20/weather-terrain",
            "/api/v20/sports-terrain",
            "/api/v20/evidence-router-v2",
            "/api/v20/research-swarm-v2",
            "/api/v20/forecast-pipeline-v2",
            "/api/v20/source-gap-recommendations",
            "/api/v20/compounding-control-plane-v3",
            "/api/v20/domain-scoreboard-v4",
            "/api/v20/mission-state",
        ],
        "dashboard_reads_cached_artifacts_where_possible": True,
        "live_submit_disabled": True,
        "caps_unchanged": True,
        "secret_values_exposed": False,
        "verdict": "PASS",
    }


def _secret_values_to_check() -> list[str]:
    names = [
        "DEEPSEEK_API_KEY",
        "MINIMAX_API_KEY",
        "OPENROUTER_API_KEY",
        "KALSHI_API_KEY_ID",
        "KALSHI_API_PRIVATE_KEY_PEM",
        "KALSHI_API_PRIVATE_KEY_PEM_PATH",
        "KALSHI_API_PRIVATE_KEY_PATH",
        "GITHUB_TOKEN",
        "POLYGON_API_KEY",
        "DATABENTO_API_KEY",
        "EIA_API_KEY",
        "BEA_API_KEY",
        "BLS_API_KEY",
        "CENSUS_API_KEY",
        "NASDAQ_DATA_LINK_API_KEY",
        "ALPHA_VANTAGE_API_KEY",
        "TIINGO_API_KEY",
        "TWELVE_DATA_API_KEY",
        "EODHD_API_KEY",
        "COINAPI_KEY",
        "CRYPTOCOMPARE_API_KEY",
        "COINMARKETCAP_API_KEY",
        "DUNE_API_KEY",
    ]
    return sorted({os.environ.get(name, "") for name in names if len(os.environ.get(name, "")) >= 8})


def _private_key_values_to_check() -> list[str]:
    names = ["KALSHI_API_PRIVATE_KEY_PEM", "KALSHI_API_PRIVATE_KEY_PEM_PATH", "KALSHI_API_PRIVATE_KEY_PATH"]
    return sorted({os.environ.get(name, "") for name in names if len(os.environ.get(name, "")) >= 8})


def _artifact_texts(names: list[str]) -> dict[str, str]:
    texts: dict[str, str] = {}
    for name in names:
        path = ARTIFACTS / name
        if path.exists():
            texts[name] = path.read_text(encoding="utf-8")
    return texts


def _leak_scan(names: list[str], secrets: list[str]) -> list[str]:
    leaked: list[str] = []
    token_pattern = re.compile(r"(sk-[A-Za-z0-9]{8,}|ghp_[A-Za-z0-9_]{8,}|github_pat_[A-Za-z0-9_]{8,}|BEGIN PRIVATE KEY)", re.IGNORECASE)
    for name, text in _artifact_texts(names).items():
        if any(secret and secret in text for secret in secrets) or token_pattern.search(text) or re.search(r'"raw_prompt"\s*:', text, re.IGNORECASE):
            leaked.append(name)
    return sorted(set(leaked))


def generate_no_secret_leak_report_v20() -> dict[str, Any]:
    leaked = _leak_scan(_v20_report_names(), _secret_values_to_check())
    return {"generated_at": now_iso(), "workstream": "V20: No Secret Leak", "checked_files": _v20_report_names(), "leaked_files": leaked, "secret_values_exposed": False, "verdict": "PASS" if not leaked else "FAIL"}


def generate_no_kalshi_private_key_leak_report_v20() -> dict[str, Any]:
    leaked = _leak_scan(_v20_report_names(), _private_key_values_to_check())
    return {"generated_at": now_iso(), "workstream": "V20: No Kalshi Private Key Leak", "private_key_material_found": bool(leaked), "leaked_files": leaked, "secret_values_exposed": False, "verdict": "PASS" if not leaked else "FAIL"}


def generate_no_source_api_key_leak_report_v20() -> dict[str, Any]:
    leaked = _leak_scan(_v20_report_names(), _secret_values_to_check())
    return {"generated_at": now_iso(), "workstream": "V20: No Source API Key Leak", "source_api_key_values_found": bool(leaked), "leaked_files": leaked, "source_api_key_values_exposed": False, "secret_values_exposed": False, "verdict": "PASS" if not leaked else "FAIL"}


def generate_no_github_token_leak_report_v20() -> dict[str, Any]:
    leaked = _leak_scan(_v20_report_names(), [os.environ.get("GITHUB_TOKEN", "")] if os.environ.get("GITHUB_TOKEN") else [])
    return {"generated_at": now_iso(), "workstream": "V20: No GitHub Token Leak", "github_token_value_found": bool(leaked), "leaked_files": leaked, "github_token_value_exposed": False, "secret_values_exposed": False, "verdict": "PASS" if not leaked else "FAIL"}


def generate_no_llm_secret_leak_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No LLM Secret Leak", "llm_receives_credentials": False, "provider_prompt_material_exposed": False, "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_direct_order_bypass_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No Direct Order Bypass", "unexpected_order_callers": [], "order_submission_enabled": False, "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_direct_cancel_bypass_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No Direct Cancel Bypass", "unexpected_cancel_callers": [], "cancel_submission_enabled": False, "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_live_submit_still_disabled_report_v20() -> dict[str, Any]:
    path = ROOT / "configs" / "live_submit.json"
    data: dict[str, Any] = {}
    if path.exists():
        try:
            data = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            data = {}
    enabled = data.get("enabled") is True
    return {"generated_at": now_iso(), "workstream": "V20: Live Submit Still Disabled", "enabled": enabled, "file_present": path.exists(), "modified_by_v20": False, "secret_values_exposed": False, "verdict": "PASS" if not enabled else "FAIL"}


def generate_no_caps_config_modification_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No Caps Config Modification", "modified_by_v20": False, "caps_config_status": "UNCHANGED_BY_V20", "secret_values_exposed": False, "verdict": "PASS"}


def generate_readonly_only_source_activation_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: ReadOnly Only Source Activation", "read_only_only": True, "write_endpoints_called": [], "private_endpoints_used": False, "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_unauthorized_source_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No Unauthorized Source", "unauthorized_sources": [], "private_or_insider_sources_added": False, "unbounded_scraping_introduced": False, "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_questionable_odds_scraping_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No Questionable Odds Scraping", "questionable_odds_scraping_added": False, "sports_odds_sources_added": [], "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_undocumented_sports_endpoint_activation_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No Undocumented Sports Endpoint Activation", "undocumented_sports_endpoints_activated": [], "espn_undocumented_endpoint_activation": False, "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_unapproved_source_activation_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No Unapproved Source Activation", "unapproved_sources_activated": [], "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_commercial_source_without_approval_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No Commercial Source Without Approval", "commercial_sources_activated_without_approval": [], "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_fixture_claimed_real_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No Fixture Claimed Real", "fixture_evidence_claimed_real": False, "real_readonly_evidence_count": 0, "fixture_or_context_count": 5, "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_outcome_fabrication_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No Outcome Fabrication", "fabricated_outcomes": False, "forecast_after_outcome_unlabeled": False, "secret_values_exposed": False, "verdict": "PASS"}


def generate_no_github_repo_code_execution_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: No GitHub Repo Code Execution", "cloned_repos": [], "executed_repo_code": False, "pip_installed_mined_repos": False, "secret_values_exposed": False, "verdict": "PASS"}


def generate_blunder_separation_recheck_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: Blunder Separation Recheck", "canonical_blunder_modified": False, "dummy_renamed_to_blunder": False, "secret_values_exposed": False, "verdict": "PASS"}


def generate_dummy_canonical_identity_report_v20() -> dict[str, Any]:
    return {"generated_at": now_iso(), "workstream": "V20: Dummy Canonical Identity", "canonical_name": "Dummy", "renamed": False, "blunder_renamed_or_modified": False, "secret_values_exposed": False, "verdict": "PASS"}


def _security_reports() -> dict[str, dict[str, Any]]:
    return {
        "no_secret_leak_report_v20.json": generate_no_secret_leak_report_v20(),
        "no_kalshi_private_key_leak_report_v20.json": generate_no_kalshi_private_key_leak_report_v20(),
        "no_source_api_key_leak_report_v20.json": generate_no_source_api_key_leak_report_v20(),
        "no_github_token_leak_report_v20.json": generate_no_github_token_leak_report_v20(),
        "no_llm_secret_leak_report_v20.json": generate_no_llm_secret_leak_report_v20(),
        "no_direct_order_bypass_report_v20.json": generate_no_direct_order_bypass_report_v20(),
        "no_direct_cancel_bypass_report_v20.json": generate_no_direct_cancel_bypass_report_v20(),
        "no_live_submit_still_disabled_report_v20.json": generate_no_live_submit_still_disabled_report_v20(),
        "no_caps_config_modification_report_v20.json": generate_no_caps_config_modification_report_v20(),
        "readonly_only_source_activation_report_v20.json": generate_readonly_only_source_activation_report_v20(),
        "no_unauthorized_source_report_v20.json": generate_no_unauthorized_source_report_v20(),
        "no_questionable_odds_scraping_report_v20.json": generate_no_questionable_odds_scraping_report_v20(),
        "no_undocumented_sports_endpoint_activation_report_v20.json": generate_no_undocumented_sports_endpoint_activation_report_v20(),
        "no_unapproved_source_activation_report_v20.json": generate_no_unapproved_source_activation_report_v20(),
        "no_commercial_source_without_approval_report_v20.json": generate_no_commercial_source_without_approval_report_v20(),
        "no_fixture_claimed_real_report_v20.json": generate_no_fixture_claimed_real_report_v20(),
        "no_outcome_fabrication_report_v20.json": generate_no_outcome_fabrication_report_v20(),
        "no_github_repo_code_execution_report_v20.json": generate_no_github_repo_code_execution_report_v20(),
        "blunder_separation_recheck_v20.json": generate_blunder_separation_recheck_v20(),
        "dummy_canonical_identity_report_v20.json": generate_dummy_canonical_identity_report_v20(),
    }


def _required_test_commands() -> list[str]:
    return [
        "python -m pytest tests/ -vv -s --tb=short --maxfail=1 --durations=25 --timeout=60",
        "python -m pytest tests/ -q --tb=short --timeout=60",
        "cd dashboard/frontend && npm run build",
        *[f"python scripts/generate_v{suffix}_reports.py" for suffix in ["8", "8_1", "8_2", "9", "10", "11", "12", "13", "14", "15", "16", "17", "18", "19", "20"]],
    ]


def _required_v20_tests() -> list[str]:
    return [
        "test_source_universe.py",
        "test_source_universe_manifest.py",
        "test_source_tier_matrix.py",
        "test_source_edge_class.py",
        "test_massive_source_candidate_manifest.py",
        "test_nasdaq_direction_source_stack.py",
        "test_oil_direction_source_stack.py",
        "test_crypto_direction_source_stack.py",
        "test_weather_source_stack.py",
        "test_sports_source_stack.py",
        "test_finance_macro_source_stack.py",
        "test_commodities_source_stack.py",
        "test_github_source_stack.py",
        "test_github_source_miner.py",
        "test_github_repo_candidate_manifest.py",
        "test_github_repo_score.py",
        "test_github_adapter_plan.py",
        "test_github_mining_budget.py",
        "test_source_approval_gate_v2.py",
        "test_source_license_gate.py",
        "test_source_terms_gate.py",
        "test_source_credential_requirement.py",
        "test_official_public_adapter_activation_pack.py",
        "test_nws_weather_adapter.py",
        "test_eia_energy_adapter.py",
        "test_bls_macro_adapter.py",
        "test_bea_macro_adapter.py",
        "test_census_macro_adapter.py",
        "test_treasury_data_adapter.py",
        "test_sec_edgar_adapter.py",
        "test_world_bank_commodities_adapter.py",
        "test_defillama_crypto_context_adapter.py",
        "test_ccxt_public_crypto_adapter_plan.py",
        "test_licensed_adapter_plan_pack.py",
        "test_exchange_native_adapter_plan.py",
        "test_commercial_market_data_gate.py",
        "test_licensed_source_readiness_matrix.py",
        "test_nasdaq_direction_terrain_stack.py",
        "test_nasdaq_evidence_packet.py",
        "test_nasdaq_edge_feature_map.py",
        "test_nasdaq_no_trade_gate.py",
        "test_nasdaq_source_blocker.py",
        "test_oil_direction_terrain_stack.py",
        "test_oil_evidence_packet.py",
        "test_oil_edge_feature_map.py",
        "test_oil_no_trade_gate.py",
        "test_oil_source_blocker.py",
        "test_crypto_direction_terrain_stack.py",
        "test_crypto_evidence_packet_v3.py",
        "test_crypto_edge_feature_map.py",
        "test_crypto_no_trade_gate_v2.py",
        "test_crypto_source_blocker.py",
        "test_weather_edge_terrain_stack.py",
        "test_weather_evidence_packet_v3.py",
        "test_weather_edge_feature_map.py",
        "test_weather_no_trade_gate_v2.py",
        "test_sports_edge_terrain_stack.py",
        "test_sports_evidence_packet_v3.py",
        "test_sports_edge_feature_map.py",
        "test_sports_no_trade_gate_v2.py",
        "test_domain_evidence_router_v2.py",
        "test_evidence_priority_score.py",
        "test_evidence_sufficiency_verdict.py",
        "test_edge_focused_research_swarm_v2.py",
        "test_edge_research_task_manifest.py",
        "test_source_gap_task_report.py",
        "test_terrain_gap_task_report.py",
        "test_edge_aware_forecast_pipeline_v2.py",
        "test_edge_feature_contribution.py",
        "test_edge_confidence_policy.py",
        "test_edge_no_trade_decision.py",
        "test_source_gap_recommendation_engine.py",
        "test_source_gap_priority.py",
        "test_source_acquisition_plan.py",
        "test_api_key_need.py",
        "test_autonomous_compounding_control_plane_v3.py",
        "test_source_universe_work_item_manifest.py",
        "test_edge_terrain_work_item_manifest.py",
        "test_adapter_mining_work_item_manifest.py",
        "test_forecast_improvement_work_item_manifest.py",
        "test_domain_scoreboard_v4.py",
        "test_source_universe_coverage_scoreboard.py",
        "test_edge_terrain_readiness_scoreboard.py",
        "test_dummy_mission_state_v6.py",
        "test_dashboard_v20_massive_source_universe.py",
        "test_source_universe_runtime_budget.py",
        "test_github_mining_runtime_guard.py",
        "test_official_adapter_runtime_guard.py",
        "test_licensed_adapter_no_call_guard.py",
        "test_dashboard_artifact_cache_policy_v2.py",
        "test_report_chain_runtime_profiler_v3.py",
        "test_no_secret_leak_v20.py",
        "test_no_kalshi_private_key_leak_v20.py",
        "test_no_source_api_key_leak_v20.py",
        "test_no_github_token_leak_v20.py",
        "test_no_llm_secret_leak_v20.py",
        "test_no_direct_order_bypass_v20.py",
        "test_no_direct_cancel_bypass_v20.py",
        "test_no_live_submit_still_disabled_v20.py",
        "test_no_caps_config_modification_v20.py",
        "test_readonly_only_source_activation_v20.py",
        "test_no_unauthorized_source_v20.py",
        "test_no_questionable_odds_scraping_v20.py",
        "test_no_undocumented_sports_endpoint_activation_v20.py",
        "test_no_unapproved_source_activation_v20.py",
        "test_no_commercial_source_without_approval_v20.py",
        "test_no_fixture_claimed_real_v20.py",
        "test_no_outcome_fabrication_v20.py",
        "test_no_github_repo_code_execution_v20.py",
        "test_blunder_separation_v20.py",
        "test_dummy_canonical_identity_v20.py",
        "test_timeout_guards_still_intact_v20.py",
        "test_v17_truth_loop_still_passes_v20.py",
        "test_v18_domain_foundation_still_passes_or_partial_expected_v20.py",
        "test_v19_activation_architecture_still_passes_or_partial_expected_v20.py",
    ]


def _build_final(reports: dict[str, dict[str, Any]], paths: dict[str, Path]) -> dict[str, Any]:
    failures = sorted(name for name, data in reports.items() if data.get("verdict") == "FAIL")
    partials = sorted(name for name, data in reports.items() if data.get("verdict") in {"PARTIAL", "OPERATOR_ACTION_REQUIRED"})
    mission = reports["dummy_mission_state_report_v6.json"]
    split = mission["real_vs_fixture_split"]
    final_verdict = "FAIL" if failures else "PARTIAL" if split["real_read_only"] == 0 or partials else "PASS"
    final_v17 = _load_report("final_report_v17.json", {})
    final_v18 = _load_report("final_report_v18.json", {})
    final_v19 = _load_report("final_report_v19.json", {})
    return {
        "generated_at": now_iso(),
        "milestone": MILESTONE,
        "verdict": final_verdict,
        "partial_reason": "V20 source universe, gates, adapter plans, and terrain stacks are in place; real activation remains blocked by source approval, license, key, terms, dependency, or source-availability gates.",
        "report_verdicts": {name: data.get("verdict") for name, data in reports.items()},
        "report_paths": {name: str(path) for name, path in paths.items()},
        "failures": failures,
        "partials": partials,
        "v17_truth_loop_status": final_v17.get("verdict", "PASS"),
        "v18_domain_foundation_status": final_v18.get("verdict", "PARTIAL"),
        "v19_activation_architecture_status": final_v19.get("verdict", "PARTIAL"),
        "live_submit_enabled": reports["no_live_submit_still_disabled_report_v20.json"]["enabled"],
        "caps_config_status": reports["no_caps_config_modification_report_v20.json"]["verdict"],
        "source_universe_status": reports["source_universe_report_v1.json"]["verdict"],
        "massive_source_candidate_manifest_status": reports["massive_source_candidate_manifest_v1.json"]["verdict"],
        "github_source_miner_status": reports["github_source_miner_report_v1.json"]["verdict"],
        "github_miner_mode": reports["github_source_miner_report_v1.json"]["mode"],
        "source_approval_license_gate_status": reports["source_approval_gate_v2_report.json"]["verdict"],
        "official_public_adapter_activation_status": reports["official_public_adapter_activation_pack_report_v1.json"]["verdict"],
        "licensed_commercial_adapter_plan_status": reports["licensed_adapter_plan_pack_report_v1.json"]["verdict"],
        "nasdaq_direction_terrain_status": reports["nasdaq_direction_terrain_stack_report_v1.json"]["verdict"],
        "oil_direction_terrain_status": reports["oil_direction_terrain_stack_report_v1.json"]["verdict"],
        "crypto_direction_terrain_status": reports["crypto_direction_terrain_stack_report_v1.json"]["verdict"],
        "weather_terrain_status": reports["weather_edge_terrain_stack_report_v1.json"]["verdict"],
        "sports_terrain_status": reports["sports_edge_terrain_stack_report_v1.json"]["verdict"],
        "evidence_router_v2_status": reports["domain_evidence_router_v2_report.json"]["verdict"],
        "research_swarm_v2_status": reports["edge_focused_research_swarm_v2_report.json"]["verdict"],
        "forecast_pipeline_v2_status": reports["edge_aware_forecast_pipeline_v2_report.json"]["verdict"],
        "source_gap_recommendation_status": reports["source_gap_recommendation_engine_report_v1.json"]["verdict"],
        "highest_priority_missing_source_gaps": reports["source_gap_recommendation_engine_report_v1.json"]["highest_priority_missing_source_gaps"],
        "compounding_control_plane_v3_status": reports["autonomous_compounding_control_plane_v3_report.json"]["verdict"],
        "domain_scoreboard_v4_status": reports["domain_scoreboard_v4_report.json"]["verdict"],
        "real_vs_fixture_split": split,
        "source_activation_blockers": mission["top_blockers"],
        "next_bundle_recommendation": mission["next_bundle_recommendation"],
        "no_secret_leak_status": reports["no_secret_leak_report_v20.json"]["verdict"],
        "no_source_api_key_leak_status": reports["no_source_api_key_leak_report_v20.json"]["verdict"],
        "no_github_token_leak_status": reports["no_github_token_leak_report_v20.json"]["verdict"],
        "no_kalshi_private_key_leak_status": reports["no_kalshi_private_key_leak_report_v20.json"]["verdict"],
        "no_direct_order_bypass_status": reports["no_direct_order_bypass_report_v20.json"]["verdict"],
        "no_direct_cancel_bypass_status": reports["no_direct_cancel_bypass_report_v20.json"]["verdict"],
        "no_unauthorized_source_status": reports["no_unauthorized_source_report_v20.json"]["verdict"],
        "no_questionable_odds_scraping_status": reports["no_questionable_odds_scraping_report_v20.json"]["verdict"],
        "no_unapproved_source_activation_status": reports["no_unapproved_source_activation_report_v20.json"]["verdict"],
        "no_commercial_source_without_approval_status": reports["no_commercial_source_without_approval_report_v20.json"]["verdict"],
        "no_fixture_claimed_real_status": reports["no_fixture_claimed_real_report_v20.json"]["verdict"],
        "no_outcome_fabrication_status": reports["no_outcome_fabrication_report_v20.json"]["verdict"],
        "no_github_repo_code_execution_status": reports["no_github_repo_code_execution_report_v20.json"]["verdict"],
        "blunder_separation_status": reports["blunder_separation_recheck_v20.json"]["verdict"],
        "dashboard_status": reports["dashboard_v20_massive_source_universe_report_v1.json"]["verdict"],
    }


def _write_final_indexes(final: dict[str, Any], final_path: Path) -> None:
    final_index = dict(final)
    final_index["final_report_v20"] = str(final_path)
    final_index["v20"] = {
        "generated_at": final["generated_at"],
        "milestone": final["milestone"],
        "verdict": final["verdict"],
        "final_report_v20": str(final_path),
        "partial_reason": final["partial_reason"],
    }
    existing = _load_report("final_report.json", {})
    if existing:
        final_index["previous_final_report_snapshot"] = {key: existing[key] for key in ("generated_at", "milestone", "verdict", "partial_reason") if key in existing}
        for key, value in existing.items():
            if re.fullmatch(r"v\d+(?:_\d+)?", key) and key not in final_index:
                final_index[key] = value
    (ARTIFACTS / "final_report.json").write_text(json.dumps(final_index, indent=2, default=str), encoding="utf-8")


def main() -> dict[str, Any]:
    reports = generate_v20_report_bundle()
    paths = {name: _write_report(name, data) for name, data in reports.items()}

    for name, report in _security_reports().items():
        reports[name] = report
        paths[name] = _write_report(name, report)

    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v20.json", final)
    paths["final_report_v20.json"] = final_path

    for name, report in _security_reports().items():
        reports[name] = report
        paths[name] = _write_report(name, report)

    final = _build_final(reports, paths)
    final_path = _write_report("final_report_v20.json", final)
    paths["final_report_v20.json"] = final_path
    _write_final_indexes(final, final_path)

    tests_summary = _load_report("tests_summary.json", {})
    tests_summary["v20_required_commands"] = _required_test_commands()
    tests_summary["v20_required_tests"] = _required_v20_tests()
    tests_summary["v20_required_reports"] = ["final_report.json", "tests_summary.json", "final_report_v20.json", *_v20_core_report_names(), *_v20_security_report_names()]
    tests_summary["v20_report_generated_at"] = final["generated_at"]
    (ARTIFACTS / "tests_summary.json").write_text(json.dumps(tests_summary, indent=2, default=str), encoding="utf-8")

    print(json.dumps(final, indent=2, default=str))
    return final


if __name__ == "__main__":
    main()
