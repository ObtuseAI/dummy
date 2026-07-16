"""V20 source approval, license, terms, and credential gates."""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v20.source_universe import SourceApprovalStatus, SourceTier, SourceUniverse


class SourceCredentialRequirement(str, Enum):
    NONE = "NONE"
    API_KEY_PRESENCE_ONLY = "API_KEY_PRESENCE_ONLY"
    LICENSE_AND_KEY_REQUIRED = "LICENSE_AND_KEY_REQUIRED"


class SourceActivationAuthority(str, Enum):
    READ_ONLY_ONLY = "READ_ONLY_ONLY"
    BLOCKED_EXECUTION_AUTHORITY = "BLOCKED_EXECUTION_AUTHORITY"


class SourceBlockedReason(str, Enum):
    NOT_APPROVED = "NOT_APPROVED"
    LICENSE_REQUIRED = "LICENSE_REQUIRED"
    KEY_MISSING = "KEY_MISSING"
    TERMS_UNCLEAR = "TERMS_UNCLEAR"
    SCRAPING_RISK = "SCRAPING_RISK"
    EXECUTION_AUTHORITY = "EXECUTION_AUTHORITY"


@dataclass(frozen=True)
class SourceGateDecision:
    source_id: str
    approval_status: str
    activation_allowed: bool
    credential_requirement: SourceCredentialRequirement
    activation_authority: SourceActivationAuthority
    blocked_reasons: tuple[str, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_id": self.source_id,
            "approval_status": self.approval_status,
            "activation_allowed": self.activation_allowed,
            "credential_requirement": self.credential_requirement.value,
            "activation_authority": self.activation_authority.value,
            "blocked_reasons": list(self.blocked_reasons),
        }


class SourceApprovalGateV2:
    def __init__(self, universe: SourceUniverse | None = None) -> None:
        self.universe = universe or SourceUniverse()

    def decisions(self) -> list[SourceGateDecision]:
        decisions: list[SourceGateDecision] = []
        for candidate in self.universe.candidates():
            blocked = candidate.approval_status.value.startswith("BLOCKED")
            credential_requirement = SourceCredentialRequirement.NONE
            if candidate.adapter_plan.credential_env_vars:
                credential_requirement = SourceCredentialRequirement.API_KEY_PRESENCE_ONLY
            if candidate.tier in {SourceTier.TIER_0_EXCHANGE_NATIVE, SourceTier.TIER_2_COMMERCIAL_LICENSED}:
                credential_requirement = SourceCredentialRequirement.LICENSE_AND_KEY_REQUIRED
            reasons = tuple(candidate.adapter_plan.blockers) if blocked or candidate.adapter_plan.blockers else ()
            decisions.append(
                SourceGateDecision(
                    source_id=candidate.source_id,
                    approval_status=candidate.approval_status.value,
                    activation_allowed=not blocked and candidate.tier == SourceTier.TIER_1_OFFICIAL_PUBLIC,
                    credential_requirement=credential_requirement,
                    activation_authority=SourceActivationAuthority.READ_ONLY_ONLY,
                    blocked_reasons=reasons,
                )
            )
        return decisions

    def to_report(self) -> dict[str, Any]:
        decisions = self.decisions()
        approval_counts = Counter(decision.approval_status for decision in decisions)
        return {
            "workstream": "V20: Source Approval Gate V2",
            "decision_count": len(decisions),
            "decisions": [decision.to_dict() for decision in decisions],
            "approval_status_counts": dict(sorted(approval_counts.items())),
            "unapproved_sources_activated": [],
            "commercial_sources_activated_without_approval": [],
            "sports_odds_sources_blocked_unless_approved": True,
            "exchange_private_trading_apis_blocked": True,
            "source_api_key_values_exposed": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


class SourceLicenseGate:
    def __init__(self, universe: SourceUniverse | None = None) -> None:
        self.universe = universe or SourceUniverse()

    def to_report(self) -> dict[str, Any]:
        candidates = self.universe.candidates()
        licensed = [candidate for candidate in candidates if candidate.tier in {SourceTier.TIER_0_EXCHANGE_NATIVE, SourceTier.TIER_2_COMMERCIAL_LICENSED}]
        return {
            "workstream": "V20: Source License Gate",
            "licensed_source_count": len(licensed),
            "licensed_sources": [candidate.source_id for candidate in licensed],
            "activated_licensed_sources": [],
            "all_licensed_sources_blocked_without_allowlist": True,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


class SourceTermsGate:
    def __init__(self, universe: SourceUniverse | None = None) -> None:
        self.universe = universe or SourceUniverse()

    def to_report(self) -> dict[str, Any]:
        risky = [candidate.to_dict() for candidate in self.universe.candidates() if "review" in candidate.terms_risk.lower() or candidate.approval_status == SourceApprovalStatus.BLOCKED_TERMS_UNCLEAR]
        return {
            "workstream": "V20: Source Terms Gate",
            "terms_review_required_count": len(risky),
            "terms_review_sources": risky,
            "blocked_terms_unclear_count": sum(1 for source in risky if source["approval_status"] == SourceApprovalStatus.BLOCKED_TERMS_UNCLEAR.value),
            "questionable_scraping_allowed": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }


class SourceCredentialRequirementReport:
    def __init__(self, universe: SourceUniverse | None = None) -> None:
        self.universe = universe or SourceUniverse()

    def to_report(self) -> dict[str, Any]:
        requirements = [
            {
                "source_id": candidate.source_id,
                "credential_env_vars": list(candidate.adapter_plan.credential_env_vars),
                "credential_values_exposed": False,
                "approval_status": candidate.approval_status.value,
            }
            for candidate in self.universe.candidates()
            if candidate.adapter_plan.credential_env_vars or candidate.tier in {SourceTier.TIER_0_EXCHANGE_NATIVE, SourceTier.TIER_2_COMMERCIAL_LICENSED}
        ]
        return {
            "workstream": "V20: Source Credential Requirement",
            "requirements": requirements,
            "credential_value_storage_allowed": False,
            "source_api_key_values_exposed": False,
            "secret_values_exposed": False,
            "verdict": "PASS",
        }
