from __future__ import annotations

from predator_mesh.v32.recovery import V32SourceRecoveryControllerV1, build_default_v32_state
from tests.v32_test_helpers import assert_v32_report_named


def test_source_recovery_controller_preserves_disabled_gate_operator_action() -> None:
    state = build_default_v32_state(enable_network=False)
    result = V32SourceRecoveryControllerV1().run(state)

    assert result.source_recovery_controller_status == "PASS_DISABLED_BY_DEFAULT"
    assert result.case_count >= 4
    assert result.attempt_count == 0
    assert result.operator_action_required is True
    assert result.recovery_decisions[0].decision == "OPERATOR_ENABLE_PUBLIC_PROBES"
    assert result.safety_proof.no_execution_bridge is True
    assert result.execution_bridge_present is False


def test_source_recovery_controller_enabled_fake_path_attempts_recovery() -> None:
    state = build_default_v32_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    result = V32SourceRecoveryControllerV1().run(state)

    assert result.source_recovery_controller_status == "PASS_WITH_REMAINING_BLOCKERS"
    assert result.attempt_count == 4
    assert result.operator_action_required is False
    assert "READONLY_ACCESS_UNAVAILABLE" in result.blockers
    assert result.execution_bridge_present is False


def test_source_recovery_controller_report_contract() -> None:
    report = assert_v32_report_named("v32_source_recovery_controller_v1_report.json", "source_recovery_controller_status")
    assert report["source_recovery_controller_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["source_recovery_case_count"] >= 4
    assert report["source_recovery_attempt_count"] == 0
