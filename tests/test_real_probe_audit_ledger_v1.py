from __future__ import annotations

from tests.v36_test_helpers import assert_current_test_report


def test_real_probe_audit_ledger_v1() -> None:
    report = assert_current_test_report(__file__)
    assert report["append_only"] is True
    assert report["gate_audit"] is True
    assert report["transport_audit"] is True
    assert report["evidence_audit"] is True
    assert report["execution_bridge_present"] is False
