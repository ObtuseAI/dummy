from __future__ import annotations

from predator_mesh.v31.probes import (
    ExplicitPublicProbeOperatorGateV3,
    FakePublicProbeTransportV1,
    V30AdapterPublicProbeRunnerV1,
)
from tests.v31_test_helpers import assert_v31_report_named


def test_probe_runner_does_not_run_when_gate_is_disabled() -> None:
    gate = ExplicitPublicProbeOperatorGateV3().decide({})
    result = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(gate)

    assert result.status == "PROBE_DISABLED"
    assert result.planned_task_count == 4
    assert result.probe_run_count == 0
    assert result.probe_failure_count == 0
    assert result.execution_bridge_present is False
    assert result.results == []


def test_probe_runner_executes_only_bounded_readonly_tasks_when_gate_enabled() -> None:
    gate = ExplicitPublicProbeOperatorGateV3().decide(
        {
            "DUMMY_PUBLIC_PROBE_MODE": "1",
            "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
        }
    )
    result = V30AdapterPublicProbeRunnerV1(transport=FakePublicProbeTransportV1()).run(gate)

    assert result.status == "PASS_READONLY_PROBES"
    assert result.planned_task_count == 4
    assert result.probe_run_count == 3
    assert result.probe_failure_count == 1
    assert result.source_family_count == 4
    assert result.execution_bridge_present is False
    assert all(item.read_only is True for item in result.results)
    assert all(item.source_api_key_required is False for item in result.results)
    assert all(item.order_endpoint_used is False for item in result.results)
    assert {failure.blocker for failure in result.failures} == {"READONLY_ACCESS_UNAVAILABLE"}


def test_v30_adapter_public_probe_runner_report_contract() -> None:
    report = assert_v31_report_named("v30_adapter_public_probe_runner_v1_report.json", "public_probe_runner_status")
    assert report["public_probe_runner_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["probe_run_count"] == 0
    assert report["probe_failure_count"] == 0
    assert report["public_probe_gate_state"] == "DISABLED_BY_DEFAULT"
