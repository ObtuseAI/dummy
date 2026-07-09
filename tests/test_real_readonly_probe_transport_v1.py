from __future__ import annotations

from predator_mesh.v36.run import RealReadonlyProbeTransportV1Impl, build_default_v36_state


def test_real_readonly_probe_transport_v1_caps() -> None:
    transport = RealReadonlyProbeTransportV1Impl()
    assert transport.per_request_timeout == 12
    assert transport.total_timeout == 24
    assert transport.request_cap == 4
    assert transport.request_count == 0


def test_real_readonly_probe_transport_v1_only_if_gate_enabled() -> None:
    state = build_default_v36_state(env={})
    report = state["real_readonly_probe_transport_v1"]
    assert report.constructed_only_if_gate_enabled is True


class _StubTransport:
    def fetch_json(self, task, timeout_seconds: int):
        return {"data": {"amount": "65000.00"}, "timestamp": "2026-07-04T00:00:00+00:00"}
