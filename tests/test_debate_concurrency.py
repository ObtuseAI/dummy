"""Wave-45: the debate runs its top-K panels concurrently but bounded.

The debate was the dominant per-cycle cost (phase timing: 5-22 min), K markets
adjudicated sequentially. It now runs them in parallel under a semaphore so the
wall time drops ~concurrency-fold without firing K x providers all at once and
tripping the provider rate limits.
"""
from __future__ import annotations

import asyncio
import types

from autonomy.brain import CycleReport, PredatorBrain
from autonomy.ledger import AutonomyLedger


def test_debate_bounded_concurrency(monkeypatch, tmp_path):
    monkeypatch.setenv("DUMMY_DEBATE_TOP_K", "6")
    monkeypatch.setenv("DUMMY_DEBATE_CONCURRENCY", "2")
    monkeypatch.setenv("DUMMY_DEBATE_CLI_TOP_K", "0")
    # Permit two complete panels for this concurrency-only test. The reviewed
    # code-level market ceiling must still prevent the requested six.
    monkeypatch.setenv("DUMMY_DEBATE_MAX_LOGICAL_CALLS_PER_CYCLE", "16")

    state = {"live": 0, "peak": 0, "calls": 0}

    async def fake_run_debate(router, market, base_prob=None, context=None, allow_cli=True):
        state["calls"] += 1
        state["live"] += 1
        state["peak"] = max(state["peak"], state["live"])
        await asyncio.sleep(0.02)
        state["live"] -= 1
        return None  # skip record/fuse; this test pins the concurrency bound

    monkeypatch.setattr("autonomy.debate.run_debate", fake_run_debate)

    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        me = types.SimpleNamespace(router=object(), ledger=ledger)
        forecaster = types.SimpleNamespace(fuse=lambda m, s: None)
        scored = [
            (types.SimpleNamespace(ticker=f"KXBTC-26JUL10-T{i}"),
             types.SimpleNamespace(probability_yes=0.6), [])
            for i in range(6)
        ]
        report = CycleReport(status="", mode="shadow", stage=1, bankroll_cents=0)
        asyncio.run(PredatorBrain._adjudicate_top_k(me, forecaster, scored, report))
    finally:
        ledger.close()

    assert state["calls"] == 2          # code-level paid-panel ceiling
    assert state["peak"] == 2           # ...and never more than the concurrency bound


def test_debate_concurrency_one_is_sequential(monkeypatch, tmp_path):
    monkeypatch.setenv("DUMMY_DEBATE_TOP_K", "4")
    monkeypatch.setenv("DUMMY_DEBATE_CONCURRENCY", "1")
    monkeypatch.setenv("DUMMY_DEBATE_CLI_TOP_K", "0")
    monkeypatch.setenv("DUMMY_DEBATE_MAX_LOGICAL_CALLS_PER_CYCLE", "16")

    state = {"live": 0, "peak": 0, "calls": 0}

    async def fake_run_debate(router, market, base_prob=None, context=None, allow_cli=True):
        state["calls"] += 1
        state["live"] += 1
        state["peak"] = max(state["peak"], state["live"])
        await asyncio.sleep(0.01)
        state["live"] -= 1
        return None

    monkeypatch.setattr("autonomy.debate.run_debate", fake_run_debate)
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        me = types.SimpleNamespace(router=object(), ledger=ledger)
        forecaster = types.SimpleNamespace(fuse=lambda m, s: None)
        scored = [(types.SimpleNamespace(ticker=f"K-{i}"),
                   types.SimpleNamespace(probability_yes=0.5), []) for i in range(4)]
        report = CycleReport(status="", mode="shadow", stage=1, bankroll_cents=0)
        asyncio.run(PredatorBrain._adjudicate_top_k(me, forecaster, scored, report))
    finally:
        ledger.close()
    assert state["calls"] == 2  # hard market cap remains in force
    assert state["peak"] == 1   # concurrency=1 -> strictly sequential (back-compat)
