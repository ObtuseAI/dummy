from __future__ import annotations

import sqlite3

import pytest

from autonomy.ledger import AutonomyLedger


TICKER = "KXSETTLEMENT-26JUL22-YES"
SETTLED_AT = "2026-07-22T20:15:00+00:00"
SOURCE = "kalshi_public_market"
EVIDENCE = {"market_status": "settled", "result": "yes"}


def _stored_row(ledger: AutonomyLedger) -> tuple[object, ...]:
    row = ledger._conn.execute(
        "SELECT s.rowid,s.market_ticker,s.result_yes,s.settled_at,p.rowid,"
        " COALESCE(p.source,''),COALESCE(p.evidence,'{}')"
        " FROM settlements s LEFT JOIN settlement_provenance p USING(market_ticker)"
        " WHERE s.market_ticker=?",
        (TICKER,),
    ).fetchone()
    assert row is not None
    return tuple(row)


def test_exact_settlement_replay_is_a_physical_no_op(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_settlement(
            TICKER,
            True,
            settled_at=SETTLED_AT,
            source=SOURCE,
            evidence=EVIDENCE,
        )
        before = _stored_row(ledger)
        changes_before = ledger._conn.total_changes

        # Key order is not evidence content, so canonical JSON makes this an
        # exact replay instead of a false conflict.
        ledger.record_settlement(
            TICKER,
            True,
            settled_at=SETTLED_AT,
            source=SOURCE,
            evidence={"result": "yes", "market_status": "settled"},
        )
        ledger.record_settlement(TICKER, True)

        assert _stored_row(ledger) == before
        assert ledger._conn.total_changes == changes_before
    finally:
        ledger.close()


@pytest.mark.parametrize(
    ("result_yes", "settled_at", "source", "evidence"),
    [
        (False, SETTLED_AT, SOURCE, EVIDENCE),
        (True, "2026-07-22T20:16:00+00:00", SOURCE, EVIDENCE),
        (True, SETTLED_AT, "different_source", EVIDENCE),
        (True, SETTLED_AT, SOURCE, {"market_status": "settled", "result": "no"}),
    ],
    ids=["result", "settled_at", "source", "evidence"],
)
def test_conflicting_settlement_facts_are_rejected_and_original_survives(
    tmp_path,
    result_yes: bool,
    settled_at: str,
    source: str,
    evidence: dict[str, str],
) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_settlement(
            TICKER,
            True,
            settled_at=SETTLED_AT,
            source=SOURCE,
            evidence=EVIDENCE,
        )
        before = _stored_row(ledger)
        changes_before = ledger._conn.total_changes

        with pytest.raises(ValueError, match="settlement record is immutable"):
            ledger.record_settlement(
                TICKER,
                result_yes,
                settled_at=settled_at,
                source=source,
                evidence=evidence,
            )

        assert _stored_row(ledger) == before
        assert ledger._conn.total_changes == changes_before
    finally:
        ledger.close()


def test_legacy_two_argument_replay_preserves_original_timestamp(tmp_path) -> None:
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ledger.record_settlement(TICKER, True)
        before = _stored_row(ledger)
        changes_before = ledger._conn.total_changes

        ledger.record_settlement(TICKER, True)

        assert _stored_row(ledger) == before
        assert ledger._conn.total_changes == changes_before
    finally:
        ledger.close()


def test_settlement_provenance_migration_is_additive_and_preserves_rows(tmp_path) -> None:
    db_path = tmp_path / "legacy.db"
    connection = sqlite3.connect(db_path)
    connection.execute(
        "CREATE TABLE settlements ("
        "market_ticker TEXT PRIMARY KEY,result_yes INTEGER NOT NULL,"
        "settled_at TEXT NOT NULL)"
    )
    connection.execute(
        "INSERT INTO settlements(market_ticker,result_yes,settled_at) VALUES (?,?,?)",
        (TICKER, 1, SETTLED_AT),
    )
    connection.commit()
    connection.close()

    ledger = AutonomyLedger(db_path)
    try:
        assert _stored_row(ledger) == (1, TICKER, 1, SETTLED_AT, None, "", "{}")
        changes_before = ledger._conn.total_changes
        ledger.record_settlement(TICKER, True)
        assert ledger._conn.total_changes == changes_before
    finally:
        ledger.close()
