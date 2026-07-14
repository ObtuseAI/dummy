from __future__ import annotations


from predator_mesh.v15.auth_probe_v2 import (
    KalshiAuthProbeDecision,
    KalshiAuthProbeV2,
)
from predator_mesh.v15.credential_shape_repair import KalshiCredentialShapeRepairEngine
from predator_mesh.v15.credential_source_conflict_resolver import KalshiCredentialSourceConflictResolver
from tests.v15_test_helpers import MALFORMED_BACKSLASH_ENV, VALID_ENV, bridge_with_env, forensics_with_env


def test_malformed_shape_skips_probe_without_network() -> None:
    probe = KalshiAuthProbeV2(
        repair_engine=KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(MALFORMED_BACKSLASH_ENV)),
        conflict_resolver=KalshiCredentialSourceConflictResolver(bridge=bridge_with_env(MALFORMED_BACKSLASH_ENV)),
        probe_fn=lambda: (_ for _ in ()).throw(AssertionError("must not call network")),
    )
    outcome = probe.run()
    assert outcome.decision == KalshiAuthProbeDecision.SKIP_MALFORMED_SHAPE.value


def test_valid_shape_probes_with_injected_deterministic_fn() -> None:
    probe = KalshiAuthProbeV2(
        repair_engine=KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(VALID_ENV)),
        conflict_resolver=KalshiCredentialSourceConflictResolver(bridge=bridge_with_env(VALID_ENV)),
        probe_fn=lambda: KalshiAuthProbeDecision.AUTH_PASS.value,
    )
    outcome = probe.run()
    assert outcome.decision == KalshiAuthProbeDecision.AUTH_PASS.value
    assert outcome.write_endpoints_called == []
    assert outcome.order_endpoints_called == []
    assert outcome.cancel_endpoints_called == []


def test_probe_never_calls_write_order_cancel_endpoints() -> None:
    probe = KalshiAuthProbeV2(
        repair_engine=KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(VALID_ENV)),
        conflict_resolver=KalshiCredentialSourceConflictResolver(bridge=bridge_with_env(VALID_ENV)),
        probe_fn=lambda: KalshiAuthProbeDecision.AUTH_FAIL.value,
    )
    report = probe.to_report()
    assert report["write_or_order_or_cancel_called"] is False
    assert report["read_only"] is True


def test_probe_enforces_bounded_timeouts_via_injected_clock() -> None:
    ticks = iter([0.0, 0.0, 11.0, 11.0])
    probe = KalshiAuthProbeV2(
        repair_engine=KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(VALID_ENV)),
        conflict_resolver=KalshiCredentialSourceConflictResolver(bridge=bridge_with_env(VALID_ENV)),
        probe_fn=lambda: KalshiAuthProbeDecision.AUTH_PASS.value,
        clock=lambda: next(ticks),
    )
    outcome = probe.run()
    assert outcome.decision == KalshiAuthProbeDecision.AUTH_TIMEOUT.value


def test_probe_endpoint_error_is_classified_not_raised() -> None:
    def boom():
        raise RuntimeError("simulated endpoint error")

    probe = KalshiAuthProbeV2(
        repair_engine=KalshiCredentialShapeRepairEngine(forensics=forensics_with_env(VALID_ENV)),
        conflict_resolver=KalshiCredentialSourceConflictResolver(bridge=bridge_with_env(VALID_ENV)),
        probe_fn=boom,
    )
    outcome = probe.run()
    assert outcome.decision == KalshiAuthProbeDecision.AUTH_ENDPOINT_ERROR.value
