"""Domain-level source activation profiles and evidence packets."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from predator_mesh.v19.source_activation import RealReadOnlySourceActivationController, SourceActivationDecision


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


_TARGETS = {
    "sports": ["event_schedule_status", "team_game_identifiers", "start_time", "event_status", "postponement_flag", "weather_impact_placeholder"],
    "weather": ["location", "forecast_timestamp", "forecast_condition", "observation_condition_if_available", "station_identifier", "time_window"],
    "crypto": ["asset_symbol", "reference_price_source", "spot_reference_price", "timestamp", "volatility_regime", "stale_fragmented_source_check"],
    "commodities": ["commodity_category", "reference_source", "latest_reference_or_calendar_fixture", "timestamp_freshness", "report_calendar_flag"],
    "finance": ["macro_event_type", "release_time", "official_public_source", "latest_value_or_calendar_entry", "release_already_occurred_flag"],
}


@dataclass(frozen=True)
class DomainSourceActivationProfile:
    domain: str
    decision: SourceActivationDecision

    @property
    def proof_ref(self) -> str:
        return f"artifacts/dummy/{self.domain}_readonly_source_activation_report_v1.json"

    def activation_report(self) -> dict[str, Any]:
        return {
            "workstream": f"V19: {self.domain.title()} ReadOnly Source Activation",
            "domain": self.domain,
            "source_activation_mode": self.decision.mode.value,
            "source_legality_class": self.decision.candidate.legality_class,
            "evidence_targets": _TARGETS[self.domain],
            "bounded_timeout_seconds": self.decision.candidate.timeout_seconds,
            "read_only_only": True,
            "live_execution_enabled": False,
            "questionable_odds_scraping_added": False,
            "fixture_fallback_labeled": True,
            "proof_refs": [self.proof_ref],
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }

    def evidence_packet_report(self) -> dict[str, Any]:
        return {
            "workstream": f"V19: {self.domain.title()} Real Evidence Packet",
            "domain": self.domain,
            "source_activation_mode": self.decision.mode.value,
            "evidence_mode": "FIXTURE_STATIC_FALLBACK",
            "real_evidence": False,
            "fixture_evidence": True,
            "fixture_evidence_claimed_real": False,
            "fields": {target: f"{self.domain}_{target}_placeholder" for target in _TARGETS[self.domain]},
            "source_legality_class": self.decision.candidate.legality_class,
            "freshness_timestamp": _now_iso(),
            "settlement_mapping_link": f"artifacts/dummy/{self.domain}_settlement_map_report_v1.json",
            "no_trade_pressure": ["real_readonly_source_not_promoted"],
            "proof_refs": [f"artifacts/dummy/{self.domain}_real_evidence_packet_report_v1.json"],
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }

    def blocker_report(self) -> dict[str, Any]:
        return {
            "workstream": f"V19: {self.domain.title()} Source Activation Blocker",
            "domain": self.domain,
            "blockers": [item.to_dict() for item in self.decision.blockers],
            "proof_refs": [f"artifacts/dummy/{self.domain}_source_activation_blocker_report_v1.json"],
            "operator_action_required": "Approve and verify bounded public read-only source fetch before promotion.",
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }


def domain_source_profile(domain: str) -> DomainSourceActivationProfile:
    controller = RealReadOnlySourceActivationController()
    decisions = {item.candidate.domain: item for item in controller.decisions()}
    return DomainSourceActivationProfile(domain, decisions[domain])


class SportsReadOnlySourceAdapter: ...
class SportsScheduleEvidenceAdapter: ...
class SportsEventStatusEvidenceAdapter: ...
class SportsSourceActivationProfile(DomainSourceActivationProfile): ...
class SportsRealEvidencePacket: ...
class WeatherReadOnlySourceAdapter: ...
class WeatherForecastEvidenceAdapter: ...
class WeatherObservationEvidenceAdapter: ...
class WeatherSourceActivationProfile(DomainSourceActivationProfile): ...
class WeatherRealEvidencePacket: ...
class CryptoReadOnlySourceAdapter: ...
class CryptoSpotEvidenceAdapter: ...
class CryptoVolatilityEvidenceAdapter: ...
class CryptoReferencePriceEvidenceAdapter: ...
class CryptoSourceActivationProfile(DomainSourceActivationProfile): ...
class CryptoRealEvidencePacket: ...
class CommoditiesReadOnlySourceAdapter: ...
class CommoditiesReferenceEvidenceAdapter: ...
class CommoditiesReportCalendarEvidenceAdapter: ...
class CommoditiesSourceActivationProfile(DomainSourceActivationProfile): ...
class CommoditiesRealEvidencePacket: ...
class FinanceReadOnlySourceAdapter: ...
class MacroCalendarEvidenceAdapter: ...
class FinanceMarketProxyEvidenceAdapter: ...
class FinanceSourceActivationProfile(DomainSourceActivationProfile): ...
class FinanceRealEvidencePacket: ...
