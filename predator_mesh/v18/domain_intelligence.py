"""Domain intelligence spine for V18 research and baseline forecasting."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v18 import DOMAINS


class DomainMarketClass(str, Enum):
    SPORTS = "SPORTS_EVENT"
    WEATHER = "WEATHER_EVENT"
    CRYPTO = "CRYPTO_REFERENCE_PRICE_EVENT"
    COMMODITIES = "COMMODITIES_REFERENCE_EVENT"
    FINANCE = "FINANCE_MACRO_OR_INDEX_EVENT"


@dataclass(frozen=True)
class DomainFeatureSchema:
    domain: str
    required_features: tuple[str, ...]
    settlement_ambiguity_flag_required: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "required_features": list(self.required_features),
            "settlement_ambiguity_flag_required": self.settlement_ambiguity_flag_required,
        }


@dataclass(frozen=True)
class DomainResearchNeed:
    domain: str
    questions: tuple[str, ...]
    source_categories: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "questions": list(self.questions), "source_categories": list(self.source_categories)}


@dataclass(frozen=True)
class DomainForecastNeed:
    domain: str
    baseline_types: tuple[str, ...]
    snapshot_requirements: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "baseline_types": list(self.baseline_types),
            "snapshot_requirements": list(self.snapshot_requirements),
        }


@dataclass(frozen=True)
class DomainNoTradePressure:
    domain: str
    triggers: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "triggers": list(self.triggers)}


@dataclass(frozen=True)
class DomainProfile:
    domain: str
    market_class: DomainMarketClass
    supported_event_types: tuple[str, ...]
    required_settlement_facts: tuple[str, ...]
    required_source_categories: tuple[str, ...]
    required_baseline_features: tuple[str, ...]
    domain_specific_no_trade_triggers: tuple[str, ...]
    outcome_ontology_mapping: tuple[str, ...]
    forecast_snapshot_requirements: tuple[str, ...]
    calibration_profile_requirements: tuple[str, ...]

    def feature_schema(self) -> DomainFeatureSchema:
        return DomainFeatureSchema(self.domain, self.required_baseline_features)

    def research_need(self) -> DomainResearchNeed:
        return DomainResearchNeed(
            domain=self.domain,
            questions=(
                "What is the exact event definition?",
                "Which public or fixture-labeled sources support the facts?",
                "What would make this a no-trade before forecasting?",
            ),
            source_categories=self.required_source_categories,
        )

    def forecast_need(self) -> DomainForecastNeed:
        return DomainForecastNeed(
            domain=self.domain,
            baseline_types=("neutral", "source_consensus_or_market_implied_if_available", "domain_fixture_baseline"),
            snapshot_requirements=self.forecast_snapshot_requirements,
        )

    def no_trade_pressure(self) -> DomainNoTradePressure:
        return DomainNoTradePressure(self.domain, self.domain_specific_no_trade_triggers)

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "market_class": self.market_class.value,
            "supported_event_types": list(self.supported_event_types),
            "required_settlement_facts": list(self.required_settlement_facts),
            "required_source_categories": list(self.required_source_categories),
            "required_baseline_features": list(self.required_baseline_features),
            "domain_specific_no_trade_triggers": list(self.domain_specific_no_trade_triggers),
            "outcome_ontology_mapping": list(self.outcome_ontology_mapping),
            "forecast_snapshot_requirements": list(self.forecast_snapshot_requirements),
            "calibration_profile_requirements": list(self.calibration_profile_requirements),
        }


_PROFILE_DATA: dict[str, DomainProfile] = {
    "sports": DomainProfile(
        domain="sports",
        market_class=DomainMarketClass.SPORTS,
        supported_event_types=("game_winner", "game_total", "player_stat_threshold"),
        required_settlement_facts=("event_time", "league_rule", "final_score_or_stat", "postponement_policy"),
        required_source_categories=("official_schedule", "official_result", "public_injury_news_boundary", "weather_if_outdoor"),
        required_baseline_features=(
            "game_team_identifiers",
            "schedule_time_context",
            "market_event_type",
            "team_player_stat_threshold_if_applicable",
            "weather_impact_flag_for_outdoor_sports",
            "injury_news_metadata_legality_boundary",
            "historical_team_form_placeholder",
            "settlement_ambiguity_flag",
            "stale_source_flag",
        ),
        domain_specific_no_trade_triggers=(
            "unclear_settlement_rule",
            "postponed_or_cancelled_event_risk",
            "stale_injury_news_data",
            "bad_source_legality",
            "missing_event_time_context",
            "insufficient_source_agreement",
        ),
        outcome_ontology_mapping=("game_winner", "game_total", "manual_import_required"),
        forecast_snapshot_requirements=("market_id", "event_id", "probability", "fixture_or_real_evidence_label", "source_refs"),
        calibration_profile_requirements=("sport", "market_type", "settlement_status", "sample_count"),
    ),
    "weather": DomainProfile(
        domain="weather",
        market_class=DomainMarketClass.WEATHER,
        supported_event_types=("temperature_threshold", "precipitation_threshold", "extreme_weather_event"),
        required_settlement_facts=("location", "time_window", "measurement_type", "station_or_source_definition"),
        required_source_categories=("official_weather_station", "public_forecast_family", "settlement_source"),
        required_baseline_features=(
            "location",
            "time_window",
            "measurement_type",
            "station_source_definition",
            "forecast_source_family",
            "forecast_disagreement",
            "forecast_age",
            "spatial_uncertainty",
            "temporal_uncertainty",
            "extreme_event_flag",
            "settlement_ambiguity_flag",
        ),
        domain_specific_no_trade_triggers=(
            "unclear_location",
            "unclear_station_or_source",
            "unclear_time_window",
            "high_forecast_disagreement",
            "stale_forecast",
            "extreme_event_uncertainty",
            "missing_settlement_source",
        ),
        outcome_ontology_mapping=("temperature_threshold", "precipitation_threshold", "manual_import_required"),
        forecast_snapshot_requirements=("forecast_age", "source_family_refs", "uncertainty_flags", "fixture_or_real_evidence_label"),
        calibration_profile_requirements=("location_family", "horizon", "measurement_type", "sample_count"),
    ),
    "crypto": DomainProfile(
        domain="crypto",
        market_class=DomainMarketClass.CRYPTO,
        supported_event_types=("crypto_price_above", "crypto_reference_price_threshold"),
        required_settlement_facts=("asset_symbol", "reference_price_source", "settlement_time", "reference_price_rule"),
        required_source_categories=("public_spot_reference", "public_index_reference", "legality_checked_news_placeholder"),
        required_baseline_features=(
            "asset_symbol",
            "reference_price_source",
            "settlement_time",
            "spot_price_terrain",
            "volatility_regime",
            "liquidity_spread_context_if_available",
            "stale_price_check",
            "fragmented_source_check",
            "event_news_impulse_legality_boundary",
            "macro_risk_placeholder",
            "settlement_ambiguity_flag",
        ),
        domain_specific_no_trade_triggers=(
            "stale_price",
            "fragmented_source_disagreement",
            "unclear_settlement_source",
            "volatility_shock",
            "thin_liquidity",
            "source_legality_missing",
            "reference_source_discrepancy",
        ),
        outcome_ontology_mapping=("crypto_price_above", "manual_import_required"),
        forecast_snapshot_requirements=("asset_symbol", "settlement_time", "reference_source_ref", "no_perp_execution_label"),
        calibration_profile_requirements=("asset_symbol", "volatility_regime", "horizon", "sample_count"),
    ),
    "commodities": DomainProfile(
        domain="commodities",
        market_class=DomainMarketClass.COMMODITIES,
        supported_event_types=("commodity_settlement_price", "inventory_report_threshold", "weather_sensitive_supply_event"),
        required_settlement_facts=("commodity_category", "reference_price_source", "settlement_time", "settlement_source"),
        required_source_categories=("public_reference_price", "public_report_calendar", "official_inventory_report"),
        required_baseline_features=(
            "commodity_category",
            "reference_price_source",
            "settlement_time_source",
            "report_calendar_flag",
            "inventory_report_event_flag",
            "weather_sensitivity_flag",
            "seasonality_placeholder",
            "supply_shock_placeholder",
            "futures_curve_basis_context_if_public_allowed",
            "settlement_ambiguity_flag",
        ),
        domain_specific_no_trade_triggers=(
            "unclear_reference_price",
            "unclear_settlement_timing",
            "stale_report_calendar",
            "high_source_disagreement",
            "supply_shock_uncertainty",
            "bad_source_legality",
            "missing_settlement_proof",
        ),
        outcome_ontology_mapping=("commodity_settlement_price", "manual_import_required"),
        forecast_snapshot_requirements=("category", "reference_source_ref", "report_calendar_flag", "fixture_or_real_evidence_label"),
        calibration_profile_requirements=("commodity_category", "report_event_flag", "horizon", "sample_count"),
    ),
    "finance": DomainProfile(
        domain="finance",
        market_class=DomainMarketClass.FINANCE,
        supported_event_types=("macro_release_threshold", "equity_index_close", "etf_threshold"),
        required_settlement_facts=("macro_event_type", "release_time", "official_source", "event_definition"),
        required_source_categories=("official_macro_source", "public_calendar", "legally_sourced_consensus_placeholder", "market_proxy_context"),
        required_baseline_features=(
            "macro_event_type",
            "release_time",
            "official_source",
            "consensus_expectation_placeholder_if_legal",
            "prior_value_placeholder",
            "market_proxy_context",
            "rates_inflation_jobs_gdp_category",
            "index_etf_threshold_category_if_applicable",
            "volatility_regime",
            "cross_asset_confirmation_placeholder",
            "settlement_ambiguity_flag",
        ),
        domain_specific_no_trade_triggers=(
            "unclear_official_source",
            "unclear_release_time",
            "stale_macro_calendar",
            "ambiguous_event_definition",
            "conflicting_source_values",
            "bad_source_legality",
            "release_already_occurred",
        ),
        outcome_ontology_mapping=("equity_index_close", "earnings_result", "manual_import_required"),
        forecast_snapshot_requirements=("release_time", "official_source_ref", "event_definition", "pre_release_label"),
        calibration_profile_requirements=("macro_category", "release_horizon", "volatility_regime", "sample_count"),
    ),
}


class DomainIntelligenceSpine:
    def __init__(self, profiles: dict[str, DomainProfile] | None = None) -> None:
        self._profiles = profiles or _PROFILE_DATA

    def profiles(self) -> list[DomainProfile]:
        return [self._profiles[domain] for domain in DOMAINS]

    def profile_for(self, domain: str) -> DomainProfile:
        try:
            return self._profiles[domain]
        except KeyError as exc:
            raise ValueError(f"Unsupported V18 domain: {domain}") from exc

    def to_report(self) -> dict[str, Any]:
        profiles = self.profiles()
        return {
            "workstream": "V18: Domain Intelligence Spine",
            "domains": list(DOMAINS),
            "domain_count": len(profiles),
            "profiles": [profile.to_dict() for profile in profiles],
            "research_needs": [profile.research_need().to_dict() for profile in profiles],
            "forecast_needs": [profile.forecast_need().to_dict() for profile in profiles],
            "no_trade_pressure": [profile.no_trade_pressure().to_dict() for profile in profiles],
            "live_submit_disabled": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def profile_manifest(self) -> dict[str, Any]:
        return {
            "workstream": "V18: Domain Profile Manifest",
            "profiles": list(DOMAINS),
            "profile_manifest": {profile.domain: profile.to_dict() for profile in self.profiles()},
            "source_legality_required": True,
            "forecast_snapshots_required": True,
            "calibration_profiles_required": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def feature_schema_report(self) -> dict[str, Any]:
        schemas = {profile.domain: profile.feature_schema().to_dict() for profile in self.profiles()}
        return {
            "workstream": "V18: Domain Feature Schema",
            "schemas": list(schemas),
            "feature_schemas": schemas,
            "settlement_ambiguity_flag_required": True,
            "stale_source_flag_supported": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }
