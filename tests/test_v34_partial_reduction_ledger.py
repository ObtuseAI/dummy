from __future__ import annotations

from predator_mesh.v34.run import V34PartialReductionLedger, build_default_v34_state
from tests.v34_test_helpers import assert_v34_report_named


def test_partial_reduction_ledger_default_remains_partial() -> None:
    ledger = V34PartialReductionLedger().evaluate(build_default_v34_state(enable_network=False))

    assert ledger.partial_reduction_status == "PASS_WITH_REMAINING_PARTIALS"
    assert ledger.execution_bridge_present is False
    assert "PROBE_DISABLED_BY_DEFAULT" in ledger.remaining_partial_cause


def test_partial_reduction_ledger_report_contract() -> None:
    report = assert_v34_report_named("v34_partial_reduction_ledger_report.json", "partial_reduction_status")

    assert report["partial_reduction_status"] == "PASS_WITH_REMAINING_PARTIALS"
    assert report["pass_delta"]["enabled_path_probe_run_count"] == 3
