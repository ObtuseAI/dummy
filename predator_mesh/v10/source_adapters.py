"""V10 bounded source-adapter promotion contracts."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class SourceAdapterMode(str, Enum):
    LIVE_PUBLIC_BOUNDED = "LIVE_PUBLIC_BOUNDED"
    SAMPLE_STATIC = "SAMPLE_STATIC"
    MOCK_ONLY_EXPLICIT = "MOCK_ONLY_EXPLICIT"


@dataclass(frozen=True)
class SourceAdapterCapability:
    name: str
    bounded_request_path: bool
    requires_secret: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "bounded_request_path": self.bounded_request_path,
            "requires_secret": self.requires_secret,
        }


@dataclass(frozen=True)
class SourceAdapterProof:
    proof_reference: str
    timeout_status: str
    legality_status: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "proof_reference": self.proof_reference,
            "timeout_status": self.timeout_status,
            "legality_status": self.legality_status,
        }


@dataclass(frozen=True)
class SourceAdapterRiskIntelligence:
    freshness: float
    latency_ms: float
    reliability: float
    uniqueness: float
    edge_contribution_placeholder: float

    def to_dict(self) -> dict[str, Any]:
        return {
            "freshness": self.freshness,
            "latency_ms": self.latency_ms,
            "reliability": self.reliability,
            "uniqueness": self.uniqueness,
            "edge_contribution_placeholder": self.edge_contribution_placeholder,
        }


@dataclass(frozen=True)
class SourceAdapterCandidate:
    source_name: str
    source_category: str
    mode: SourceAdapterMode
    capability: SourceAdapterCapability
    risk_intelligence: SourceAdapterRiskIntelligence
    proof: SourceAdapterProof
    timeout_s: float

    @property
    def legality_status(self) -> str:
        return self.proof.legality_status

    @property
    def proof_reference(self) -> str:
        return self.proof.proof_reference

    def to_manifest_entry(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_category": self.source_category,
            "mode": self.mode.value,
            "freshness": self.risk_intelligence.freshness,
            "latency_ms": self.risk_intelligence.latency_ms,
            "reliability": self.risk_intelligence.reliability,
            "uniqueness": self.risk_intelligence.uniqueness,
            "edge_contribution_placeholder": self.risk_intelligence.edge_contribution_placeholder,
            "compliance_source_legality_status": self.legality_status,
            "timeout_status": self.proof.timeout_status,
            "timeout_s": self.timeout_s,
            "proof_reference": self.proof_reference,
        }


@dataclass(frozen=True)
class SourceAdapterPromotionDecision:
    source_name: str
    source_category: str
    mode: SourceAdapterMode
    decision: str
    reason: str
    proof_reference: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "source_name": self.source_name,
            "source_category": self.source_category,
            "mode": self.mode.value,
            "decision": self.decision,
            "reason": self.reason,
            "proof_reference": self.proof_reference,
        }


class SourceAdapterPromotionEngine:
    def discover_candidates(self) -> list[SourceAdapterCandidate]:
        return [
            SourceAdapterCandidate(
                source_name="btc_public_price_volatility",
                source_category="crypto_btc",
                mode=SourceAdapterMode.LIVE_PUBLIC_BOUNDED,
                capability=SourceAdapterCapability("bounded_public_metadata", True),
                risk_intelligence=SourceAdapterRiskIntelligence(0.92, 120.0, 0.83, 0.76, 0.70),
                proof=SourceAdapterProof("source-adapter-proof-btc-public", "BOUNDED", "PUBLIC_ALLOWED"),
                timeout_s=8.0,
            ),
            SourceAdapterCandidate(
                source_name="macro_calendar_static_metadata",
                source_category="macro_calendar",
                mode=SourceAdapterMode.SAMPLE_STATIC,
                capability=SourceAdapterCapability("static_public_calendar_shape", True),
                risk_intelligence=SourceAdapterRiskIntelligence(0.58, 3.0, 0.72, 0.62, 0.48),
                proof=SourceAdapterProof("source-adapter-proof-macro-static", "BOUNDED", "PUBLIC_ALLOWED"),
                timeout_s=2.0,
            ),
            SourceAdapterCandidate(
                source_name="weather_public_sample",
                source_category="weather",
                mode=SourceAdapterMode.SAMPLE_STATIC,
                capability=SourceAdapterCapability("static_public_weather_shape", True),
                risk_intelligence=SourceAdapterRiskIntelligence(0.54, 4.0, 0.68, 0.60, 0.44),
                proof=SourceAdapterProof("source-adapter-proof-weather-sample", "BOUNDED", "PUBLIC_ALLOWED"),
                timeout_s=2.0,
            ),
            SourceAdapterCandidate(
                source_name="sports_schedule_static",
                source_category="sports_schedule",
                mode=SourceAdapterMode.SAMPLE_STATIC,
                capability=SourceAdapterCapability("static_public_schedule_shape", True),
                risk_intelligence=SourceAdapterRiskIntelligence(0.50, 4.0, 0.66, 0.55, 0.40),
                proof=SourceAdapterProof("source-adapter-proof-sports-static", "BOUNDED", "PUBLIC_ALLOWED"),
                timeout_s=2.0,
            ),
            SourceAdapterCandidate(
                source_name="prediction_market_cross_price_explicit_mock",
                source_category="prediction_market_cross_price",
                mode=SourceAdapterMode.MOCK_ONLY_EXPLICIT,
                capability=SourceAdapterCapability("explicit_mock_cross_price_shape", True),
                risk_intelligence=SourceAdapterRiskIntelligence(0.30, 1.0, 0.42, 0.50, 0.30),
                proof=SourceAdapterProof("source-adapter-proof-cross-price-mock", "BOUNDED", "PUBLIC_ALLOWED"),
                timeout_s=1.0,
            ),
        ]

    def promotion_decisions(self) -> list[SourceAdapterPromotionDecision]:
        decisions: list[SourceAdapterPromotionDecision] = []
        for candidate in self.discover_candidates():
            if candidate.mode is SourceAdapterMode.LIVE_PUBLIC_BOUNDED:
                decision = "PROMOTE"
                reason = "Bounded public metadata path with no secret requirement."
            elif candidate.mode is SourceAdapterMode.SAMPLE_STATIC:
                decision = "KEEP_SAMPLE"
                reason = "Safe static sample retained until a supported public dependency exists."
            else:
                decision = "KEEP_MOCK_EXPLICIT"
                reason = "Explicit mock retained because no approved public source is configured."
            decisions.append(
                SourceAdapterPromotionDecision(
                    source_name=candidate.source_name,
                    source_category=candidate.source_category,
                    mode=candidate.mode,
                    decision=decision,
                    reason=reason,
                    proof_reference=candidate.proof_reference,
                )
            )
        return decisions

    def candidate_manifest(self) -> dict[str, Any]:
        candidates = self.discover_candidates()
        return {
            "workstream": "V10: Source Adapter Candidate Manifest",
            "candidate_count": len(candidates),
            "candidates": [candidate.to_manifest_entry() for candidate in candidates],
            "verdict": "PASS" if candidates else "FAIL",
        }

    def mode_report(self) -> dict[str, Any]:
        candidates = self.discover_candidates()
        counts = {mode.value: 0 for mode in SourceAdapterMode}
        for candidate in candidates:
            counts[candidate.mode.value] += 1
        partial = counts[SourceAdapterMode.SAMPLE_STATIC.value] > 0 or counts[SourceAdapterMode.MOCK_ONLY_EXPLICIT.value] > 0
        return {
            "workstream": "V10: Source Adapter Modes",
            "mode_counts": counts,
            "partial_reason": "sample_or_mock_adapters_remaining" if partial else "",
            "verdict": "PARTIAL" if partial else "PASS",
        }

    def timeout_report(self) -> dict[str, Any]:
        candidates = self.discover_candidates()
        entries = [
            {
                "source_name": candidate.source_name,
                "source_category": candidate.source_category,
                "mode": candidate.mode.value,
                "timeout_s": candidate.timeout_s,
                "timeout_status": candidate.proof.timeout_status,
            }
            for candidate in candidates
        ]
        return {
            "workstream": "V10: Source Adapter Timeouts",
            "max_timeout_s": max((candidate.timeout_s for candidate in candidates), default=0),
            "adapters": entries,
            "verdict": "PASS"
            if candidates and all(candidate.timeout_s <= 10 and candidate.proof.timeout_status == "BOUNDED" for candidate in candidates)
            else "FAIL",
        }

    def to_report(self) -> dict[str, Any]:
        candidates = self.discover_candidates()
        decisions = self.promotion_decisions()
        return {
            "workstream": "V10: Source Adapter Promotion Engine",
            "candidate_count": len(candidates),
            "promoted_count": sum(1 for decision in decisions if decision.decision == "PROMOTE"),
            "sample_count": sum(1 for decision in decisions if decision.decision == "KEEP_SAMPLE"),
            "mock_explicit_count": sum(1 for decision in decisions if decision.decision == "KEEP_MOCK_EXPLICIT"),
            "candidates": [candidate.to_manifest_entry() for candidate in candidates],
            "decisions": [decision.to_dict() for decision in decisions],
            "verdict": "PASS" if candidates and decisions else "FAIL",
        }
