"""Wave-81: chunked signal-writes release the whole-DB lock between batches so
concurrent writers interleave, instead of one multi-minute transaction. The
persisted result must be identical to the single-transaction path; all_or_none
(replay atomicity) must never chunk.
"""
from __future__ import annotations

import autonomy.ledger as ledger_mod
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def _sig(source, ticker, at="2026-01-01T00:00:01+00:00"):
    return Signal(source=source, market_ticker=ticker, probability_yes=0.5,
                  uncertainty=0.1, rationale="", created_at=at)


def _count(led) -> int:
    return led._conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]


def test_chunked_write_persists_every_row(monkeypatch, tmp_path):
    monkeypatch.setattr(ledger_mod, "LEDGER_SIGNAL_WRITE_CHUNK", 2)
    led = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        sigs = [_sig(f"s{i}", f"MKT{i}") for i in range(7)]
        accepted = led.record_signals(sigs, mode="live")
        assert accepted == [True] * 7
        assert _count(led) == 7  # all committed across the chunk boundaries
    finally:
        led.close()


def test_chunked_matches_single_transaction(monkeypatch, tmp_path):
    def run(chunk: int, name: str) -> int:
        monkeypatch.setattr(ledger_mod, "LEDGER_SIGNAL_WRITE_CHUNK", chunk)
        led = AutonomyLedger(db_path=tmp_path / name)
        try:
            led.record_signals([_sig(f"s{i}", f"M{i}") for i in range(10)], mode="live")
            return _count(led)
        finally:
            led.close()
    assert run(3, "chunked.db") == run(0, "single.db") == 10


def test_all_or_none_is_atomic_regardless_of_chunk(monkeypatch, tmp_path):
    # Tiny chunk must NOT break all_or_none: a batch containing a duplicate is
    # rejected wholesale (both False), leaving nothing half-written.
    monkeypatch.setattr(ledger_mod, "LEDGER_SIGNAL_WRITE_CHUNK", 1)
    led = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        led.record_signals([_sig("s1", "DUP", "2026-01-01T00:00:01+00:00")], mode="retro")
        before = _count(led)
        # Second write pairs a fresh row with the exact duplicate -> all_or_none
        # rejects the whole pair.
        pair = [_sig("s2", "NEW", "2026-01-01T00:00:02+00:00"),
                _sig("s1", "DUP", "2026-01-01T00:00:01+00:00")]
        assert led.record_signals(pair, mode="retro", all_or_none=True) == [False, False]
        assert _count(led) == before  # nothing from the rejected batch persisted
    finally:
        led.close()
