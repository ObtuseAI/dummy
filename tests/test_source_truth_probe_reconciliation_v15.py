from __future__ import annotations

from predator_mesh.v34.run import SourceTruthProbeReconciliationV15, build_default_v34_state
from tests.v34_test_helpers import assert_current_test_report


def test_source_truth_probe_reconciliation_default_partial_action() -> None:
    truth = SourceTruthProbeReconciliationV15().evaluate(build_default_v34_state(enable_network=False))

    assert truth.source_truth_enabled_probe_evidence_v14_status == "PASS_WITH_REMAINING_PARTIALS"
    assert truth.enabled_probe_health_truth_signal == "NO_PROBE_RUN_DEFAULT_DISABLED"
    assert truth.enabled_source_recovery_action_v14 == "operator must set exact read-only public probe gate"
    assert truth.execution_bridge_present is False


def test_source_truth_probe_reconciliation_report_contract() -> None:
    report = assert_current_test_report(__file__)

    assert report["source_truth_enabled_probe_evidence_v14_status"] == "PASS_WITH_REMAINING_PARTIALS"
    assert report["reconciled_source_recovery_action_v15"] == "operator must set exact read-only public probe gate"
