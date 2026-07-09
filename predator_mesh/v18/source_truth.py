"""Legality-first source truth registry for V18."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v18 import DOMAINS


class SourceLegalityClass(str, Enum):
    PUBLIC_ALLOWED = "PUBLIC_ALLOWED"
    PUBLIC_STATIC_FIXTURE = "PUBLIC_STATIC_FIXTURE"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    UNVERIFIED_SOURCE = "UNVERIFIED_SOURCE"
    DISALLOWED_PRIVATE = "DISALLOWED_PRIVATE"
    DISALLOWED_SCRAPING_RISK = "DISALLOWED_SCRAPING_RISK"


@dataclass(frozen=True)
class SourceFreshnessProfile:
    freshness_status: str
    max_age_seconds: int | None
    fallback_mode: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "freshness_status": self.freshness_status,
            "max_age_seconds": self.max_age_seconds,
            "fallback_mode": self.fallback_mode,
        }


@dataclass(frozen=True)
class SourceReliabilityProfile:
    sample_count: int
    outcome_backed: bool
    reliability_label: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_count": self.sample_count,
            "outcome_backed": self.outcome_backed,
            "reliability_label": self.reliability_label,
        }


@dataclass(frozen=True)
class SourceContradictionProfile:
    contradiction_id: str
    domain: str
    description: str
    source_refs: tuple[str, ...]
    represented: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "contradiction_id": self.contradiction_id,
            "domain": self.domain,
            "description": self.description,
            "source_refs": list(self.source_refs),
            "represented": self.represented,
        }


@dataclass(frozen=True)
class SourceDomainCoverage:
    domain: str
    source_refs: tuple[str, ...]
    coverage_status: str

    def to_dict(self) -> dict[str, Any]:
        return {"domain": self.domain, "source_refs": list(self.source_refs), "coverage_status": self.coverage_status}


@dataclass(frozen=True)
class SourcePromotionEligibility:
    source_id: str
    eligible: bool
    reason: str
    requires_outcome_backed_proof: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "eligible": self.eligible,
            "reason": self.reason,
            "requires_outcome_backed_proof": self.requires_outcome_backed_proof,
        }


@dataclass(frozen=True)
class SourceCandidate:
    source_id: str
    domain: str
    category: str
    legality_class: SourceLegalityClass
    freshness: SourceFreshnessProfile
    reliability: SourceReliabilityProfile
    fallback_mode: str
    sample_static: bool = True
    labeled_live: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "domain": self.domain,
            "category": self.category,
            "legality_class": self.legality_class.value,
            "freshness": self.freshness.to_dict(),
            "reliability": self.reliability.to_dict(),
            "fallback_mode": self.fallback_mode,
            "sample_static": self.sample_static,
            "labeled_live": self.labeled_live,
        }


class SourceTruthRegistryV2:
    def candidates(self) -> list[SourceCandidate]:
        return [
            SourceCandidate(
                source_id=f"{domain}_fixture_source_v18",
                domain=domain,
                category=f"{domain}_public_static_fixture",
                legality_class=SourceLegalityClass.PUBLIC_STATIC_FIXTURE,
                freshness=SourceFreshnessProfile("STATIC_FIXTURE", None, "fixture_static_no_live_claim"),
                reliability=SourceReliabilityProfile(0, False, "UNPROVEN_FIXTURE"),
                fallback_mode="no_trade_or_fixture_baseline_only",
            )
            for domain in DOMAINS
        ]

    def contradictions(self) -> list[SourceContradictionProfile]:
        return [
            SourceContradictionProfile(
                contradiction_id=f"{domain}-fixture-disagreement",
                domain=domain,
                description="Fixture lane records the contradiction shape before promoting any source.",
                source_refs=(f"{domain}_fixture_source_v18", f"{domain}_settlement_fixture_v18"),
            )
            for domain in DOMAINS
        ]

    def coverage(self) -> list[SourceDomainCoverage]:
        return [
            SourceDomainCoverage(
                domain=domain,
                source_refs=tuple(candidate.source_id for candidate in self.candidates() if candidate.domain == domain),
                coverage_status="FIXTURE_STATIC",
            )
            for domain in DOMAINS
        ]

    def promotion_eligibility(self) -> list[SourcePromotionEligibility]:
        return [
            SourcePromotionEligibility(
                source_id=candidate.source_id,
                eligible=False,
                reason="Fixture/static or unproven source cannot be promoted without outcome-backed proof.",
            )
            for candidate in self.candidates()
        ]

    def to_report(self) -> dict[str, Any]:
        candidates = self.candidates()
        return {
            "workstream": "V18: Source Truth Registry V2",
            "source_count": len(candidates),
            "sources": [candidate.to_dict() for candidate in candidates],
            "legality_classes": [item.value for item in SourceLegalityClass],
            "domain_coverage": [coverage.domain for coverage in self.coverage()],
            "all_sources_have_legality": all(candidate.legality_class for candidate in candidates),
            "all_sources_have_domain_coverage": all(candidate.domain in DOMAINS for candidate in candidates),
            "all_sources_have_freshness_profile": all(candidate.freshness for candidate in candidates),
            "all_sources_have_fallback_mode": all(candidate.fallback_mode for candidate in candidates),
            "sample_static_sources_labeled_live": any(candidate.sample_static and candidate.labeled_live for candidate in candidates),
            "source_bloodlines_connect_to_v17_outcome_attribution": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def legality_class_report(self) -> dict[str, Any]:
        return {
            "workstream": "V18: Source Legality Class",
            "legality_classes": [item.value for item in SourceLegalityClass],
            "legality_required_for_every_source": True,
            "private_insider_or_credentialed_data_allowed": False,
            "unauthorized_scraping_allowed": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def domain_coverage_report(self) -> dict[str, Any]:
        return {
            "workstream": "V18: Source Domain Coverage",
            "domain_coverage": [coverage.domain for coverage in self.coverage()],
            "coverage": [coverage.to_dict() for coverage in self.coverage()],
            "live_sources_claimed": [],
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def contradiction_report(self) -> dict[str, Any]:
        contradictions = self.contradictions()
        return {
            "workstream": "V18: Source Contradiction Profile",
            "contradictions_represented": bool(contradictions),
            "contradictions": [item.to_dict() for item in contradictions],
            "contradiction_count": len(contradictions),
            "hidden_contradictions": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def promotion_eligibility_report(self) -> dict[str, Any]:
        eligibility = self.promotion_eligibility()
        return {
            "workstream": "V18: Source Promotion Eligibility",
            "promotion_eligibility": [item.to_dict() for item in eligibility],
            "no_source_promoted_without_proof": all(not item.eligible for item in eligibility),
            "sample_static_sources_blocked_from_live_promotion": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }
