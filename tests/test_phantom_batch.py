"""Wave-43c: apply_settlement with pre-fetched signals == the per-market query.

_apply_phantom_settlements shares one batched calibration fetch across a
backlog of settlements instead of one query per market. This pins that passing
the batched signals produces identical weight updates to the query path, so the
backlog optimization can't change what the learner learns.
"""
from __future__ import annotations

from autonomy.ledger import AutonomyLedger
from autonomy.learner import Learner
from autonomy.ontology import Signal


def _sig(source, ticker, p, at):
    return Signal(source=source, market_ticker=ticker, probability_yes=p,
                  uncertainty=0.1, rationale="", created_at=at)


def _seed(led):
    led.record_signal(_sig("market_prior", "M", 0.5, "2026-01-01T00:00:01+00:00"))
    led.record_signal(_sig("s1", "M", 0.9, "2026-01-01T00:00:02+00:00"))
    led.record_signal(_sig("s2", "M", 0.3, "2026-01-01T00:00:03+00:00"))
    led.record_settlement("M", True)


def test_prefetched_signals_match_query(tmp_path):
    a = AutonomyLedger(db_path=tmp_path / "a.db")
    _seed(a)
    r_query = Learner(a).apply_settlement("M", True)   # queries per market
    a.close()

    b = AutonomyLedger(db_path=tmp_path / "b.db")
    _seed(b)
    prefetched = b.calibration_signals_for_settled(["M"])["M"]
    r_batch = Learner(b).apply_settlement("M", True, signals=prefetched)  # shared fetch
    b.close()

    assert r_query and r_query == r_batch
