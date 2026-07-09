from __future__ import annotations


def test_outcome_ledger_schema_lists_required_record_types() -> None:
    from predator_mesh.v17.outcome_ledger import OutcomeLedger

    report = OutcomeLedger.schema_report()

    assert "MARKET_DISCOVERED" in report["record_types"]
    assert "IMPROVEMENT_PROPOSAL_CREATED" in report["record_types"]
    assert report["append_only"] is True
