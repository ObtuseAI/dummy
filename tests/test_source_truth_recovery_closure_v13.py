from __future__ import annotations

from predator_mesh.v32.recovery import SourceTruthRecoveryClosureV13, build_default_v32_state
from tests.v32_test_helpers import assert_current_test_report


def test_source_truth_recovery_closure_v13_preserves_default_partial_truth() -> None:
    truth = SourceTruthRecoveryClosureV13().evaluate(build_default_v32_state(enable_network=False))

    assert truth.source_truth_recovery_closure_v13_status == "PASS_WITH_REMAINING_PARTIALS"
    assert truth.source_recovery_truth_signal == "GATE_DISABLED_RECOVERY_PLANNED"
    assert truth.probe_run_truth_signal == "NO_PROBE_RUN_DEFAULT_DISABLED"
    assert truth.live_score_truth_signal == "NO_VALID_LIVE_PUBLIC_SCORE_EXPANSION"
    assert truth.source_truth_recovery_action_v13 == "operator may enable bounded read-only probe pass"
    assert truth.execution_bridge_present is False


def test_source_truth_recovery_closure_report_contract() -> None:
    report = assert_current_test_report(__file__)
    assert report["source_truth_recovery_closure_v13_status"] == "PASS_WITH_REMAINING_PARTIALS"
    assert report["source_truth_recovery_action_v13"] == "operator may enable bounded read-only probe pass"
