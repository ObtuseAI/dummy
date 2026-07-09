from __future__ import annotations

from predator_mesh.v34.run import PublicProbeTransportGuardV1


def test_transport_guard_returns_none_when_gate_disabled() -> None:
    guard = PublicProbeTransportGuardV1().select(gate_enabled=False, enable_network=False)

    assert guard.mode == PublicProbeTransportGuardV1.NONE
    assert guard.network_enabled is False
    assert guard.transport_class == "NoTransport"
    assert guard.execution_bridge_present is False


def test_transport_guard_returns_fake_when_enabled_and_no_network() -> None:
    guard = PublicProbeTransportGuardV1().select(gate_enabled=True, enable_network=False)

    assert guard.mode == PublicProbeTransportGuardV1.FAKE
    assert guard.network_enabled is False
    assert guard.transport_class == "FakePublicProbeTransportV1"


def test_transport_guard_returns_real_readonly_when_network_enabled() -> None:
    guard = PublicProbeTransportGuardV1().select(gate_enabled=True, enable_network=True)

    assert guard.mode == PublicProbeTransportGuardV1.REAL_READONLY
    assert guard.network_enabled is True
    assert guard.transport_class == "HttpJsonPublicProbeTransportV1"


def test_transport_guard_transport_for_none_is_none() -> None:
    state = PublicProbeTransportGuardV1().select(gate_enabled=False)

    assert PublicProbeTransportGuardV1().transport_for(state) is None
