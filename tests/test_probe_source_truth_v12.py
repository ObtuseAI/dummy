from __future__ import annotations

from predator_mesh.v31.probes import ProbeSourceTruthV12, build_default_v31_state
from tests.v31_test_helpers import assert_current_test_report


def test_probe_source_truth_v12_preserves_disabled_default_and_next_action() -> None:
    truth = ProbeSourceTruthV12().evaluate(build_default_v31_state(enable_network=False))

    assert truth.probe_source_truth_v12_status == "PASS_WITH_REMAINING_PARTIALS"
    assert truth.probe_health_truth_signal == "PROBE_GATE_DISABLED_BY_DEFAULT"
    assert truth.public_evidence_truth_signal == "NO_LIVE_PUBLIC_EVIDENCE_CAPTURED"
    assert truth.live_score_truth_signal == "NO_VALID_LIVE_PUBLIC_SCORE_SEED"
    assert truth.probe_source_truth_action_v12 == "operator may enable bounded read-only public probes"
    assert truth.execution_bridge_present is False


def test_probe_source_truth_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["probe_source_truth_v12_status"] == "PASS_WITH_REMAINING_PARTIALS"
    assert report["probe_source_truth_action_v12"] == "operator may enable bounded read-only public probes"
