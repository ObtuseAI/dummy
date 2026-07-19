"""Wave-43d: the JOIN evidence_split counts markets by provenance correctly.

Replaced correlated EXISTS-per-settlement (a recal residual cost) with one
JOIN+GROUP. Pins the same counts: a market with any live signal is live_settled;
one with a retro but no live signal is retro_settled; no-signal markets count
for neither. Also validated old==new on the live ledger.
"""
from __future__ import annotations

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def _sig(source, ticker, at):
    return Signal(source=source, market_ticker=ticker, probability_yes=0.5,
                  uncertainty=0.1, rationale="", created_at=at)


def test_evidence_split_counts(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        # L: live only -> live_settled
        led.record_signals([_sig("s1", "L", "2026-01-01T00:00:01+00:00")], mode="live")
        led.record_settlement("L", True)
        # R: retro only -> retro_settled
        led.record_signals([_sig("s1", "R", "2026-01-01T00:00:01+00:00")], mode="retro")
        led.record_settlement("R", True)
        # B: both -> live_settled (has_live wins)
        led.record_signals([_sig("s1", "B", "2026-01-01T00:00:01+00:00")], mode="live")
        led.record_signals([_sig("s2", "B", "2026-01-01T00:00:02+00:00")], mode="retro")
        led.record_settlement("B", True)
        # N: no signals -> neither
        led.record_settlement("N", True)

        assert led.evidence_split() == {"live_settled": 2, "retro_settled": 1}
    finally:
        led.close()


def test_evidence_split_empty(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "e.db")
    try:
        assert led.evidence_split() == {"live_settled": 0, "retro_settled": 0}
    finally:
        led.close()
