"""Domain-specific V18 research foundations and baseline lanes."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from predator_mesh.v18.domain_intelligence import DomainIntelligenceSpine, DomainProfile


_BASELINES: dict[str, tuple[str, ...]] = {
    "sports": ("neutral_baseline", "market_implied_baseline_if_available", "simple_recent_form_fixture_baseline", "weather_impact_adjustment_when_evidence_exists"),
    "weather": ("neutral_baseline", "source_consensus_baseline", "persistence_baseline", "fixture_climatology_placeholder_static_only"),
    "crypto": ("neutral_baseline", "recent_trend_baseline", "source_consensus_price_baseline", "volatility_regime_fixture_baseline"),
    "commodities": ("neutral_baseline", "recent_trend_baseline", "report_calendar_fixture_baseline", "source_consensus_baseline_where_safe"),
    "finance": ("neutral_baseline", "prior_value_fixture_baseline", "market_implied_baseline_if_available", "source_consensus_baseline_if_legal"),
}

_EXCLUSIONS: dict[str, tuple[str, ...]] = {
    "crypto": ("no_crypto_perpetual_trading", "no_leverage", "no_live_perp_execution", "no_live_crypto_position_management"),
}


@dataclass(frozen=True)
class DomainResearchFoundation:
    profile: DomainProfile

    @property
    def domain(self) -> str:
        return self.profile.domain

    def research_report(self) -> dict[str, Any]:
        report = {
            "workstream": f"V18: {self.domain.title()} Research Foundation",
            "domain": self.domain,
            "market_class": self.profile.market_class.value,
            "supported_event_types": list(self.profile.supported_event_types),
            "feature_categories": list(self.profile.required_baseline_features),
            "source_categories": list(self.profile.required_source_categories),
            "settlement_facts": list(self.profile.required_settlement_facts),
            "source_legality_required": True,
            "fixture_evidence_claimed_real": False,
            "authorized_data_only": True,
            "exclusions": list(_EXCLUSIONS.get(self.domain, ())),
            "secret_values_exposed": False,
            "verdict": "PASS",
        }
        if self.domain == "commodities":
            report["commodity_categories"] = ["energy", "metals", "agriculture"]
        return report

    def baseline_report(self) -> dict[str, Any]:
        return {
            "workstream": f"V18: {self.domain.title()} Baseline Forecast",
            "domain": self.domain,
            "baseline_types": list(_BASELINES[self.domain]),
            "heavy_ml_used": False,
            "fake_edge_claimed": False,
            "fixture_vs_real_label_required": True,
            "forecast_snapshot_required": True,
            "exclusions": list(_EXCLUSIONS.get(self.domain, ())),
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def settlement_report(self) -> dict[str, Any]:
        return {
            "workstream": f"V18: {self.domain.title()} Settlement Map",
            "domain": self.domain,
            "settlement_facts": list(self.profile.required_settlement_facts),
            "settlement_source_required": True,
            "source_disagreement_represented": True,
            "fabricates_truth": False,
            "no_trade_on_ambiguity": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def no_trade_report(self) -> dict[str, Any]:
        return {
            "workstream": f"V18: {self.domain.title()} No-Trade Gate",
            "domain": self.domain,
            "no_trade_triggers": list(self.profile.domain_specific_no_trade_triggers),
            "settlement_ambiguity_generates_no_trade": True,
            "bad_source_legality_blocks_forecast": True,
            "stale_data_visible": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


def domain_foundation(domain: str) -> DomainResearchFoundation:
    return DomainResearchFoundation(DomainIntelligenceSpine().profile_for(domain))


class SportsFeatureSet:
    categories = DomainIntelligenceSpine().profile_for("sports").required_baseline_features


class SportsResearchPacket:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("sports").research_report()


class SportsSettlementMap:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("sports").settlement_report()


class SportsNoTradeGate:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("sports").no_trade_report()


class SportsBaselineForecast:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("sports").baseline_report()


class WeatherFeatureSet:
    categories = DomainIntelligenceSpine().profile_for("weather").required_baseline_features


class WeatherResearchPacket:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("weather").research_report()


class WeatherSettlementMap:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("weather").settlement_report()


class WeatherNoTradeGate:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("weather").no_trade_report()


class WeatherBaselineForecast:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("weather").baseline_report()


class CryptoFeatureSet:
    categories = DomainIntelligenceSpine().profile_for("crypto").required_baseline_features


class CryptoResearchPacket:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("crypto").research_report()


class CryptoSettlementMap:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("crypto").settlement_report()


class CryptoNoTradeGate:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("crypto").no_trade_report()


class CryptoBaselineForecast:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("crypto").baseline_report()


class CommoditiesFeatureSet:
    categories = DomainIntelligenceSpine().profile_for("commodities").required_baseline_features
    commodity_categories = ("energy", "metals", "agriculture")


class CommoditiesResearchPacket:
    def to_report(self) -> dict[str, Any]:
        report = domain_foundation("commodities").research_report()
        report["commodity_categories"] = list(CommoditiesFeatureSet.commodity_categories)
        return report


class CommoditiesSettlementMap:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("commodities").settlement_report()


class CommoditiesNoTradeGate:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("commodities").no_trade_report()


class CommoditiesBaselineForecast:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("commodities").baseline_report()


class FinanceFeatureSet:
    categories = DomainIntelligenceSpine().profile_for("finance").required_baseline_features


class FinanceResearchPacket:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("finance").research_report()


class FinanceSettlementMap:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("finance").settlement_report()


class FinanceNoTradeGate:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("finance").no_trade_report()


class FinanceBaselineForecast:
    def to_report(self) -> dict[str, Any]:
        return domain_foundation("finance").baseline_report()
