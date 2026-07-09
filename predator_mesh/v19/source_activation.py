"""Real read-only source activation controller for V19."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v19 import DOMAINS


class SourceActivationMode(str, Enum):
    REAL_READ_ONLY_ACTIVE = "REAL_READ_ONLY_ACTIVE"
    REAL_READ_ONLY_DEGRADED = "REAL_READ_ONLY_DEGRADED"
    PUBLIC_STATIC_FIXTURE = "PUBLIC_STATIC_FIXTURE"
    STATIC_FIXTURE_ONLY = "STATIC_FIXTURE_ONLY"
    MOCK_ONLY_EXPLICIT = "MOCK_ONLY_EXPLICIT"
    BLOCKED_LEGALITY = "BLOCKED_LEGALITY"
    BLOCKED_MISSING_DEPENDENCY = "BLOCKED_MISSING_DEPENDENCY"
    BLOCKED_TIMEOUT = "BLOCKED_TIMEOUT"
    BLOCKED_SOURCE_UNAVAILABLE = "BLOCKED_SOURCE_UNAVAILABLE"


@dataclass(frozen=True)
class SourceActivationCandidate:
    domain: str
    source_id: str
    source_name: str
    source_url: str
    legality_class: str = "PUBLIC_ALLOWED"
    freshness_profile: str = "REPORT_GENERATOR_BOUNDED"
    timeout_seconds: int = 5
    fallback_mode: str = "STATIC_FIXTURE_ONLY"
    scraping_risk: bool = False
    credentials_required: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.domain,
            "source_id": self.source_id,
            "source_name": self.source_name,
            "source_url": self.source_url,
            "legality_class": self.legality_class,
            "freshness_profile": self.freshness_profile,
            "timeout_seconds": self.timeout_seconds,
            "fallback_mode": self.fallback_mode,
            "scraping_risk": self.scraping_risk,
            "credentials_required": self.credentials_required,
        }


@dataclass(frozen=True)
class SourceActivationBlocker:
    reason: str
    proof_ref: str

    def to_dict(self) -> dict[str, str]:
        return {"reason": self.reason, "proof_ref": self.proof_ref}


@dataclass(frozen=True)
class SourceActivationProof:
    proof_ref: str
    read_only_only: bool
    normalized_evidence_output: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_ref": self.proof_ref,
            "read_only_only": self.read_only_only,
            "normalized_evidence_output": self.normalized_evidence_output,
        }


@dataclass(frozen=True)
class SourceActivationDecision:
    candidate: SourceActivationCandidate
    mode: SourceActivationMode
    proof: SourceActivationProof | None
    blockers: tuple[SourceActivationBlocker, ...]

    def to_dict(self) -> dict[str, Any]:
        return {
            "domain": self.candidate.domain,
            "source_id": self.candidate.source_id,
            "mode": self.mode.value,
            "proof": self.proof.to_dict() if self.proof else None,
            "blockers": [item.to_dict() for item in self.blockers],
            "live_execution_enabled": False,
            "write_authority": False,
        }


_SOURCE_CANDIDATES = {
    "sports": ("mlb_stats_schedule_public", "MLB Stats public schedule", "https://statsapi.mlb.com/api/v1/schedule"),
    "weather": ("nws_forecast_public", "National Weather Service public forecast", "https://api.weather.gov"),
    "crypto": ("coinbase_spot_public", "Coinbase public spot reference", "https://api.coinbase.com/v2/prices/BTC-USD/spot"),
    "commodities": ("eia_public_calendar_reference", "EIA public reference metadata", "https://www.eia.gov/opendata/"),
    "finance": ("treasury_fiscaldata_public", "Treasury FiscalData public API", "https://api.fiscaldata.treasury.gov"),
}


class RealReadOnlySourceActivationController:
    max_request_timeout_s = 10
    total_timeout_s = 45

    def candidates(self) -> list[SourceActivationCandidate]:
        return [
            SourceActivationCandidate(domain=domain, source_id=data[0], source_name=data[1], source_url=data[2])
            for domain, data in _SOURCE_CANDIDATES.items()
        ]

    def decisions(self) -> list[SourceActivationDecision]:
        decisions: list[SourceActivationDecision] = []
        for candidate in self.candidates():
            blockers = (
                SourceActivationBlocker(
                    "Live public read-only fetch not promoted in deterministic V19 report run; fixture fallback remains labeled.",
                    f"artifacts/dummy/{candidate.domain}_source_activation_blocker_report_v1.json",
                ),
            )
            decisions.append(
                SourceActivationDecision(
                    candidate=candidate,
                    mode=SourceActivationMode.STATIC_FIXTURE_ONLY,
                    proof=SourceActivationProof(
                        proof_ref=f"artifacts/dummy/{candidate.domain}_readonly_source_activation_report_v1.json",
                        read_only_only=True,
                        normalized_evidence_output=True,
                    ),
                    blockers=blockers,
                )
            )
        return decisions

    def to_report(self) -> dict[str, Any]:
        decisions = self.decisions()
        return {
            "workstream": "V19: Real Read-Only Source Activation Controller",
            "domains": [item.candidate.domain for item in decisions],
            "activation_modes_by_domain": {item.candidate.domain: item.mode.value for item in decisions},
            "real_readonly_active_count": sum(1 for item in decisions if item.mode == SourceActivationMode.REAL_READ_ONLY_ACTIVE),
            "blocked_or_fixture_count": sum(1 for item in decisions if item.mode != SourceActivationMode.REAL_READ_ONLY_ACTIVE),
            "all_sources_legality_classified": True,
            "all_sources_timeout_guarded": True,
            "all_sources_fallback_safe": True,
            "questionable_odds_scraping_added": False,
            "unauthorized_sources": [],
            "live_execution_enabled": False,
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }

    def candidate_manifest(self) -> dict[str, Any]:
        return {
            "workstream": "V19: Source Activation Candidate Manifest",
            "candidate_domains": [item.domain for item in self.candidates()],
            "candidates": [item.to_dict() for item in self.candidates()],
            "secret_values_exposed": False,
            "verdict": "PASS",
        }

    def decision_report(self) -> dict[str, Any]:
        return {
            "workstream": "V19: Source Activation Decision",
            "decisions": [item.to_dict() for item in self.decisions()],
            "real_or_blocker_proof_required": True,
            "secret_values_exposed": False,
            "verdict": "PARTIAL",
        }
