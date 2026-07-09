from __future__ import annotations

from v18_test_helpers import assert_pass_report


def test_v18_no_trade_gates_integrate_with_decision_ledger() -> None:
    from predator_mesh.v18.integration import V18DecisionLedgerIntegration

    report = V18DecisionLedgerIntegration().to_report()

    assert_pass_report(report)
    assert report["no_trade_decision_records"] == 5
    assert report["live_execution_enabled"] is False
