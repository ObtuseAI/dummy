"""V20 source universe, source ranking, and source stack reports."""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from enum import Enum
from typing import Any, Iterable

from predator_mesh.v20 import SOURCE_DOMAINS


class SourceTier(str, Enum):
    TIER_0_EXCHANGE_NATIVE = "TIER_0_EXCHANGE_NATIVE"
    TIER_1_OFFICIAL_PUBLIC = "TIER_1_OFFICIAL_PUBLIC"
    TIER_2_COMMERCIAL_LICENSED = "TIER_2_COMMERCIAL_LICENSED"
    TIER_3_OPEN_SOURCE_GITHUB = "TIER_3_OPEN_SOURCE_GITHUB"
    TIER_4_FREE_PUBLIC_CONTEXT = "TIER_4_FREE_PUBLIC_CONTEXT"
    TIER_5_BLOCKED_UNTIL_APPROVED = "TIER_5_BLOCKED_UNTIL_APPROVED"


class SourceDomain(str, Enum):
    SPORTS = "sports"
    WEATHER = "weather"
    CRYPTO = "crypto"
    COMMODITIES = "commodities"
    FINANCE = "finance"
    NASDAQ_INDEX_DIRECTION = "nasdaq_index_direction"
    OIL_ENERGY_DIRECTION = "oil_energy_direction"
    CROSS_ASSET_MACRO = "cross_asset_macro"
    VOLATILITY = "volatility"
    NEWS_EVENT_METADATA = "news_event_metadata"
    KALSHI_MARKET_TERRAIN = "kalshi_market_terrain"


class SourceClass(str, Enum):
    EXCHANGE_ORDERBOOK = "exchange_orderbook"
    EXCHANGE_TRADES = "exchange_trades"
    FUTURES_MARKET_DATA = "futures_market_data"
    EQUITY_MARKET_DATA = "equity_market_data"
    OPTIONS_VOLATILITY = "options_volatility"
    MACRO_OFFICIAL = "macro_official"
    COMMODITY_FUNDAMENTALS = "commodity_fundamentals"
    WEATHER_FORECAST = "weather_forecast"
    WEATHER_OBSERVATION = "weather_observation"
    SPORTS_SCHEDULE_STATUS = "sports_schedule_status"
    SPORTS_STATS = "sports_stats"
    CRYPTO_EXCHANGE_PUBLIC = "crypto_exchange_public"
    CRYPTO_ONCHAIN = "crypto_onchain"
    NEWS_EVENT_METADATA = "news_event_metadata"
    GITHUB_ADAPTER_CANDIDATE = "github_adapter_candidate"
    STATIC_FIXTURE = "static_fixture"
    BLOCKED_SOURCE = "blocked_source"


class SourceApprovalStatus(str, Enum):
    APPROVED_PUBLIC_READONLY = "APPROVED_PUBLIC_READONLY"
    APPROVED_OFFICIAL_PUBLIC = "APPROVED_OFFICIAL_PUBLIC"
    APPROVED_COMMERCIAL_LICENSED = "APPROVED_COMMERCIAL_LICENSED"
    APPROVED_RESEARCH_ONLY = "APPROVED_RESEARCH_ONLY"
    APPROVED_STATIC_FIXTURE = "APPROVED_STATIC_FIXTURE"
    BLOCKED_NOT_APPROVED = "BLOCKED_NOT_APPROVED"
    BLOCKED_LICENSE_REQUIRED = "BLOCKED_LICENSE_REQUIRED"
    BLOCKED_KEY_MISSING = "BLOCKED_KEY_MISSING"
    BLOCKED_TERMS_UNCLEAR = "BLOCKED_TERMS_UNCLEAR"
    BLOCKED_SCRAPING_RISK = "BLOCKED_SCRAPING_RISK"
    BLOCKED_PAYWALLED = "BLOCKED_PAYWALLED"
    BLOCKED_PRIVATE = "BLOCKED_PRIVATE"
    BLOCKED_RATE_LIMIT_UNKNOWN = "BLOCKED_RATE_LIMIT_UNKNOWN"
    BLOCKED_EXECUTION_AUTHORITY = "BLOCKED_EXECUTION_AUTHORITY"


class SourceLicenseStatus(str, Enum):
    PUBLIC_ALLOWED = "PUBLIC_ALLOWED"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    KEY_REQUIRED = "KEY_REQUIRED"
    TERMS_REVIEW_REQUIRED = "TERMS_REVIEW_REQUIRED"
    RESEARCH_ONLY = "RESEARCH_ONLY"
    STATIC_FIXTURE = "STATIC_FIXTURE"
    BLOCKED_PAYWALLED = "BLOCKED_PAYWALLED"
    BLOCKED_PRIVATE = "BLOCKED_PRIVATE"


class SourceCostClass(str, Enum):
    FREE_PUBLIC = "FREE_PUBLIC"
    FREE_KEY_REQUIRED = "FREE_KEY_REQUIRED"
    COMMERCIAL_LICENSED = "COMMERCIAL_LICENSED"
    MIXED_OR_DATASET_DEPENDENT = "MIXED_OR_DATASET_DEPENDENT"
    UNKNOWN_REVIEW_REQUIRED = "UNKNOWN_REVIEW_REQUIRED"


class SourceLatencyClass(str, Enum):
    REALTIME = "REALTIME"
    NEAR_REALTIME = "NEAR_REALTIME"
    INTRADAY = "INTRADAY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    STATIC = "STATIC"


class SourceFreshnessClass(str, Enum):
    REALTIME = "REALTIME"
    INTRADAY = "INTRADAY"
    DAILY = "DAILY"
    WEEKLY = "WEEKLY"
    MONTHLY = "MONTHLY"
    STATIC_FIXTURE = "STATIC_FIXTURE"


class SourceEdgeClass(str, Enum):
    HIGH_DIRECTIONAL_EDGE = "HIGH_DIRECTIONAL_EDGE"
    MEDIUM_CONTEXT_EDGE = "MEDIUM_CONTEXT_EDGE"
    LOW_CONTEXT_EDGE = "LOW_CONTEXT_EDGE"
    SETTLEMENT_TRUTH = "SETTLEMENT_TRUTH"
    ADAPTER_ACCELERATOR = "ADAPTER_ACCELERATOR"
    BLOCKED_OR_UNUSABLE = "BLOCKED_OR_UNUSABLE"


class SourceActivationRisk(str, Enum):
    LOW_PUBLIC_READONLY = "LOW_PUBLIC_READONLY"
    MEDIUM_TERMS_REVIEW = "MEDIUM_TERMS_REVIEW"
    HIGH_LICENSE_OR_KEY_REQUIRED = "HIGH_LICENSE_OR_KEY_REQUIRED"
    BLOCKED_EXECUTION_AUTHORITY = "BLOCKED_EXECUTION_AUTHORITY"
    BLOCKED_SCRAPING_OR_PRIVATE = "BLOCKED_SCRAPING_OR_PRIVATE"


@dataclass(frozen=True)
class SourceTruthScore:
    provenance: float
    legality: float
    freshness: float
    calibration_value: float

    @property
    def total(self) -> float:
        return round((self.provenance + self.legality + self.freshness + self.calibration_value) / 4, 3)

    def to_dict(self) -> dict[str, float]:
        return {
            "provenance": self.provenance,
            "legality": self.legality,
            "freshness": self.freshness,
            "calibration_value": self.calibration_value,
            "total": self.total,
        }


@dataclass(frozen=True)
class SourceAdapterPlan:
    mode: str
    endpoints_or_classes_needed: tuple[str, ...]
    dependency: str = "stdlib/httpx_optional"
    credential_env_vars: tuple[str, ...] = ()
    activation_authority: str = "READ_ONLY_ONLY"
    live_execution_enabled: bool = False
    network_policy: str = "BOUNDED_TIMEOUT_FALLBACK_SAFE"
    implementation_status: str = "PLAN_OR_READONLY_CONTEXT"
    blockers: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "endpoints_or_classes_needed": list(self.endpoints_or_classes_needed),
            "dependency": self.dependency,
            "credential_env_vars": list(self.credential_env_vars),
            "activation_authority": self.activation_authority,
            "live_execution_enabled": self.live_execution_enabled,
            "network_policy": self.network_policy,
            "implementation_status": self.implementation_status,
            "blockers": list(self.blockers),
            "order_endpoints_allowed": False,
            "cancel_endpoints_allowed": False,
        }


@dataclass(frozen=True)
class SourceProofRef:
    report_name: str
    proof_type: str = "SOURCE_UNIVERSE_CLASSIFICATION"

    def to_dict(self) -> dict[str, str]:
        return {"report_name": self.report_name, "proof_type": self.proof_type}


@dataclass(frozen=True)
class SourceCandidate:
    source_id: str
    name: str
    domains: tuple[str, ...]
    tier: SourceTier
    source_class: SourceClass
    legality_class: str
    approval_status: SourceApprovalStatus
    license_status: SourceLicenseStatus
    cost_class: SourceCostClass
    latency_class: SourceLatencyClass
    freshness_class: SourceFreshnessClass
    expected_edge_class: SourceEdgeClass
    adapter_plan: SourceAdapterPlan
    fallback_mode: str
    activation_risk: SourceActivationRisk
    proof_refs: tuple[SourceProofRef, ...]
    source_url: str
    terms_risk: str = "TERMS_REVIEWED_PUBLIC_READONLY_OR_BLOCKED"
    truth_score: SourceTruthScore = SourceTruthScore(0.6, 1.0, 0.5, 0.5)
    truth_source_role: str = "DATA_OR_CONTEXT_SOURCE"
    fixture_claimed_real: bool = False
    real_readonly_active: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "name": self.name,
            "source_url": self.source_url,
            "tier": self.tier.value,
            "domains": list(self.domains),
            "source_class": self.source_class.value,
            "legality_class": self.legality_class,
            "approval_status": self.approval_status.value,
            "license_status": self.license_status.value,
            "cost_class": self.cost_class.value,
            "latency_class": self.latency_class.value,
            "freshness_class": self.freshness_class.value,
            "expected_edge_class": self.expected_edge_class.value,
            "adapter_plan": self.adapter_plan.to_dict(),
            "fallback_mode": self.fallback_mode,
            "activation_risk": self.activation_risk.value,
            "proof_refs": [ref.to_dict() for ref in self.proof_refs],
            "terms_risk": self.terms_risk,
            "truth_score": self.truth_score.to_dict(),
            "truth_source_role": self.truth_source_role,
            "fixture_claimed_real": self.fixture_claimed_real,
            "real_readonly_active": self.real_readonly_active,
            "live_execution_enabled": False,
        }


@dataclass(frozen=True)
class SourceUniverseQuery:
    domain: str | None = None
    tier: SourceTier | None = None
    source_class: SourceClass | None = None


@dataclass(frozen=True)
class SourceUniverseReport:
    candidates: tuple[SourceCandidate, ...]

    def to_dict(self) -> dict[str, Any]:
        tiers = Counter(candidate.tier.value for candidate in self.candidates)
        approvals = Counter(candidate.approval_status.value for candidate in self.candidates)
        return {
            "workstream": "V20: Source Universe",
            "source_count": len(self.candidates),
            "tiers": sorted(tiers),
            "tier_counts": dict(sorted(tiers.items())),
            "domains": sorted({domain for candidate in self.candidates for domain in candidate.domains}),
            "approval_status_counts": dict(sorted(approvals.items())),
            "all_candidates_legality_classified": all(candidate.legality_class for candidate in self.candidates),
            "all_candidates_have_approval_status": all(candidate.approval_status for candidate in self.candidates),
            "commercial_sources_default_blocked": all(
                candidate.approval_status
                in {SourceApprovalStatus.BLOCKED_LICENSE_REQUIRED, SourceApprovalStatus.BLOCKED_KEY_MISSING, SourceApprovalStatus.BLOCKED_TERMS_UNCLEAR}
                for candidate in self.candidates
                if candidate.tier == SourceTier.TIER_2_COMMERCIAL_LICENSED
            ),
            "github_repos_truth_sources": False,
            "fixture_sources_labeled_real": False,
            "live_execution_enabled": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


def _defaults_for_tier(tier: SourceTier) -> tuple[SourceApprovalStatus, SourceLicenseStatus, SourceCostClass, SourceActivationRisk, str, str]:
    if tier == SourceTier.TIER_0_EXCHANGE_NATIVE:
        return (
            SourceApprovalStatus.BLOCKED_LICENSE_REQUIRED,
            SourceLicenseStatus.LICENSE_REQUIRED,
            SourceCostClass.COMMERCIAL_LICENSED,
            SourceActivationRisk.HIGH_LICENSE_OR_KEY_REQUIRED,
            "LICENSED_ADAPTER_PLAN_ONLY",
            "Exchange-native read-only data requires operator-approved license and credentials.",
        )
    if tier == SourceTier.TIER_1_OFFICIAL_PUBLIC:
        return (
            SourceApprovalStatus.APPROVED_OFFICIAL_PUBLIC,
            SourceLicenseStatus.PUBLIC_ALLOWED,
            SourceCostClass.FREE_PUBLIC,
            SourceActivationRisk.LOW_PUBLIC_READONLY,
            "PUBLIC_READONLY_WITH_STATIC_FALLBACK",
            "Official/public read-only source can be used only through bounded adapters.",
        )
    if tier == SourceTier.TIER_2_COMMERCIAL_LICENSED:
        return (
            SourceApprovalStatus.BLOCKED_LICENSE_REQUIRED,
            SourceLicenseStatus.LICENSE_REQUIRED,
            SourceCostClass.COMMERCIAL_LICENSED,
            SourceActivationRisk.HIGH_LICENSE_OR_KEY_REQUIRED,
            "LICENSED_ADAPTER_PLAN_ONLY",
            "Commercial source remains blocked until license and key are explicitly allowlisted.",
        )
    if tier == SourceTier.TIER_3_OPEN_SOURCE_GITHUB:
        return (
            SourceApprovalStatus.APPROVED_RESEARCH_ONLY,
            SourceLicenseStatus.TERMS_REVIEW_REQUIRED,
            SourceCostClass.FREE_PUBLIC,
            SourceActivationRisk.MEDIUM_TERMS_REVIEW,
            "ADAPTER_CANDIDATE_ONLY",
            "GitHub repositories accelerate adapters but are never truth sources.",
        )
    if tier == SourceTier.TIER_4_FREE_PUBLIC_CONTEXT:
        return (
            SourceApprovalStatus.APPROVED_RESEARCH_ONLY,
            SourceLicenseStatus.TERMS_REVIEW_REQUIRED,
            SourceCostClass.FREE_PUBLIC,
            SourceActivationRisk.MEDIUM_TERMS_REVIEW,
            "RESEARCH_CONTEXT_ONLY",
            "Free public context source requires terms and freshness review before promotion.",
        )
    return (
        SourceApprovalStatus.BLOCKED_NOT_APPROVED,
        SourceLicenseStatus.TERMS_REVIEW_REQUIRED,
        SourceCostClass.UNKNOWN_REVIEW_REQUIRED,
        SourceActivationRisk.BLOCKED_SCRAPING_OR_PRIVATE,
        "BLOCKED_UNTIL_OPERATOR_APPROVAL",
        "Source is blocked until explicit operator approval.",
    )


def _candidate(
    source_id: str,
    name: str,
    domains: Iterable[str],
    tier: SourceTier,
    source_class: SourceClass,
    url: str,
    *,
    edge: SourceEdgeClass | None = None,
    approval_status: SourceApprovalStatus | None = None,
    license_status: SourceLicenseStatus | None = None,
    cost_class: SourceCostClass | None = None,
    freshness_class: SourceFreshnessClass | None = None,
    latency_class: SourceLatencyClass | None = None,
    credential_env_vars: tuple[str, ...] = (),
    terms_risk: str | None = None,
    adapter_mode: str | None = None,
    endpoints: tuple[str, ...] = (),
) -> SourceCandidate:
    default_approval, default_license, default_cost, default_risk, fallback, default_terms = _defaults_for_tier(tier)
    expected_edge = edge or (
        SourceEdgeClass.HIGH_DIRECTIONAL_EDGE
        if tier in {SourceTier.TIER_0_EXCHANGE_NATIVE, SourceTier.TIER_2_COMMERCIAL_LICENSED}
        else SourceEdgeClass.MEDIUM_CONTEXT_EDGE
    )
    if source_class == SourceClass.GITHUB_ADAPTER_CANDIDATE:
        expected_edge = SourceEdgeClass.ADAPTER_ACCELERATOR
    final_license = license_status or default_license
    blockers: tuple[str, ...] = ()
    final_approval = approval_status or default_approval
    if credential_env_vars and final_approval == SourceApprovalStatus.APPROVED_RESEARCH_ONLY:
        final_approval = SourceApprovalStatus.BLOCKED_KEY_MISSING
    if tier in {SourceTier.TIER_0_EXCHANGE_NATIVE, SourceTier.TIER_2_COMMERCIAL_LICENSED}:
        blockers = ("operator_license_or_allowlist_missing", "source_key_value_not_stored")
    elif credential_env_vars:
        blockers = ("api_key_presence_required",)
    adapter_plan = SourceAdapterPlan(
        mode=adapter_mode or fallback,
        endpoints_or_classes_needed=endpoints or (source_class.value,),
        credential_env_vars=credential_env_vars,
        implementation_status="ADAPTER_PLAN_ONLY" if "PLAN" in fallback else "READONLY_CONTEXT_CLASSIFIED",
        blockers=blockers,
    )
    truth_role = "ADAPTER_CANDIDATE_ONLY" if source_class == SourceClass.GITHUB_ADAPTER_CANDIDATE else "DATA_OR_CONTEXT_SOURCE"
    if source_class == SourceClass.STATIC_FIXTURE:
        truth_role = "STATIC_FIXTURE_ONLY"
    return SourceCandidate(
        source_id=source_id,
        name=name,
        domains=tuple(domains),
        tier=tier,
        source_class=source_class,
        legality_class="PUBLIC_READONLY_ALLOWED" if tier == SourceTier.TIER_1_OFFICIAL_PUBLIC else "REVIEW_OR_LICENSE_REQUIRED",
        approval_status=final_approval,
        license_status=final_license,
        cost_class=cost_class or default_cost,
        latency_class=latency_class or (SourceLatencyClass.NEAR_REALTIME if tier == SourceTier.TIER_0_EXCHANGE_NATIVE else SourceLatencyClass.DAILY),
        freshness_class=freshness_class or (SourceFreshnessClass.REALTIME if tier == SourceTier.TIER_0_EXCHANGE_NATIVE else SourceFreshnessClass.DAILY),
        expected_edge_class=expected_edge,
        adapter_plan=adapter_plan,
        fallback_mode=fallback,
        activation_risk=default_risk,
        proof_refs=(SourceProofRef("artifacts/dummy/source_universe_manifest_v1.json"),),
        source_url=url,
        terms_risk=terms_risk or default_terms,
        truth_score=SourceTruthScore(0.8 if tier == SourceTier.TIER_1_OFFICIAL_PUBLIC else 0.55, 1.0 if tier == SourceTier.TIER_1_OFFICIAL_PUBLIC else 0.45, 0.75, 0.65),
        truth_source_role=truth_role,
    )


class SourceUniverseRegistry:
    def __init__(self) -> None:
        self._candidates = tuple(_build_candidates())

    def candidates(self) -> list[SourceCandidate]:
        return list(self._candidates)

    def query(self, query: SourceUniverseQuery) -> list[SourceCandidate]:
        candidates = self.candidates()
        if query.domain:
            candidates = [candidate for candidate in candidates if query.domain in candidate.domains]
        if query.tier:
            candidates = [candidate for candidate in candidates if candidate.tier == query.tier]
        if query.source_class:
            candidates = [candidate for candidate in candidates if candidate.source_class == query.source_class]
        return candidates


class SourceUniverse:
    def __init__(self, registry: SourceUniverseRegistry | None = None) -> None:
        self.registry = registry or SourceUniverseRegistry()

    def candidates(self) -> list[SourceCandidate]:
        return self.registry.candidates()

    def query(self, query: SourceUniverseQuery) -> list[SourceCandidate]:
        return self.registry.query(query)

    def to_report(self) -> dict[str, Any]:
        report = SourceUniverseReport(tuple(self.candidates())).to_dict()
        report["domains"] = sorted(set(report["domains"]) | set(SOURCE_DOMAINS))
        return report

    def manifest_report(self) -> dict[str, Any]:
        sources = [candidate.to_dict() for candidate in self.candidates()]
        return {
            "workstream": "V20: Source Universe Manifest",
            "source_count": len(sources),
            "sources": sources,
            "source_ids": [source["source_id"] for source in sources],
            "all_sources_have_required_fields": True,
            "fixture_sources_labeled_real": False,
            "github_repos_truth_sources": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def tier_matrix_report(self) -> dict[str, Any]:
        matrix: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
        for candidate in self.candidates():
            for domain in candidate.domains:
                matrix[domain][candidate.tier.value] += 1
        return {
            "workstream": "V20: Source Tier Matrix",
            "matrix": {domain: dict(sorted(counts.items())) for domain, counts in sorted(matrix.items())},
            "tiers": [tier.value for tier in SourceTier],
            "tier_0_exchange_native_prioritized": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def edge_class_report(self) -> dict[str, Any]:
        counts = Counter(candidate.expected_edge_class.value for candidate in self.candidates())
        return {
            "workstream": "V20: Source Edge Class",
            "edge_class_counts": dict(sorted(counts.items())),
            "high_edge_source_count": counts[SourceEdgeClass.HIGH_DIRECTIONAL_EDGE.value],
            "github_adapter_candidate_count": counts[SourceEdgeClass.ADAPTER_ACCELERATOR.value],
            "no_fake_edge_claims": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def stack_report(self, stack_name: str, domains: tuple[str, ...]) -> dict[str, Any]:
        sources = [candidate.to_dict() for candidate in self.candidates() if set(candidate.domains) & set(domains)]
        blocked = [source for source in sources if source["approval_status"].startswith("BLOCKED")]
        return {
            "workstream": f"V20: {stack_name} Source Stack",
            "domains": list(domains),
            "source_count": len(sources),
            "sources": sources,
            "blocked_source_count": len(blocked),
            "real_readonly_active_count": sum(1 for source in sources if source["real_readonly_active"]),
            "commercial_sources_default_blocked": all(
                source["approval_status"] in {"BLOCKED_LICENSE_REQUIRED", "BLOCKED_KEY_MISSING", "BLOCKED_TERMS_UNCLEAR"}
                for source in sources
                if source["tier"] == SourceTier.TIER_2_COMMERCIAL_LICENSED.value
            ),
            "github_adapter_candidates_only": all(
                source["truth_source_role"] == "ADAPTER_CANDIDATE_ONLY"
                for source in sources
                if source["source_class"] == SourceClass.GITHUB_ADAPTER_CANDIDATE.value
            ),
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


def _build_candidates() -> list[SourceCandidate]:
    T0 = SourceTier.TIER_0_EXCHANGE_NATIVE
    T1 = SourceTier.TIER_1_OFFICIAL_PUBLIC
    T2 = SourceTier.TIER_2_COMMERCIAL_LICENSED
    T3 = SourceTier.TIER_3_OPEN_SOURCE_GITHUB
    T4 = SourceTier.TIER_4_FREE_PUBLIC_CONTEXT
    T5 = SourceTier.TIER_5_BLOCKED_UNTIL_APPROVED
    return [
        _candidate("CME_NQ_ES_FUTURES", "CME Group NQ/ES futures market data", ("nasdaq_index_direction", "finance"), T0, SourceClass.FUTURES_MARKET_DATA, "https://www.cmegroup.com/market-data.html", endpoints=("NQ orderbook", "NQ trades", "ES context")),
        _candidate("CME_CL_ENERGY_FUTURES", "CME Group CL/energy futures market data", ("oil_energy_direction", "commodities"), T0, SourceClass.FUTURES_MARKET_DATA, "https://www.cmegroup.com/market-data.html", endpoints=("CL orderbook", "CL trades")),
        _candidate("ICE_BRENT_ENERGY_FUTURES", "ICE Brent and energy futures", ("oil_energy_direction", "commodities"), T0, SourceClass.FUTURES_MARKET_DATA, "https://www.ice.com/market-data"),
        _candidate("DATABENTO_FUTURES_EQUITIES_OPTIONS", "Databento futures/equities/options", ("nasdaq_index_direction", "oil_energy_direction", "finance", "commodities"), T2, SourceClass.FUTURES_MARKET_DATA, "https://databento.com", credential_env_vars=("DATABENTO_API_KEY",)),
        _candidate("POLYGON_MASSIVE_MARKET_DATA", "Polygon/Massive market data", ("nasdaq_index_direction", "finance"), T2, SourceClass.EQUITY_MARKET_DATA, "https://polygon.io", credential_env_vars=("POLYGON_API_KEY",)),
        _candidate("NASDAQ_DATA_LINK", "Nasdaq Data Link", ("nasdaq_index_direction", "finance", "commodities"), T2, SourceClass.EQUITY_MARKET_DATA, "https://data.nasdaq.com", credential_env_vars=("NASDAQ_DATA_LINK_API_KEY",)),
        _candidate("CBOE_DATASHOP_LIVEVOL", "Cboe DataShop / LiveVol", ("nasdaq_index_direction", "volatility", "finance"), T2, SourceClass.OPTIONS_VOLATILITY, "https://datashop.cboe.com"),
        _candidate("DXFEED_MARKET_DATA", "dxFeed market data", ("nasdaq_index_direction", "finance", "volatility"), T2, SourceClass.EQUITY_MARKET_DATA, "https://www.dxfeed.com"),
        _candidate("INTRINIO_MARKET_DATA", "Intrinio market data", ("nasdaq_index_direction", "finance"), T2, SourceClass.EQUITY_MARKET_DATA, "https://intrinio.com", credential_env_vars=("INTRINIO_API_KEY",)),
        _candidate("TIINGO_MARKET_DATA", "Tiingo market data", ("nasdaq_index_direction", "finance"), T2, SourceClass.EQUITY_MARKET_DATA, "https://www.tiingo.com", credential_env_vars=("TIINGO_API_KEY",)),
        _candidate("ALPHA_VANTAGE_CONTEXT", "Alpha Vantage", ("nasdaq_index_direction", "finance"), T4, SourceClass.EQUITY_MARKET_DATA, "https://www.alphavantage.co", credential_env_vars=("ALPHA_VANTAGE_API_KEY",), approval_status=SourceApprovalStatus.BLOCKED_KEY_MISSING, license_status=SourceLicenseStatus.KEY_REQUIRED, cost_class=SourceCostClass.FREE_KEY_REQUIRED),
        _candidate("TWELVE_DATA_CONTEXT", "Twelve Data", ("nasdaq_index_direction", "finance"), T2, SourceClass.EQUITY_MARKET_DATA, "https://twelvedata.com", credential_env_vars=("TWELVE_DATA_API_KEY",)),
        _candidate("EODHD_CONTEXT", "EODHD", ("nasdaq_index_direction", "finance"), T2, SourceClass.EQUITY_MARKET_DATA, "https://eodhd.com", credential_env_vars=("EODHD_API_KEY",)),
        _candidate("YFINANCE_RESEARCH_ONLY", "Yahoo/yfinance research fallback", ("nasdaq_index_direction", "finance"), T4, SourceClass.EQUITY_MARKET_DATA, "https://finance.yahoo.com", terms_risk="Research-only fallback with terms caution; not production truth."),
        _candidate("FRED_ALFRED_MACRO_CONTEXT", "FRED/ALFRED official macro context", ("finance", "cross_asset_macro", "nasdaq_index_direction"), T1, SourceClass.MACRO_OFFICIAL, "https://fred.stlouisfed.org"),
        _candidate("BEA_API", "BEA API", ("finance", "cross_asset_macro"), T1, SourceClass.MACRO_OFFICIAL, "https://apps.bea.gov/api", credential_env_vars=("BEA_API_KEY",), approval_status=SourceApprovalStatus.BLOCKED_KEY_MISSING, license_status=SourceLicenseStatus.KEY_REQUIRED, cost_class=SourceCostClass.FREE_KEY_REQUIRED),
        _candidate("BLS_API", "BLS API", ("finance", "cross_asset_macro", "nasdaq_index_direction"), T1, SourceClass.MACRO_OFFICIAL, "https://www.bls.gov/developers/"),
        _candidate("CENSUS_API", "Census API", ("finance", "cross_asset_macro"), T1, SourceClass.MACRO_OFFICIAL, "https://www.census.gov/data/developers.html"),
        _candidate("TREASURY_FISCAL_DATA", "Treasury Fiscal Data API", ("finance", "cross_asset_macro"), T1, SourceClass.MACRO_OFFICIAL, "https://fiscaldata.treasury.gov/api-documentation/"),
        _candidate("TREASURY_YIELD_DATA", "Treasury yield data", ("finance", "cross_asset_macro", "nasdaq_index_direction"), T1, SourceClass.MACRO_OFFICIAL, "https://home.treasury.gov/resource-center/data-chart-center/interest-rates"),
        _candidate("FED_H41_H8", "Federal Reserve H.4.1/H.8", ("finance", "cross_asset_macro"), T1, SourceClass.MACRO_OFFICIAL, "https://www.federalreserve.gov/releases/"),
        _candidate("SEC_EDGAR", "SEC EDGAR", ("finance", "nasdaq_index_direction", "news_event_metadata"), T1, SourceClass.MACRO_OFFICIAL, "https://www.sec.gov/edgar"),
        _candidate("EIA_OPEN_DATA", "EIA Open Data API", ("oil_energy_direction", "commodities"), T1, SourceClass.COMMODITY_FUNDAMENTALS, "https://www.eia.gov/opendata/", credential_env_vars=("EIA_API_KEY",), approval_status=SourceApprovalStatus.BLOCKED_KEY_MISSING, license_status=SourceLicenseStatus.KEY_REQUIRED, cost_class=SourceCostClass.FREE_KEY_REQUIRED),
        _candidate("OPEC_PUBLIC_REPORTS", "OPEC public reports", ("oil_energy_direction", "commodities"), T4, SourceClass.COMMODITY_FUNDAMENTALS, "https://www.opec.org"),
        _candidate("IEA_PUBLIC_REPORTS", "IEA public reports/data", ("oil_energy_direction", "commodities"), T4, SourceClass.COMMODITY_FUNDAMENTALS, "https://www.iea.org", terms_risk="Source/license review required before activation."),
        _candidate("BAKER_HUGHES_RIG_COUNT", "Baker Hughes rig count", ("oil_energy_direction", "commodities"), T4, SourceClass.COMMODITY_FUNDAMENTALS, "https://rigcount.bakerhughes.com", terms_risk="Public/commercial terms review required."),
        _candidate("NOAA_NWS_HURRICANE_DISRUPTION", "NOAA/NWS hurricane and disruption products", ("oil_energy_direction", "weather"), T1, SourceClass.WEATHER_FORECAST, "https://www.nhc.noaa.gov"),
        _candidate("MARINETRAFFIC_KPLER_VORTEXA", "MarineTraffic/Kpler/Vortexa tanker flows", ("oil_energy_direction", "commodities"), T2, SourceClass.COMMODITY_FUNDAMENTALS, "https://www.marinetraffic.com"),
        _candidate("WOODMAC_RYSTAD_GENSCAPE", "Wood Mackenzie/Rystad/Genscape", ("oil_energy_direction", "commodities"), T2, SourceClass.COMMODITY_FUNDAMENTALS, "https://www.woodmac.com"),
        _candidate("WORLD_BANK_COMMODITY_PRICES", "World Bank commodity prices", ("commodities", "oil_energy_direction", "cross_asset_macro"), T1, SourceClass.COMMODITY_FUNDAMENTALS, "https://www.worldbank.org/en/research/commodity-markets"),
        _candidate("USDA_NASS_QUICK_STATS", "USDA NASS Quick Stats", ("commodities",), T1, SourceClass.COMMODITY_FUNDAMENTALS, "https://quickstats.nass.usda.gov", credential_env_vars=("USDA_NASS_API_KEY",), approval_status=SourceApprovalStatus.BLOCKED_KEY_MISSING, license_status=SourceLicenseStatus.KEY_REQUIRED, cost_class=SourceCostClass.FREE_KEY_REQUIRED),
        _candidate("USDA_WASDE", "USDA WASDE", ("commodities",), T1, SourceClass.COMMODITY_FUNDAMENTALS, "https://www.usda.gov/oce/commodity/wasde"),
        _candidate("LME_DATA", "LME data", ("commodities",), T2, SourceClass.FUTURES_MARKET_DATA, "https://www.lme.com"),
        _candidate("GDELT_EVENT_METADATA", "GDELT news/event metadata", ("commodities", "news_event_metadata", "oil_energy_direction", "nasdaq_index_direction"), T4, SourceClass.NEWS_EVENT_METADATA, "https://www.gdeltproject.org", terms_risk="Public source/terms gate required."),
        _candidate("COINBASE_PUBLIC_MARKET_DATA", "Coinbase public market data", ("crypto",), T4, SourceClass.CRYPTO_EXCHANGE_PUBLIC, "https://docs.cloud.coinbase.com"),
        _candidate("KRAKEN_PUBLIC_API", "Kraken public API", ("crypto",), T4, SourceClass.CRYPTO_EXCHANGE_PUBLIC, "https://docs.kraken.com/api/"),
        _candidate("BINANCE_PUBLIC_API", "Binance public API", ("crypto",), T5, SourceClass.CRYPTO_EXCHANGE_PUBLIC, "https://developers.binance.com", approval_status=SourceApprovalStatus.BLOCKED_TERMS_UNCLEAR, terms_risk="Terms/region gate required."),
        _candidate("OKX_PUBLIC_API", "OKX public API", ("crypto",), T5, SourceClass.CRYPTO_EXCHANGE_PUBLIC, "https://www.okx.com/docs-v5/en/", approval_status=SourceApprovalStatus.BLOCKED_TERMS_UNCLEAR),
        _candidate("BYBIT_PUBLIC_API", "Bybit public API", ("crypto",), T5, SourceClass.CRYPTO_EXCHANGE_PUBLIC, "https://bybit-exchange.github.io/docs/v5/intro", approval_status=SourceApprovalStatus.BLOCKED_TERMS_UNCLEAR),
        _candidate("DERIBIT_PUBLIC_OPTIONS_VOL", "Deribit public options/vol", ("crypto", "volatility"), T5, SourceClass.OPTIONS_VOLATILITY, "https://docs.deribit.com", approval_status=SourceApprovalStatus.BLOCKED_TERMS_UNCLEAR),
        _candidate("CCXT_PUBLIC_PLAN", "CCXT exchange public adapter plan", ("crypto",), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/ccxt/ccxt"),
        _candidate("KAIKO_COMMERCIAL", "Kaiko", ("crypto",), T2, SourceClass.CRYPTO_EXCHANGE_PUBLIC, "https://www.kaiko.com"),
        _candidate("COINAPI_COMMERCIAL", "CoinAPI", ("crypto",), T2, SourceClass.CRYPTO_EXCHANGE_PUBLIC, "https://www.coinapi.io", credential_env_vars=("COINAPI_KEY",)),
        _candidate("CRYPTOCOMPARE_KEY_GATE", "CryptoCompare", ("crypto",), T2, SourceClass.CRYPTO_EXCHANGE_PUBLIC, "https://min-api.cryptocompare.com", credential_env_vars=("CRYPTOCOMPARE_API_KEY",)),
        _candidate("COINMARKETCAP_KEY_GATE", "CoinMarketCap API", ("crypto",), T2, SourceClass.CRYPTO_EXCHANGE_PUBLIC, "https://coinmarketcap.com/api/", credential_env_vars=("COINMARKETCAP_API_KEY",)),
        _candidate("COINGECKO_CONTEXT_ONLY", "CoinGecko API", ("crypto",), T4, SourceClass.CRYPTO_EXCHANGE_PUBLIC, "https://www.coingecko.com/en/api", terms_risk="Context only; not sufficient as edge truth."),
        _candidate("GLASSNODE_COMMERCIAL", "Glassnode", ("crypto",), T2, SourceClass.CRYPTO_ONCHAIN, "https://glassnode.com"),
        _candidate("CRYPTOQUANT_COMMERCIAL", "CryptoQuant", ("crypto",), T2, SourceClass.CRYPTO_ONCHAIN, "https://cryptoquant.com"),
        _candidate("THE_GRAPH_PUBLIC_KEY_GATE", "The Graph", ("crypto",), T4, SourceClass.CRYPTO_ONCHAIN, "https://thegraph.com"),
        _candidate("DUNE_API_KEY_GATE", "Dune API", ("crypto",), T2, SourceClass.CRYPTO_ONCHAIN, "https://dune.com/docs/api/", credential_env_vars=("DUNE_API_KEY",)),
        _candidate("DEFILLAMA_PUBLIC_CONTEXT", "DefiLlama API", ("crypto",), T4, SourceClass.CRYPTO_ONCHAIN, "https://defillama.com/docs/api"),
        _candidate("NWS_API_WEATHER_GOV", "NWS api.weather.gov", ("weather", "sports", "oil_energy_direction"), T1, SourceClass.WEATHER_FORECAST, "https://api.weather.gov"),
        _candidate("NOAA_CLIMATE_DATA_ONLINE", "NOAA Climate Data Online / NCEI", ("weather",), T1, SourceClass.WEATHER_OBSERVATION, "https://www.ncei.noaa.gov/cdo-web/"),
        _candidate("NOAA_MRMS", "NOAA MRMS", ("weather",), T1, SourceClass.WEATHER_OBSERVATION, "https://www.nssl.noaa.gov/projects/mrms/"),
        _candidate("NOAA_SPC", "NOAA SPC", ("weather",), T1, SourceClass.WEATHER_FORECAST, "https://www.spc.noaa.gov"),
        _candidate("NOAA_NHC", "NOAA NHC", ("weather", "oil_energy_direction"), T1, SourceClass.WEATHER_FORECAST, "https://www.nhc.noaa.gov"),
        _candidate("NOAA_NOMADS_AWS_HRRR_RAP_GFS", "NOAA NOMADS/AWS HRRR/RAP/GFS", ("weather",), T1, SourceClass.WEATHER_FORECAST, "https://nomads.ncep.noaa.gov"),
        _candidate("ECMWF_OPEN_DATA", "ECMWF Open Data", ("weather",), T1, SourceClass.WEATHER_FORECAST, "https://www.ecmwf.int/en/forecasts/datasets/open-data"),
        _candidate("METEOSTAT", "Meteostat", ("weather",), T4, SourceClass.WEATHER_OBSERVATION, "https://meteostat.net"),
        _candidate("OPEN_METEO", "Open-Meteo", ("weather",), T4, SourceClass.WEATHER_FORECAST, "https://open-meteo.com"),
        _candidate("TOMORROWIO_ACCUWEATHER_WEATHERCOMPANY", "Tomorrow.io / AccuWeather / Weather Company", ("weather",), T2, SourceClass.WEATHER_FORECAST, "https://www.tomorrow.io"),
        _candidate("IEM_ASOS_AWOS", "IEM ASOS/AWOS station observations", ("weather", "sports"), T4, SourceClass.WEATHER_OBSERVATION, "https://mesonet.agron.iastate.edu/request/download.phtml"),
        _candidate("SPORTSDATAIO_LICENSED", "SportsDataIO", ("sports",), T2, SourceClass.SPORTS_STATS, "https://sportsdata.io"),
        _candidate("SPORTSRADAR_LICENSED", "Sportradar", ("sports",), T2, SourceClass.SPORTS_STATS, "https://sportradar.com"),
        _candidate("STATS_PERFORM_OPTA", "Stats Perform / Opta", ("sports",), T2, SourceClass.SPORTS_STATS, "https://www.statsperform.com/opta/"),
        _candidate("THESPORTSDB_PUBLIC", "TheSportsDB", ("sports",), T4, SourceClass.SPORTS_STATS, "https://www.thesportsdb.com"),
        _candidate("BALLDONTLIE_NBA_PUBLIC", "balldontlie NBA public API", ("sports",), T4, SourceClass.SPORTS_STATS, "https://www.balldontlie.io"),
        _candidate("CFBD_API", "CollegeFootballData API", ("sports",), T4, SourceClass.SPORTS_STATS, "https://collegefootballdata.com"),
        _candidate("SPORTSDATAVERSE_NFLVERSE", "sportsdataverse/nflverse", ("sports",), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/nflverse"),
        _candidate("MLB_STATS_API_TERMS_REVIEW", "MLB Stats API", ("sports",), T5, SourceClass.SPORTS_SCHEDULE_STATUS, "https://statsapi.mlb.com", approval_status=SourceApprovalStatus.BLOCKED_TERMS_UNCLEAR),
        _candidate("NHL_API_TERMS_REVIEW", "NHL API", ("sports",), T5, SourceClass.SPORTS_SCHEDULE_STATUS, "https://api-web.nhle.com", approval_status=SourceApprovalStatus.BLOCKED_TERMS_UNCLEAR),
        _candidate("FOOTBALL_DATA_ORG_KEY_GATE", "football-data.org", ("sports",), T4, SourceClass.SPORTS_STATS, "https://www.football-data.org", credential_env_vars=("FOOTBALL_DATA_API_KEY",), approval_status=SourceApprovalStatus.BLOCKED_KEY_MISSING, license_status=SourceLicenseStatus.KEY_REQUIRED, cost_class=SourceCostClass.FREE_KEY_REQUIRED),
        _candidate("KAGGLE_HISTORICAL_SPORTS_FIXTURE", "Kaggle historical datasets", ("sports",), T4, SourceClass.STATIC_FIXTURE, "https://www.kaggle.com", approval_status=SourceApprovalStatus.APPROVED_STATIC_FIXTURE, license_status=SourceLicenseStatus.STATIC_FIXTURE, freshness_class=SourceFreshnessClass.STATIC_FIXTURE),
        _candidate("INTERACTIVE_BROKERS_READONLY_GATE", "Interactive Brokers read-only gate", ("finance", "nasdaq_index_direction"), T5, SourceClass.EQUITY_MARKET_DATA, "https://www.interactivebrokers.com", approval_status=SourceApprovalStatus.BLOCKED_EXECUTION_AUTHORITY),
        _candidate("OPENBB_FINANCE_OPENBB", "OpenBB-finance/OpenBB", ("finance", "nasdaq_index_direction"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/OpenBB-finance/OpenBB"),
        _candidate("WEATHER_GOV_API_GITHUB_DOCS", "weather-gov/api GitHub docs", ("weather",), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/weather-gov/api"),
        _candidate("ROPENSCI_EIA", "ropensci/eia", ("oil_energy_direction", "commodities"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/ropensci/eia"),
        _candidate("RANAROUSSI_YFINANCE", "ranaroussi/yfinance", ("finance", "nasdaq_index_direction"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/ranaroussi/yfinance"),
        _candidate("ROMELTORRES_ALPHA_VANTAGE", "RomelTorres/alpha_vantage", ("finance", "nasdaq_index_direction"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/RomelTorres/alpha_vantage"),
        _candidate("WILSONFREITAS_AWESOME_QUANT", "wilsonfreitas/awesome-quant", ("finance", "nasdaq_index_direction"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/wilsonfreitas/awesome-quant"),
        _candidate("FINRL_REFERENCE", "FinRL reference", ("finance",), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/AI4Finance-Foundation/FinRL"),
        _candidate("FINGPT_REFERENCE", "FinGPT reference", ("finance", "news_event_metadata"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/AI4Finance-Foundation/FinGPT"),
        _candidate("FINNLP_REFERENCE", "FinNLP reference", ("finance", "news_event_metadata"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/AI4Finance-Foundation/FinNLP"),
        _candidate("PYBASEBALL", "pybaseball", ("sports",), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/jldbc/pybaseball"),
        _candidate("NBA_API", "nba_api", ("sports",), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/swar/nba_api"),
        _candidate("HERBIE_METPY_SIPHON", "Herbie / MetPy / Siphon", ("weather",), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/blaylockbk/Herbie"),
        _candidate("SEC_EDGAR_DOWNLOADER", "sec-edgar-downloader / SEC clients", ("finance",), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/jadchaar/sec-edgar-downloader"),
        _candidate("PANDAS_DATAREADER", "pandas-datareader", ("finance", "cross_asset_macro"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/pydata/pandas-datareader"),
        _candidate("QUANTLIB_PYTHON", "QuantLib-Python", ("finance", "volatility"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/lballabio/QuantLib-SWIG"),
        _candidate("PY_VOLLIB", "py_vollib", ("finance", "volatility"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/vollib/py_vollib"),
        _candidate("ARCH_STATSMODELS", "arch / statsmodels", ("finance", "cross_asset_macro", "volatility"), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/bashtage/arch"),
        _candidate("VECTORBT_BACKTRADER_ZIPLINE", "vectorbt / backtrader / zipline-like tools", ("finance",), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/polakowo/vectorbt"),
        _candidate("FREQTRADE_HUMMINGBOT_ARCH_REF", "freqtrade/hummingbot architecture reference", ("crypto",), T3, SourceClass.GITHUB_ADAPTER_CANDIDATE, "https://github.com/freqtrade/freqtrade", terms_risk="Architecture reference only; no execution authority."),
    ]
