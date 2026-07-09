from __future__ import annotations


def test_decision_ledger_records_decisions_and_links_forecast_proof() -> None:
    from predator_mesh.v17.decisions import DecisionLedger

    ledger = DecisionLedger()
    record = ledger.record_decision(
        market_id="KXDEMO-TRUTH",
        forecast_snapshot_id="forecast-1",
        decision_type="NO_TRADE",
        proof_refs=["decision-proof"],
    )

    assert record.decision_type == "NO_TRADE"
    assert record.forecast_snapshot_id == "forecast-1"
    assert ledger.to_report()["decision_count"] == 1
