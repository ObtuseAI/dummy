from __future__ import annotations

from predator_mesh.v36.run import build_default_v36_state


def test_minimal_real_public_probe_pass_gate_disabled() -> None:
    state = build_default_v36_state(env={})
    pass_result = state["minimal_real_public_probe_pass_v1"]
    assert pass_result.gate_enabled is False
    assert pass_result.probe_run_count == 0
    assert pass_result.blocker is not None


def test_minimal_real_public_probe_pass_gate_enabled_stub() -> None:
    state = build_default_v36_state(
        env={
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        },
        real_transport=_StubTransport(),
    )
    pass_result = state["minimal_real_public_probe_pass_v1"]
    assert pass_result.gate_enabled is True


class _StubTransport:
    def fetch_json(self, task, timeout_seconds: int):
        if task.source_family == "weather":
            return {"properties": {"temperature": {"value": 25.0}, "timestamp": "2026-07-04T00:00:00+00:00"}}
        if task.source_family == "crypto":
            return {"data": {"amount": "65000.00"}, "timestamp": "2026-07-04T00:00:00+00:00"}
        if task.source_family == "public_event":
            return [{"value": 3.0}]
        return {}
