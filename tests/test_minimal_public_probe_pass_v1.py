from __future__ import annotations

from predator_mesh.v32.recovery import MinimalPublicProbePassV1, OperatorGatedProbeRunV2
from tests.v32_test_helpers import assert_v32_report_named


def test_minimal_public_probe_pass_does_not_run_when_gate_disabled() -> None:
    gate = OperatorGatedProbeRunV2().decide({})
    result = MinimalPublicProbePassV1().run(gate)

    assert result.minimal_public_probe_pass_status == "PASS_DISABLED_BY_DEFAULT"
    assert result.probe_run_count == 0
    assert result.failure_count == 0
    assert result.execution_bridge_present is False


def test_minimal_public_probe_pass_runs_small_fake_pass_when_enabled() -> None:
    gate = OperatorGatedProbeRunV2().decide({
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    result = MinimalPublicProbePassV1().run(gate)

    assert result.minimal_public_probe_pass_status == "PASS_WITH_REMAINING_BLOCKERS"
    assert result.probe_run_count == 3
    assert result.failure_count == 1
    assert result.source_family_summary["source_family_count"] == 4
    assert result.safety_summary["execution_bridge_present"] is False


def test_minimal_public_probe_pass_report_contract() -> None:
    report = assert_v32_report_named("minimal_public_probe_pass_v1_report.json", "minimal_public_probe_pass_status")
    assert report["minimal_public_probe_pass_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["probe_run_count"] == 0
