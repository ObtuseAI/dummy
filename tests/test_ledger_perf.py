"""Wave-43: the ledger applies performance PRAGMAs without breaking the non-WAL
invariant. The 2 MB default cache + synchronous=FULL were the per-cycle write
tax on a multi-GB ledger."""
from __future__ import annotations

from autonomy.ledger import AutonomyLedger


def test_perf_pragmas_applied(tmp_path):
    led = AutonomyLedger(tmp_path / "l.db")
    try:
        c = led._conn
        assert int(c.execute("PRAGMA synchronous").fetchone()[0]) == 1   # NORMAL
        assert int(c.execute("PRAGMA cache_size").fetchone()[0]) < 0     # negative => KiB, big cache
        # journal_mode is NOT touched -- retention's atomic archive needs non-WAL.
        assert str(c.execute("PRAGMA journal_mode").fetchone()[0]).lower() != "wal"
    finally:
        led.close()


def test_perf_pragmas_env_override(tmp_path, monkeypatch):
    monkeypatch.setenv("DUMMY_LEDGER_SYNCHRONOUS", "FULL")
    monkeypatch.setenv("DUMMY_LEDGER_CACHE_MB", "64")
    led = AutonomyLedger(tmp_path / "l2.db")
    try:
        c = led._conn
        assert int(c.execute("PRAGMA synchronous").fetchone()[0]) == 2   # FULL
        assert int(c.execute("PRAGMA cache_size").fetchone()[0]) == -(64 * 1024)
    finally:
        led.close()
