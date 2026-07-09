"""V15 real terrain retry gate V2, gated on credential shape + auth."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from predator_mesh.v14.credential_forensics import KalshiCredentialForensics
from predator_mesh.v15.auth_probe_v2 import KalshiAuthProbeDecision, KalshiAuthProbeV2
from predator_mesh.v15.credential_shape_repair import (
    KalshiCredentialShapeRepairEngine,
    KalshiEnvRepairVerdict,
)
from predator_mesh.v15.credential_source_conflict_resolver import KalshiCredentialSourceConflictResolver


class RealTerrainCredentialShapeState(str, Enum):
    SHAPE_VALID = "SHAPE_VALID"
    SHAPE_MALFORMED = "SHAPE_MALFORMED"
    SHAPE_ABSENT = "SHAPE_ABSENT"
    SHAPE_CONFLICTING_SOURCES = "SHAPE_CONFLICTING_SOURCES"


class RealTerrainAuthState(str, Enum):
    NOT_ATTEMPTED = "NOT_ATTEMPTED"
    AUTH_PASS = "AUTH_PASS"
    AUTH_FAIL = "AUTH_FAIL"
    AUTH_TIMEOUT = "AUTH_TIMEOUT"
    AUTH_ENDPOINT_ERROR = "AUTH_ENDPOINT_ERROR"


class RealTerrainRetryDecisionV2(str, Enum):
    RETRY_REAL_READ_ONLY_NOW = "RETRY_REAL_READ_ONLY_NOW"
    BLOCKED_MALFORMED_ENVIRONMENT_VARIABLE = "BLOCKED_MALFORMED_ENVIRONMENT_VARIABLE"
    BLOCKED_CONFLICTING_CREDENTIAL_SOURCES = "BLOCKED_CONFLICTING_CREDENTIAL_SOURCES"
    BLOCKED_AUTH_FAILED = "BLOCKED_AUTH_FAILED"
    BLOCKED_CREDENTIALS_MISSING = "BLOCKED_CREDENTIALS_MISSING"
    BLOCKED_NO_ELIGIBLE_MARKET = "BLOCKED_NO_ELIGIBLE_MARKET"
    USE_SAMPLE_STATIC_FALLBACK = "USE_SAMPLE_STATIC_FALLBACK"
    QUARANTINE_CREDENTIAL_SOURCE = "QUARANTINE_CREDENTIAL_SOURCE"


class RealTerrainRetryGateV2:
    def __init__(
        self,
        *,
        repair_engine: KalshiCredentialShapeRepairEngine | None = None,
        conflict_resolver: KalshiCredentialSourceConflictResolver | None = None,
        auth_probe: KalshiAuthProbeV2 | None = None,
        forensics_report: dict[str, Any] | None = None,
        no_eligible_market: bool = False,
    ) -> None:
        # When only a forensics report is supplied, the gate is report-driven:
        # shape comes from the report and no live auth probe is ever run.
        # Injecting engines/probe explicitly opts into live evaluation.
        self._report_driven = forensics_report is not None and repair_engine is None
        self._auth_probe_injected = auth_probe is not None
        self.repair_engine = repair_engine or KalshiCredentialShapeRepairEngine()
        self.conflict_resolver = conflict_resolver or KalshiCredentialSourceConflictResolver()
        self.auth_probe = auth_probe or KalshiAuthProbeV2(repair_engine=self.repair_engine, conflict_resolver=self.conflict_resolver)
        self.forensics_report = forensics_report or KalshiCredentialForensics().to_report()
        self.no_eligible_market = no_eligible_market

    def _shape_state_from_report(self) -> RealTerrainCredentialShapeState:
        reason = str(self.forensics_report.get("failure_reason", ""))
        if reason == "MALFORMED_ENVIRONMENT_VARIABLE":
            return RealTerrainCredentialShapeState.SHAPE_MALFORMED
        if reason == "CREDENTIALS_MISSING":
            return RealTerrainCredentialShapeState.SHAPE_ABSENT
        if reason in ("", "NONE"):
            return RealTerrainCredentialShapeState.SHAPE_VALID
        return RealTerrainCredentialShapeState.SHAPE_MALFORMED

    def shape_state(self) -> RealTerrainCredentialShapeState:
        if self._report_driven:
            return self._shape_state_from_report()
        verdict = self.repair_engine.verdict()
        if self.conflict_resolver.resolve().has_conflict:
            return RealTerrainCredentialShapeState.SHAPE_CONFLICTING_SOURCES
        if verdict == KalshiEnvRepairVerdict.SHAPE_VALID:
            return RealTerrainCredentialShapeState.SHAPE_VALID
        if verdict == KalshiEnvRepairVerdict.SHAPE_ABSENT:
            return RealTerrainCredentialShapeState.SHAPE_ABSENT
        return RealTerrainCredentialShapeState.SHAPE_MALFORMED

    def auth_state(self) -> RealTerrainAuthState:
        shape = self.shape_state()
        if shape != RealTerrainCredentialShapeState.SHAPE_VALID:
            return RealTerrainAuthState.NOT_ATTEMPTED
        if self._report_driven and not self._auth_probe_injected:
            # Report-driven gates never contact the broker: auth is unknown,
            # so the decision falls through to the sample-static fallback.
            return RealTerrainAuthState.NOT_ATTEMPTED
        outcome = self.auth_probe.run()
        try:
            return RealTerrainAuthState(outcome.decision)
        except ValueError:
            return RealTerrainAuthState.AUTH_ENDPOINT_ERROR

    def decision(self) -> RealTerrainRetryDecisionV2:
        shape = self.shape_state()
        if shape == RealTerrainCredentialShapeState.SHAPE_CONFLICTING_SOURCES:
            return RealTerrainRetryDecisionV2.BLOCKED_CONFLICTING_CREDENTIAL_SOURCES
        if shape == RealTerrainCredentialShapeState.SHAPE_ABSENT:
            return RealTerrainRetryDecisionV2.BLOCKED_CREDENTIALS_MISSING
        if shape == RealTerrainCredentialShapeState.SHAPE_MALFORMED:
            return RealTerrainRetryDecisionV2.BLOCKED_MALFORMED_ENVIRONMENT_VARIABLE

        auth = self.auth_state()
        if auth == RealTerrainAuthState.AUTH_PASS:
            if self.no_eligible_market:
                return RealTerrainRetryDecisionV2.BLOCKED_NO_ELIGIBLE_MARKET
            return RealTerrainRetryDecisionV2.RETRY_REAL_READ_ONLY_NOW
        if auth in {RealTerrainAuthState.AUTH_FAIL, RealTerrainAuthState.AUTH_TIMEOUT, RealTerrainAuthState.AUTH_ENDPOINT_ERROR}:
            return RealTerrainRetryDecisionV2.BLOCKED_AUTH_FAILED
        return RealTerrainRetryDecisionV2.USE_SAMPLE_STATIC_FALLBACK

    def to_report(self) -> dict[str, Any]:
        decision = self.decision()
        should_retry = decision == RealTerrainRetryDecisionV2.RETRY_REAL_READ_ONLY_NOW
        return {
            "workstream": "V15: Real Terrain Retry Gate V2",
            "decision": decision.value,
            "credential_shape_state": self.shape_state().value,
            "auth_state": self.auth_state().value,
            "retry_count": 1 if should_retry else 0,
            "write_endpoints_called": [],
            "order_endpoints_called": [],
            "cancel_endpoints_called": [],
            "secret_values_exposed": False,
            "verdict": "PASS" if should_retry else "PARTIAL",
        }
