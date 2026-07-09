from __future__ import annotations

from predator_mesh.v32.recovery import OperatorGatedProbeRunV2
from tests.v32_test_helpers import assert_v32_report_named


def test_operator_gated_probe_run_requires_exact_ack() -> None:
    disabled = OperatorGatedProbeRunV2().decide({"DUMMY_PUBLIC_PROBE_MODE": "1", "DUMMY_PUBLIC_PROBE_ACK": "please run"})

    assert disabled.enabled is False
    assert disabled.ack_validation_status == "FAIL_INVALID_ACK"
    assert disabled.run_blocker == "EXACT_READONLY_ACK_REQUIRED"
    assert disabled.no_execution_proof.no_execution_bridge is True


def test_operator_gated_probe_run_enables_only_for_exact_readonly_ack() -> None:
    enabled = OperatorGatedProbeRunV2().decide({
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })

    assert enabled.enabled is True
    assert enabled.gate_state == "ENABLED_READONLY_PUBLIC_PROBES"
    assert enabled.ack_validation_status == "PASS"
    assert enabled.max_requests == 4
    assert enabled.source_families == ["weather", "crypto", "public_event", "kalshi_readonly"]
    assert enabled.no_execution_proof.no_order_cancel_paths is True


def test_operator_gated_probe_run_report_contract() -> None:
    report = assert_v32_report_named("operator_gated_probe_run_v2_report.json", "operator_gated_probe_run_status")
    assert report["operator_gated_probe_run_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["gate_state"] == "DISABLED_BY_DEFAULT"
    assert report["ack_validation_status"] == "FAIL_MISSING_ACK"
