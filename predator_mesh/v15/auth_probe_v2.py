"""V15 bounded, read-only Kalshi auth probe.

Enforces <=10s per-request timeout, <=45s total budget, and NEVER calls
write/order/cancel endpoints. Read-only auth check only.
"""

from __future__ import annotations

import time
from dataclasses import dataclass
from enum import Enum
from typing import Any, Callable

from predator_mesh.v15.credential_shape_repair import (
    KalshiCredentialShapeRepairEngine,
    KalshiEnvRepairVerdict,
)
from predator_mesh.v15.credential_source_conflict_resolver import KalshiCredentialSourceConflictResolver

PER_REQUEST_TIMEOUT_S = 10.0
TOTAL_BUDGET_S = 45.0


class KalshiAuthProbeDecision(str, Enum):
    SKIP_MALFORMED_SHAPE = "SKIP_MALFORMED_SHAPE"
    SKIP_CONFLICTING_SOURCES = "SKIP_CONFLICTING_SOURCES"
    PROBE_READ_ONLY_AUTH = "PROBE_READ_ONLY_AUTH"
    AUTH_PASS = "AUTH_PASS"
    AUTH_FAIL = "AUTH_FAIL"
    AUTH_TIMEOUT = "AUTH_TIMEOUT"
    AUTH_ENDPOINT_ERROR = "AUTH_ENDPOINT_ERROR"


@dataclass(frozen=True)
class KalshiAuthShapeGate:
    shape_valid: bool
    sources_conflicting: bool

    def allows_probe(self) -> bool:
        return self.shape_valid and not self.sources_conflicting

    def to_dict(self) -> dict[str, Any]:
        return {"shape_valid": self.shape_valid, "sources_conflicting": self.sources_conflicting, "allows_probe": self.allows_probe()}


@dataclass(frozen=True)
class KalshiAuthProbeOutcome:
    decision: str
    elapsed_s: float
    write_endpoints_called: list[str]
    order_endpoints_called: list[str]
    cancel_endpoints_called: list[str]
    read_only: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "decision": self.decision,
            "elapsed_s": self.elapsed_s,
            "read_only": self.read_only,
            "write_endpoints_called": self.write_endpoints_called,
            "order_endpoints_called": self.order_endpoints_called,
            "cancel_endpoints_called": self.cancel_endpoints_called,
            "per_request_timeout_s": PER_REQUEST_TIMEOUT_S,
            "total_budget_s": TOTAL_BUDGET_S,
        }


# Default read-only probe: real bounded read-only call, gated so it only ever
# runs once credential shape + source conflict checks already passed. Tests
# inject a fake probe_fn instead, so this never runs under pytest.
def _default_probe_fn() -> str:
    """Bounded, read-only Kalshi auth probe via KalshiClient.get_account().

    GET /portfolio/balance only. No write/order/cancel endpoint is ever
    called. Returns one of AUTH_PASS / AUTH_FAIL / AUTH_TIMEOUT /
    AUTH_ENDPOINT_ERROR; never raises or leaks response content.
    """
    import asyncio
    from predator_mesh.v13.credential_bridge import KalshiReadOnlyCredentialBridge

    async def _probe() -> str:
        bridge = KalshiReadOnlyCredentialBridge()
        try:
            with bridge.credential_environment_overlay():
                # kalshi.client caches KALSHI_API_BASE/VERSION as module-level
                # constants at first import (which may happen eagerly via the
                # predator_mesh package before this overlay ever runs), so
                # patch the resolved values onto the already-imported module
                # rather than relying on import-time env resolution.
                import kalshi.client as _kalshi_client_mod
                import os as _os

                _kalshi_client_mod.BASE = _os.environ.get("KALSHI_API_BASE", _kalshi_client_mod.BASE).rstrip("/")
                _kalshi_client_mod.VERSION = _os.environ.get("KALSHI_API_VERSION", _kalshi_client_mod.VERSION)
                KalshiClient = _kalshi_client_mod.KalshiClient

                client = KalshiClient()
                try:
                    await asyncio.wait_for(client.get_account(), timeout=PER_REQUEST_TIMEOUT_S)
                finally:
                    await client.close()
            return KalshiAuthProbeDecision.AUTH_PASS.value
        except asyncio.TimeoutError:
            return KalshiAuthProbeDecision.AUTH_TIMEOUT.value
        except Exception as exc:  # noqa: BLE001 - classify, never leak exc content w/ secrets
            status = getattr(getattr(exc, "response", None), "status_code", None)
            if status in (401, 403):
                return KalshiAuthProbeDecision.AUTH_FAIL.value
            return KalshiAuthProbeDecision.AUTH_ENDPOINT_ERROR.value

    return asyncio.run(_probe())


class KalshiAuthProbeV2:
    def __init__(
        self,
        *,
        repair_engine: KalshiCredentialShapeRepairEngine | None = None,
        conflict_resolver: KalshiCredentialSourceConflictResolver | None = None,
        probe_fn: Callable[[], str] | None = None,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self.repair_engine = repair_engine or KalshiCredentialShapeRepairEngine()
        self.conflict_resolver = conflict_resolver or KalshiCredentialSourceConflictResolver()
        self.probe_fn = probe_fn or _default_probe_fn
        self._clock = clock or time.monotonic

    def shape_gate(self) -> KalshiAuthShapeGate:
        shape_valid = self.repair_engine.verdict() == KalshiEnvRepairVerdict.SHAPE_VALID
        conflicting = self.conflict_resolver.resolve().has_conflict
        return KalshiAuthShapeGate(shape_valid=shape_valid, sources_conflicting=conflicting)

    def run(self) -> KalshiAuthProbeOutcome:
        gate = self.shape_gate()
        start = self._clock()
        if not gate.shape_valid:
            return KalshiAuthProbeOutcome(KalshiAuthProbeDecision.SKIP_MALFORMED_SHAPE.value, 0.0, [], [], [])
        if gate.sources_conflicting:
            return KalshiAuthProbeOutcome(KalshiAuthProbeDecision.SKIP_CONFLICTING_SOURCES.value, 0.0, [], [], [])

        request_start = self._clock()
        try:
            decision = self.probe_fn()
        except TimeoutError:
            decision = KalshiAuthProbeDecision.AUTH_TIMEOUT.value
        except Exception:
            decision = KalshiAuthProbeDecision.AUTH_ENDPOINT_ERROR.value
        request_elapsed = self._clock() - request_start
        if request_elapsed > PER_REQUEST_TIMEOUT_S:
            decision = KalshiAuthProbeDecision.AUTH_TIMEOUT.value
        total_elapsed = self._clock() - start
        if total_elapsed > TOTAL_BUDGET_S:
            decision = KalshiAuthProbeDecision.AUTH_TIMEOUT.value

        if decision not in {d.value for d in KalshiAuthProbeDecision}:
            decision = KalshiAuthProbeDecision.AUTH_ENDPOINT_ERROR.value

        return KalshiAuthProbeOutcome(decision, round(total_elapsed, 4), [], [], [])

    def to_report(self) -> dict[str, Any]:
        gate = self.shape_gate()
        outcome = self.run()
        return {
            "workstream": "V15: Kalshi Auth Probe V2",
            "shape_gate": gate.to_dict(),
            "outcome": outcome.to_dict(),
            "read_only": True,
            "write_or_order_or_cancel_called": bool(
                outcome.write_endpoints_called or outcome.order_endpoints_called or outcome.cancel_endpoints_called
            ),
            "secret_values_exposed": False,
            "verdict": "PASS" if outcome.decision == KalshiAuthProbeDecision.AUTH_PASS.value else "PARTIAL",
        }
