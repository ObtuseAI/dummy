"""V14 real-terrain retry gate."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v14.credential_forensics import KalshiCredentialForensics


class RealTerrainRetryDecision(str, Enum):
    RETRY_REAL_READ_ONLY_NOW = "RETRY_REAL_READ_ONLY_NOW"
    BLOCKED_CREDENTIALS_INVALID = "BLOCKED_CREDENTIALS_INVALID"
    BLOCKED_CREDENTIALS_MISSING = "BLOCKED_CREDENTIALS_MISSING"
    BLOCKED_NO_ELIGIBLE_MARKET = "BLOCKED_NO_ELIGIBLE_MARKET"
    USE_SAMPLE_STATIC_FALLBACK = "USE_SAMPLE_STATIC_FALLBACK"
    QUARANTINE_CREDENTIAL_SOURCE = "QUARANTINE_CREDENTIAL_SOURCE"


class RealTerrainReadinessState(str, Enum):
    READY_FOR_REAL_READ_ONLY_RETRY = "READY_FOR_REAL_READ_ONLY_RETRY"
    BLOCKED_CREDENTIALS_INVALID = "BLOCKED_CREDENTIALS_INVALID"
    BLOCKED_CREDENTIALS_MISSING = "BLOCKED_CREDENTIALS_MISSING"
    BLOCKED_NO_ELIGIBLE_MARKET = "BLOCKED_NO_ELIGIBLE_MARKET"
    SAMPLE_STATIC_FALLBACK = "SAMPLE_STATIC_FALLBACK"


@dataclass(frozen=True)
class RealTerrainReadiness:
    state: RealTerrainReadinessState
    real_terrain_ready: bool
    blockers: list[str]

    def to_report(self) -> dict[str, Any]:
        return {
            "workstream": "V14: Real Terrain Readiness State",
            "state": self.state.value,
            "real_terrain_ready": self.real_terrain_ready,
            "blockers": self.blockers,
            "verdict": "PASS" if self.real_terrain_ready else "PARTIAL",
        }


class RealTerrainRetryGate:
    def __init__(self, *, forensics_report: dict[str, Any] | None = None) -> None:
        self.forensics_report = forensics_report

    def _forensics(self) -> dict[str, Any]:
        return self.forensics_report or KalshiCredentialForensics().to_report()

    def _decision(self, forensics: dict[str, Any]) -> RealTerrainRetryDecision:
        reason = forensics.get("failure_reason", "CREDENTIALS_MISSING")
        if forensics.get("credentials_valid_for_retry") is True:
            return RealTerrainRetryDecision.RETRY_REAL_READ_ONLY_NOW
        if reason == "CREDENTIALS_MISSING":
            return RealTerrainRetryDecision.BLOCKED_CREDENTIALS_MISSING
        if reason in {"MALFORMED_ENVIRONMENT_VARIABLE", "UNSUPPORTED_PRIVATE_KEY_ENCODING"}:
            return RealTerrainRetryDecision.BLOCKED_CREDENTIALS_INVALID
        return RealTerrainRetryDecision.BLOCKED_CREDENTIALS_INVALID

    def readiness_state(self) -> RealTerrainReadiness:
        forensics = self._forensics()
        decision = self._decision(forensics)
        if decision is RealTerrainRetryDecision.RETRY_REAL_READ_ONLY_NOW:
            return RealTerrainReadiness(RealTerrainReadinessState.READY_FOR_REAL_READ_ONLY_RETRY, True, [])
        if decision is RealTerrainRetryDecision.BLOCKED_CREDENTIALS_MISSING:
            return RealTerrainReadiness(RealTerrainReadinessState.BLOCKED_CREDENTIALS_MISSING, False, ["CREDENTIALS_MISSING"])
        return RealTerrainReadiness(RealTerrainReadinessState.BLOCKED_CREDENTIALS_INVALID, False, ["CREDENTIALS_INVALID"])

    def to_report(self) -> dict[str, Any]:
        forensics = self._forensics()
        decision = self._decision(forensics)
        should_retry = decision is RealTerrainRetryDecision.RETRY_REAL_READ_ONLY_NOW
        return {
            "workstream": "V14: Real Terrain Retry Gate",
            "decision": decision.value,
            "retry_count": 1 if should_retry else 0,
            "write_endpoints_called": [],
            "order_endpoints_called": [],
            "cancel_endpoints_called": [],
            "failure_reason": forensics.get("failure_reason", "CREDENTIALS_MISSING"),
            "secret_values_exposed": False,
            "verdict": "PASS" if should_retry else "PARTIAL",
        }
