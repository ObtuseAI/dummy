from __future__ import annotations

from predator_mesh.v36.run import build_default_v36_state


def test_exact_operator_gate_runtime_v5_exact() -> None:
    state = build_default_v36_state(
        env={
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        },
        real_transport=_StubTransport(),
    )
    gate = state["exact_operator_gate_runtime_v5"]
    assert gate.run_decision is True
    assert gate.ack_decision == "EXACT_ACK_VALID"


def test_exact_operator_gate_runtime_v5_missing() -> None:
    state = build_default_v36_state(env={})
    gate = state["exact_operator_gate_runtime_v5"]
    assert gate.run_decision is False
    assert gate.ack_decision == "FAIL_MISSING_ACK"


def test_exact_operator_gate_runtime_v5_fuzzy() -> None:
    state = build_default_v36_state(
        env={
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY",
        }
    )
    gate = state["exact_operator_gate_runtime_v5"]
    assert gate.run_decision is False
    assert gate.ack_decision == "FAIL_MISSING_ACK"


class _StubTransport:
    def fetch_json(self, task, timeout_seconds: int):
        return {"properties": {"temperature": {"value": 25.0}, "timestamp": "2026-07-04T00:00:00+00:00"}}
