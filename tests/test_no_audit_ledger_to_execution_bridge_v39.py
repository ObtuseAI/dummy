from __future__ import annotations

from tests.v39_test_helpers import assert_current_test_report


def test_no_audit_ledger_to_execution_bridge_v39() -> None:
    report = assert_current_test_report(__file__)
    assert report["execution_bridge_present"] is False
    assert report["audit_ledger_to_execution_bridge_present"] is False

