from __future__ import annotations


def test_outcome_ledger_integrity_hash_chain_passes_and_detects_mutation() -> None:
    from tests.v17_test_helpers import fixture_ledger

    ledger = fixture_ledger()
    assert ledger.integrity_check().verdict == "PASS"
    ledger.records[0].payload["tampered"] = True
    assert ledger.integrity_check().verdict == "FAIL"
