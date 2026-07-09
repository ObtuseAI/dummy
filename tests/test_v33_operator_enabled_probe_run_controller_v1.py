from __future__ import annotations

from predator_mesh.v33.run import V33OperatorEnabledProbeRunControllerV1, build_default_v33_state
from tests.v33_test_helpers import assert_v33_report_named


def test_v33_controller_preserves_default_disabled_operator_action() -> None:
    state = build_default_v33_state(enable_network=False)
    result = V33OperatorEnabledProbeRunControllerV1().run(state)

    assert result.operator_enabled_probe_run_controller_status == "PASS_DISABLED_BY_DEFAULT"
    assert result.gate_state == "DISABLED_BY_DEFAULT"
    assert result.exact_ack_validation_status == "FAIL_MISSING_ACK"
    assert result.probe_run_count == 0
    assert result.operator_packet.operator_action.endswith("READ_ONLY_PUBLIC_PROBES_ONLY")
    assert result.safety_proof.no_execution_bridge is True
    assert result.execution_bridge_present is False


def test_v33_controller_enabled_fake_path_runs_bounded_observation_pass() -> None:
    state = build_default_v33_state(enable_network=False, env={
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    result = V33OperatorEnabledProbeRunControllerV1().run(state)

    assert result.operator_enabled_probe_run_controller_status == "PASS_WITH_REMAINING_BLOCKERS"
    assert result.gate_state == "ENABLED_READONLY_PUBLIC_PROBES"
    assert result.exact_ack_validation_status == "PASS"
    assert result.probe_run_count == 3
    assert result.live_public_evidence_packet_count == 3
    assert result.observed_forecast_count == 3
    assert result.live_scored_count == 3
    assert "READONLY_ACCESS_UNAVAILABLE" in result.remaining_blockers
    assert result.execution_bridge_present is False


def test_v33_controller_report_contract() -> None:
    report = assert_v33_report_named(
        "v33_operator_enabled_probe_run_controller_v1_report.json",
        "operator_enabled_probe_run_controller_status",
    )

    assert report["operator_enabled_probe_run_controller_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["probe_run_count"] == 0
    assert report["operator_action_required"] is True
