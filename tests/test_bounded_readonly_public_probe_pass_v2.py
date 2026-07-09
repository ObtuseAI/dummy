from __future__ import annotations

from predator_mesh.v34.run import BoundedReadonlyPublicProbePassV2, ExactGateAcknowledgementHardeningV4
from tests.v34_test_helpers import assert_v34_report_named


def test_bounded_readonly_public_probe_pass_does_not_run_when_gate_disabled() -> None:
    gate = ExactGateAcknowledgementHardeningV4().validate({})
    result = BoundedReadonlyPublicProbePassV2().run(gate)

    assert result.minimal_live_public_probe_execution_status == "PASS_DISABLED_BY_DEFAULT"
    assert result.probe_run_count == 0
    assert result.network_probe_attempted is False
    assert result.execution_bridge_present is False


def test_bounded_readonly_public_probe_pass_runs_small_fake_pass_when_enabled() -> None:
    gate = ExactGateAcknowledgementHardeningV4().validate({
        "DUMMY_PUBLIC_PROBE_MODE": "1",
        "DUMMY_PUBLIC_PROBE_ACK": "READ_ONLY_PUBLIC_PROBES_ONLY",
    })
    result = BoundedReadonlyPublicProbePassV2().run(gate)

    assert result.minimal_live_public_probe_execution_status == "PASS_WITH_REMAINING_BLOCKERS"
    assert result.probe_run_count == 3
    assert result.failure_count == 1
    assert result.source_family_count == 4
    assert result.budget.max_requests == 4
    assert result.safety_proof.no_order_cancel_paths is True


def test_bounded_readonly_public_probe_pass_report_contract() -> None:
    report = assert_v34_report_named("bounded_readonly_public_probe_pass_v2_report.json", "minimal_live_public_probe_execution_status")

    assert report["minimal_live_public_probe_execution_status"] == "PASS_DISABLED_BY_DEFAULT"
    assert report["probe_run_count"] == 0
