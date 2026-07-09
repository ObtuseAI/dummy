from __future__ import annotations

from predator_mesh.v15.auth_probe_v2 import KalshiAuthProbeDecision, KalshiAuthProbeV2
from predator_mesh.v15.credential_shape_repair import KalshiCredentialShapeRepairEngine
from predator_mesh.v15.credential_source_conflict_resolver import KalshiCredentialSourceConflictResolver
from predator_mesh.v15.retry_gate_v2 import (
    RealTerrainAuthState,
    RealTerrainCredentialShapeState,
    RealTerrainRetryDecisionV2,
    RealTerrainRetryGateV2,
)
from tests.v15_test_helpers import MALFORMED_BACKSLASH_ENV, MISSING_ENV, VALID_ENV, bridge_with_env, forensics_with_env


def _gate(env: dict[str, str], probe_fn=None, no_eligible_market: bool = False) -> RealTerrainRetryGateV2:
    repair = KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(env))
    resolver = KalshiCredentialSourceConflictResolver(bridge=bridge_with_env(env))
    auth_probe = KalshiAuthProbeV2(repair_engine=repair, conflict_resolver=resolver, probe_fn=probe_fn or (lambda: KalshiAuthProbeDecision.AUTH_FAIL.value))
    return RealTerrainRetryGateV2(repair_engine=repair, conflict_resolver=resolver, auth_probe=auth_probe, no_eligible_market=no_eligible_market)


def test_malformed_shape_blocks() -> None:
    gate = _gate(MALFORMED_BACKSLASH_ENV)
    assert gate.shape_state() in {RealTerrainCredentialShapeState.SHAPE_MALFORMED, RealTerrainCredentialShapeState.SHAPE_CONFLICTING_SOURCES}
    assert gate.decision() in {
        RealTerrainRetryDecisionV2.BLOCKED_MALFORMED_ENVIRONMENT_VARIABLE,
        RealTerrainRetryDecisionV2.BLOCKED_CONFLICTING_CREDENTIAL_SOURCES,
    }


def test_missing_credentials_blocks() -> None:
    gate = _gate(MISSING_ENV)
    assert gate.shape_state() == RealTerrainCredentialShapeState.SHAPE_ABSENT
    assert gate.decision() == RealTerrainRetryDecisionV2.BLOCKED_CREDENTIALS_MISSING
    assert gate.auth_state() == RealTerrainAuthState.NOT_ATTEMPTED


def test_valid_shape_auth_pass_retries_now() -> None:
    gate = _gate(VALID_ENV, probe_fn=lambda: KalshiAuthProbeDecision.AUTH_PASS.value)
    assert gate.shape_state() == RealTerrainCredentialShapeState.SHAPE_VALID
    assert gate.decision() == RealTerrainRetryDecisionV2.RETRY_REAL_READ_ONLY_NOW


def test_valid_shape_auth_fail_blocks() -> None:
    gate = _gate(VALID_ENV, probe_fn=lambda: KalshiAuthProbeDecision.AUTH_FAIL.value)
    assert gate.decision() == RealTerrainRetryDecisionV2.BLOCKED_AUTH_FAILED


def test_no_eligible_market_after_auth_pass() -> None:
    gate = _gate(VALID_ENV, probe_fn=lambda: KalshiAuthProbeDecision.AUTH_PASS.value, no_eligible_market=True)
    assert gate.decision() == RealTerrainRetryDecisionV2.BLOCKED_NO_ELIGIBLE_MARKET


def test_report_never_calls_write_order_cancel() -> None:
    gate = _gate(VALID_ENV, probe_fn=lambda: KalshiAuthProbeDecision.AUTH_PASS.value)
    report = gate.to_report()
    assert report["write_endpoints_called"] == []
    assert report["order_endpoints_called"] == []
    assert report["cancel_endpoints_called"] == []
    assert report["secret_values_exposed"] is False
