from __future__ import annotations


def test_outcome_ledger_appends_deterministic_records_and_replays_state() -> None:
    from tests.v17_test_helpers import fixture_ledger

    ledger = fixture_ledger()
    records = ledger.query().records

    assert len(records) == 3
    assert records[0].record_id == "000001-MARKET_DISCOVERED-KXDEMO-TRUTH"
    assert ledger.replay().record_count == 3
    assert "fixture-market-proof" in records[0].proof_refs
