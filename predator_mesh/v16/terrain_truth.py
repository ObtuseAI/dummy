"""Real terrain truth resolver for V16."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any


class RealTerrainTruthVerdict(str, Enum):
    PASS_REAL_TERRAIN = "PASS_REAL_TERRAIN"
    PASS_REAL_TERRAIN_WITH_WARNINGS = "PASS_REAL_TERRAIN_WITH_WARNINGS"
    PARTIAL_CREDENTIALS_MISSING = "PARTIAL_CREDENTIALS_MISSING"
    PARTIAL_CREDENTIALS_INVALID = "PARTIAL_CREDENTIALS_INVALID"
    PARTIAL_CONFIG_BINDING_ERROR = "PARTIAL_CONFIG_BINDING_ERROR"
    PARTIAL_NO_ELIGIBLE_MARKET = "PARTIAL_NO_ELIGIBLE_MARKET"
    PARTIAL_EMPTY_ORDERBOOK = "PARTIAL_EMPTY_ORDERBOOK"
    PARTIAL_ENDPOINT_UNAVAILABLE = "PARTIAL_ENDPOINT_UNAVAILABLE"
    PARTIAL_SAMPLE_STATIC_FALLBACK = "PARTIAL_SAMPLE_STATIC_FALLBACK"
    FAIL_MALFORMED_PIPELINE = "FAIL_MALFORMED_PIPELINE"
    FAIL_TRUTH_MISMATCH = "FAIL_TRUTH_MISMATCH"


@dataclass(frozen=True)
class RealTerrainTruthInput:
    credential_shape_state: str
    auth_probe_state: str
    config_binding_state: str
    market_discovery_state: str
    eligible_market_candidate_count: int
    orderbook_snapshot_state: str
    nonempty_book_proof: bool
    read_only_endpoint_audit: bool
    replay_state: str
    fallback_state: str
    artifact_freshness: str
    downstream_terrain_labels: list[str] | None = None


@dataclass(frozen=True)
class RealTerrainTruthEvidence:
    input: RealTerrainTruthInput
    real_evidence_present: bool

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Real Terrain Truth Evidence",
            "credential_shape_state": self.input.credential_shape_state,
            "auth_probe_state": self.input.auth_probe_state,
            "config_binding_state": self.input.config_binding_state,
            "market_discovery_state": self.input.market_discovery_state,
            "eligible_market_candidate_count": self.input.eligible_market_candidate_count,
            "orderbook_snapshot_state": self.input.orderbook_snapshot_state,
            "nonempty_book_proof": self.input.nonempty_book_proof,
            "read_only_endpoint_audit": self.input.read_only_endpoint_audit,
            "replay_state": self.input.replay_state,
            "fallback_state": self.input.fallback_state,
            "artifact_freshness": self.input.artifact_freshness,
            "real_evidence_present": self.real_evidence_present,
            "secret_values_exposed": False,
            "verdict": "PASS" if self.real_evidence_present else "PARTIAL",
        }


@dataclass(frozen=True)
class RealTerrainTruthMismatch:
    reason: str
    stale_or_wrong_labels: list[str]

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Real Terrain Truth Mismatch",
            "mismatch_detected": True,
            "reason": self.reason,
            "stale_or_wrong_labels": self.stale_or_wrong_labels,
            "secret_values_exposed": False,
            "verdict": "FAIL",
        }


@dataclass(frozen=True)
class RealTerrainTruthResolution:
    verdict: str
    evidence: RealTerrainTruthEvidence
    mismatch: RealTerrainTruthMismatch | None = None
    warnings: list[str] | None = None

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V16: Real Terrain Truth Resolver",
            "terrain_truth_verdict": self.verdict,
            "real_evidence_present": self.evidence.real_evidence_present,
            "mismatch_detected": self.mismatch is not None,
            "mismatch": self.mismatch.to_report() if self.mismatch else None,
            "warnings": self.warnings or [],
            "secret_values_exposed": False,
            "verdict": "FAIL" if self.verdict.startswith("FAIL") else ("PASS" if self.verdict.startswith("PASS") else "PARTIAL"),
        }


class RealTerrainTruthResolver:
    def __init__(self, input: RealTerrainTruthInput) -> None:
        self.input = input

    def resolve(self) -> RealTerrainTruthResolution:
        real_evidence = self._real_evidence_present()
        evidence = RealTerrainTruthEvidence(self.input, real_evidence)
        mismatch_labels = self._mismatch_labels(real_evidence)
        if mismatch_labels:
            mismatch = RealTerrainTruthMismatch(
                reason="Real read-only discovery and nonempty orderbook evidence exists, but a downstream label still claims fallback or malformed terrain.",
                stale_or_wrong_labels=mismatch_labels,
            )
            return RealTerrainTruthResolution(RealTerrainTruthVerdict.FAIL_TRUTH_MISMATCH.value, evidence, mismatch)
        if self.input.credential_shape_state in {"SHAPE_ABSENT", "CREDENTIALS_MISSING"}:
            return self._result(RealTerrainTruthVerdict.PARTIAL_CREDENTIALS_MISSING, evidence)
        if self.input.credential_shape_state in {"SHAPE_MALFORMED", "SHAPE_CONFLICTING_SOURCES"}:
            return self._result(RealTerrainTruthVerdict.PARTIAL_CREDENTIALS_INVALID, evidence)
        if self.input.auth_probe_state in {"AUTH_FAIL", "AUTH_TIMEOUT", "AUTH_ENDPOINT_ERROR"}:
            return self._result(RealTerrainTruthVerdict.PARTIAL_CREDENTIALS_INVALID, evidence)
        if self.input.config_binding_state != "PASS":
            return self._result(RealTerrainTruthVerdict.PARTIAL_CONFIG_BINDING_ERROR, evidence)
        if self.input.market_discovery_state == "PARTIAL_NO_ELIGIBLE_MARKET" or self.input.eligible_market_candidate_count <= 0:
            return self._result(RealTerrainTruthVerdict.PARTIAL_NO_ELIGIBLE_MARKET, evidence)
        if not self.input.read_only_endpoint_audit:
            return self._result(RealTerrainTruthVerdict.PARTIAL_ENDPOINT_UNAVAILABLE, evidence)
        if self.input.orderbook_snapshot_state == "SAMPLE_STATIC_FALLBACK":
            return self._result(RealTerrainTruthVerdict.PARTIAL_SAMPLE_STATIC_FALLBACK, evidence)
        if not self.input.nonempty_book_proof:
            return self._result(RealTerrainTruthVerdict.PARTIAL_EMPTY_ORDERBOOK, evidence)
        if (
            self.input.market_discovery_state == "REAL_READ_ONLY_DISCOVERY"
            and self.input.eligible_market_candidate_count > 0
            and self.input.orderbook_snapshot_state == "REAL_READ_ONLY_DEGRADED"
            and self.input.nonempty_book_proof
        ):
            return RealTerrainTruthResolution(
                RealTerrainTruthVerdict.PASS_REAL_TERRAIN_WITH_WARNINGS.value,
                evidence,
                warnings=["REAL_ORDERBOOK_DEGRADED_NONEMPTY"],
            )
        if real_evidence:
            warnings = [] if self.input.artifact_freshness == "FRESH" else ["ARTIFACT_FRESHNESS_WARNING"]
            verdict = RealTerrainTruthVerdict.PASS_REAL_TERRAIN_WITH_WARNINGS if warnings else RealTerrainTruthVerdict.PASS_REAL_TERRAIN
            return RealTerrainTruthResolution(verdict.value, evidence, warnings=warnings)
        return self._result(RealTerrainTruthVerdict.FAIL_MALFORMED_PIPELINE, evidence)

    def _result(self, verdict: RealTerrainTruthVerdict, evidence: RealTerrainTruthEvidence) -> RealTerrainTruthResolution:
        return RealTerrainTruthResolution(verdict.value, evidence)

    def _real_evidence_present(self) -> bool:
        return (
            self.input.credential_shape_state == "SHAPE_VALID"
            and self.input.auth_probe_state == "AUTH_PASS"
            and self.input.config_binding_state == "PASS"
            and self.input.market_discovery_state == "REAL_READ_ONLY_DISCOVERY"
            and self.input.eligible_market_candidate_count > 0
            and self.input.orderbook_snapshot_state in {"REAL_READ_ONLY", "REAL_READ_ONLY_DEGRADED"}
            and self.input.nonempty_book_proof
            and self.input.read_only_endpoint_audit
        )

    def _mismatch_labels(self, real_evidence: bool) -> list[str]:
        if not real_evidence:
            return []
        labels = [self.input.fallback_state, *(self.input.downstream_terrain_labels or [])]
        bad_markers = ("SAMPLE_STATIC_FALLBACK", "FAIL_MALFORMED_PIPELINE")
        return [label for label in labels if any(marker in label for marker in bad_markers)]
