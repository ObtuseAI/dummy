"""Wave-43b: calibration_signals_for_settled must equal the per-market version.

The backtester replaced ~354k per-market round-trips (the recal's dominant cost)
with one batched fetch. It feeds source trust and promotion, so the batch has to
reproduce the per-market selection EXACTLY: earliest phantom opinion per source
for un-traded markets, latest opinion at/before the earliest decision for traded
ones (signals after the decision excluded). Validated 200/200 on the live ledger;
this pins the branches synthetically.
"""
from __future__ import annotations

import json

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def _sig(source, ticker, p, at):
    return Signal(source=source, market_ticker=ticker, probability_yes=p,
                  uncertainty=0.1, rationale="", created_at=at)


def _norm(rows):
    return sorted(
        (str(r["source"]), round(float(r["probability_yes"]), 9),
         str(r["created_at"]), json.dumps(r["features"], sort_keys=True, default=str))
        for r in rows
    )


def test_batch_matches_per_market(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        # Phantom market (never traded): earliest opinion per source wins.
        led.record_signal(_sig("s1", "PH", 0.10, "2026-01-01T00:00:01+00:00"))
        led.record_signal(_sig("s2", "PH", 0.20, "2026-01-01T00:00:02+00:00"))
        led.record_signal(_sig("s1", "PH", 0.90, "2026-01-01T00:00:03+00:00"))  # later, ignored
        led.record_settlement("PH", True)

        # Traded market: latest opinion at/before the decision; later excluded.
        led.record_signal(_sig("s1", "TR", 0.11, "2026-01-01T00:00:01+00:00"))
        led.record_signal(_sig("s2", "TR", 0.21, "2026-01-01T00:00:01+00:00"))
        led.record_signal(_sig("s1", "TR", 0.55, "2026-01-01T00:00:02+00:00"))  # latest before decision
        led.record_signal(_sig("s1", "TR", 0.99, "2026-01-01T00:00:05+00:00"))  # after decision, excluded
        led._conn.execute(
            "INSERT INTO decisions(decision_id, market_ticker, action, side, price_cents, "
            "count, ev_cents, kelly, notional_cents, probability_yes, sources_used, created_at) "
            "VALUES ('d1','TR','BUY','yes',50,1,1.0,0.1,50,0.55,'[]','2026-01-01T00:00:03+00:00')"
        )
        led._conn.commit()
        led.record_settlement("TR", False)

        tickers = ["PH", "TR"]
        batch = led.calibration_signals_for_settled(tickers)
        for tk in tickers:
            assert _norm(batch.get(tk, [])) == _norm(led.calibration_signals_for_market(tk)), tk

        # phantom picked the earliest s1 (0.10), traded picked the pre-decision s1 (0.55)
        ph = {r["source"]: r["probability_yes"] for r in batch["PH"]}
        tr = {r["source"]: r["probability_yes"] for r in batch["TR"]}
        assert ph["s1"] == 0.10 and ph["s2"] == 0.20
        assert tr["s1"] == 0.55 and tr["s2"] == 0.21
    finally:
        led.close()


def test_batch_empty_and_missing(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        assert led.calibration_signals_for_settled([]) == {}
        # settled market with no signals -> absent from the result (like the loop's [])
        led.record_settlement("NADA", True)
        assert led.calibration_signals_for_settled(["NADA"]) == {}
    finally:
        led.close()
