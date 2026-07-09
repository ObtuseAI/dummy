from __future__ import annotations

from predator_mesh.v34.run import ReconciledProbeAuditLedgerV3, build_default_v34_state
from tests.v34_test_helpers import assert_current_test_report


def test_reconciled_probe_audit_ledger_records_disabled_gate_without_secrets() -> None:
    audit = ReconciledProbeAuditLedgerV3().audit(build_default_v34_state(enable_network=False))

    assert audit.enabled_probe_audit_ledger_status == "PASS"
    assert audit.gate_state == "DISABLED_BY_DEFAULT"
    assert audit.probe_run_count == 0
    assert audit.secret_values_exposed is False
    assert audit.execution_bridge_present is False


def test_reconciled_probe_audit_ledger_report_contract() -> None:
    report = assert_current_test_report(__file__)

    assert report["enabled_probe_audit_ledger_status"] == "PASS"
    assert report["reconciled_probe_gate_audit"]["gate_state"] == "DISABLED_BY_DEFAULT"
