"""V15 real orderbook terrain closure V3.

CRITICAL invariant: never returns PASS_REAL_TERRAIN unless the underlying
snapshot's mode is provably REAL_READ_ONLY (checked from the actual
OrderbookSnapshotMode on the resolved closure, not merely a label).
"""

from __future__ import annotations

from typing import Any

from predator_mesh.v12.orderbook_snapshot import OrderbookSnapshotMode
from predator_mesh.v14.credential_forensics import KalshiCredentialForensics
from predator_mesh.v14.terrain_closure import RealOrderbookTerrainClosureV2
from predator_mesh.v15.retry_gate_v2 import RealTerrainRetryDecisionV2, RealTerrainRetryGateV2


class RealOrderbookTerrainClosureV3:
    def __init__(
        self,
        *,
        forensics_report: dict[str, Any] | None = None,
        retry_gate: RealTerrainRetryGateV2 | None = None,
        inner: RealOrderbookTerrainClosureV2 | None = None,
    ) -> None:
        self.forensics_report = forensics_report or KalshiCredentialForensics().to_report()
        self.retry_gate = retry_gate or RealTerrainRetryGateV2(forensics_report=self.forensics_report)
        self.inner = inner or RealOrderbookTerrainClosureV2(forensics_report=self.forensics_report)

    def terrain_mode(self) -> str:
        decision = self.retry_gate.decision()
        closure = self.inner._closure_or_fallback()  # noqa: SLF001
        real_mode_proven = closure.snapshot_result.mode is OrderbookSnapshotMode.REAL_READ_ONLY

        if decision == RealTerrainRetryDecisionV2.BLOCKED_MALFORMED_ENVIRONMENT_VARIABLE:
            return "PARTIAL_MALFORMED_ENVIRONMENT_VARIABLE"
        if decision == RealTerrainRetryDecisionV2.BLOCKED_CONFLICTING_CREDENTIAL_SOURCES:
            return "PARTIAL_CONFLICTING_CREDENTIAL_SOURCES"
        if decision == RealTerrainRetryDecisionV2.BLOCKED_CREDENTIALS_MISSING:
            return "PARTIAL_CREDENTIALS_MISSING"
        if decision == RealTerrainRetryDecisionV2.BLOCKED_AUTH_FAILED:
            return "PARTIAL_CREDENTIALS_INVALID"
        if decision == RealTerrainRetryDecisionV2.BLOCKED_NO_ELIGIBLE_MARKET:
            return "PARTIAL_NO_ELIGIBLE_MARKET"
        if decision == RealTerrainRetryDecisionV2.RETRY_REAL_READ_ONLY_NOW:
            # Provably real only if the actual snapshot mode is REAL_READ_ONLY;
            # never claim PASS_REAL_TERRAIN off the decision label alone.
            if real_mode_proven:
                return "PASS_REAL_TERRAIN"
            return "FAIL_MALFORMED_PIPELINE"
        # USE_SAMPLE_STATIC_FALLBACK / QUARANTINE_CREDENTIAL_SOURCE
        if real_mode_proven:
            # Contradiction: fallback decision but real data used - treat as
            # pipeline malformation, never silently upgrade to PASS.
            return "FAIL_MALFORMED_PIPELINE"
        return "PASS_SAMPLE_FALLBACK"

    def to_report(self) -> dict[str, Any]:
        mode = self.terrain_mode()
        closure = self.inner._closure_or_fallback()  # noqa: SLF001
        real_mode_proven = closure.snapshot_result.mode is OrderbookSnapshotMode.REAL_READ_ONLY
        return {
            "workstream": "V15: Real Orderbook Terrain Closure V3",
            "terrain_mode": mode,
            "retry_decision": self.retry_gate.decision().value,
            "credential_shape_state": self.retry_gate.shape_state().value,
            "auth_state": self.retry_gate.auth_state().value,
            "real_orderbook_snapshot_mode": closure.snapshot_result.mode.value,
            "real_terrain_provably_used": real_mode_proven,
            "sample_fallback_used": not real_mode_proven,
            "secret_values_exposed": False,
            "verdict": "PASS" if mode.startswith("PASS") else ("FAIL" if mode.startswith("FAIL") else "PARTIAL"),
        }
