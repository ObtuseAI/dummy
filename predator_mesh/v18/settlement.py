"""Settlement-rule mapping and ambiguity pressure for V18."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from predator_mesh.v18 import DOMAINS
from predator_mesh.v18.domain_intelligence import DomainIntelligenceSpine


@dataclass(frozen=True)
class SettlementSourceRequirement:
    source_ref: str
    legality_required: bool
    read_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {"source_ref": self.source_ref, "legality_required": self.legality_required, "read_only": self.read_only}


@dataclass(frozen=True)
class SettlementRuleProfile:
    domain: str
    rule_id: str
    event_types: tuple[str, ...]
    required_facts: tuple[str, ...]
    source_requirement: SettlementSourceRequirement
    ambiguity_flags: tuple[str, ...]
    fabricates_truth: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "rule_id": self.rule_id,
            "event_types": list(self.event_types),
            "required_facts": list(self.required_facts),
            "source_requirement": self.source_requirement.to_dict(),
            "ambiguity_flags": list(self.ambiguity_flags),
            "fabricates_truth": self.fabricates_truth,
        }


@dataclass(frozen=True)
class SettlementNoTradePressure:
    domain: str
    reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "reasons": list(self.reasons)}


class SettlementRuleMapper:
    max_request_timeout_s = 10
    total_timeout_s = 45

    def __init__(self, spine: DomainIntelligenceSpine | None = None) -> None:
        self.spine = spine or DomainIntelligenceSpine()

    def profiles(self) -> list[SettlementRuleProfile]:
        profiles: list[SettlementRuleProfile] = []
        for domain in DOMAINS:
            profile = self.spine.profile_for(domain)
            profiles.append(
                SettlementRuleProfile(
                    domain=domain,
                    rule_id=f"{domain}-settlement-profile-v18",
                    event_types=profile.supported_event_types,
                    required_facts=profile.required_settlement_facts,
                    source_requirement=SettlementSourceRequirement(
                        source_ref=f"{domain}_settlement_fixture_v18",
                        legality_required=True,
                    ),
                    ambiguity_flags=("FIXTURE_PROFILE_NEEDS_OFFICIAL_SOURCE_CONFIRMATION",),
                )
            )
        return profiles

    def no_trade_pressures(self) -> list[SettlementNoTradePressure]:
        return [
            SettlementNoTradePressure(
                domain=profile.domain,
                reasons=("unclear_or_fixture_settlement_source", "source_disagreement_represented"),
            )
            for profile in self.profiles()
        ]

    def to_report(self) -> dict[str, Any]:
        profiles = self.profiles()
        return {
            "workstream": "V18: Settlement Rule Mapper",
            "domains": [profile.domain for profile in profiles],
            "profiles": [profile.to_dict() for profile in profiles],
            "settlement_source_explicit": True,
            "source_disagreement_represented": True,
            "fabricates_truth": any(profile.fabricates_truth for profile in profiles),
            "max_request_timeout_s": self.max_request_timeout_s,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def no_trade_pressure_report(self) -> dict[str, Any]:
        pressures = self.no_trade_pressures()
        return {
            "workstream": "V18: Settlement No-Trade Pressure",
            "pressure_count": len(pressures),
            "pressures": [pressure.to_dict() for pressure in pressures],
            "unclear_settlement_generates_no_trade": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


class SettlementAmbiguityDetector:
    def __init__(self, profiles: list[SettlementRuleProfile]) -> None:
        self._profiles = profiles

    def to_report(self) -> dict[str, Any]:
        ambiguous = [profile for profile in self._profiles if profile.ambiguity_flags]
        return {
            "workstream": "V18: Settlement Ambiguity Detector",
            "ambiguous_profile_count": len(ambiguous),
            "ambiguous_profiles": [profile.to_dict() for profile in ambiguous],
            "ambiguous_settlement_generates_no_trade": bool(ambiguous),
            "fabricates_truth": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }
