"""Wave-46: pruning redundant re-pricings must not move any weight.

The prune keeps exactly the signal the backtester selects per (source, market)
-- the earliest phantom opinion, or the latest opinion at/before the first
decision -- and deletes the rest for old-settled markets. This pins the core
safety property: run_backtest's derived weights are identical before and after,
so the prune is pure size reduction with zero effect on trust/promotion.
"""
from __future__ import annotations

from autonomy.backtest import run_backtest
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal
from autonomy.signal_prune import apply_prune, plan_prune


def _sig(source, ticker, p, at):
    return Signal(source=source, market_ticker=ticker, probability_yes=p,
                  uncertainty=0.1, rationale="", created_at=at)


def _seed(led):
    # Traded market A: sharp re-prices 3x; a decision at :03 -> backtester uses
    # the latest opinion at/before :03 (the :02 one); :01 and :05 are redundant.
    led.record_signal(_sig("market_prior", "A", 0.5, "2026-01-01T00:00:01+00:00"))
    led.record_signal(_sig("sharp", "A", 0.6, "2026-01-01T00:00:01+00:00"))
    led.record_signal(_sig("sharp", "A", 0.8, "2026-01-01T00:00:02+00:00"))
    led.record_signal(_sig("sharp", "A", 0.9, "2026-01-01T00:00:05+00:00"))
    led._conn.execute(
        "UPDATE signals SET ingested_at=created_at WHERE market_ticker='A'"
    )
    led._conn.execute(
        "INSERT INTO decisions(decision_id,market_ticker,action,side,price_cents,count,"
        "ev_cents,kelly,notional_cents,probability_yes,sources_used,created_at) "
        "VALUES ('d','A','BUY','yes',50,1,1.0,0.1,50,0.8,'[]','2026-01-01T00:00:03+00:00')")
    led._conn.commit()
    led.record_settlement("A", True)
    # Phantom market B: dull re-prices 2x, no decision -> backtester uses earliest.
    led.record_signal(_sig("market_prior", "B", 0.5, "2026-01-01T00:00:01+00:00"))
    led.record_signal(_sig("dull", "B", 0.2, "2026-01-01T00:00:01+00:00"))
    led.record_signal(_sig("dull", "B", 0.7, "2026-01-01T00:00:02+00:00"))
    led.record_settlement("B", False)


def test_prune_preserves_backtest_weights(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed(led)
        w_before = dict(run_backtest(led)["derived_weights"])
        n_before = led._conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]

        plan = plan_prune(led, settled_before_days=-1)   # cutoff in the future -> all settled qualify
        assert plan["prunable"] >= 3                       # sharp:01,05 + dull:02
        deleted = apply_prune(led, plan["prunable_ids"])
        assert deleted == plan["prunable"]

        w_after = dict(run_backtest(led)["derived_weights"])
        n_after = led._conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]

        assert w_before == w_after           # PROOF: not a single weight moved
        assert n_after == n_before - deleted  # exactly the redundant rows went
    finally:
        led.close()


def test_prune_keeps_live_and_retro_lanes_and_prunes_late_receipts(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "lanes.db")
    try:
        ticker = "LANES"
        led.record_signal(_sig("market_prior", ticker, 0.50, "2026-01-01T00:00:01+00:00"))
        led.record_signal(_sig("sharp", ticker, 0.60, "2026-01-01T00:00:01+00:00"))
        led.record_signal(_sig("sharp", ticker, 0.70, "2026-01-01T00:00:02+00:00"))
        led.record_signal(_sig("late", ticker, 0.95, "2026-01-01T00:00:02+00:00"))
        led.record_signal(
            _sig("market_prior", ticker, 0.45, "2026-01-01T00:00:01+00:00"),
            mode="retro",
        )
        led.record_signal(
            _sig("sharp", ticker, 0.80, "2026-01-01T00:00:01+00:00"),
            mode="retro",
        )
        led.record_signal(
            _sig("sharp", ticker, 0.90, "2026-01-01T00:00:02+00:00"),
            mode="retro",
        )
        led._conn.execute(
            "UPDATE signals SET ingested_at=created_at "
            "WHERE market_ticker='LANES' AND mode='live' AND source!='late'"
        )
        led._conn.execute(
            "INSERT INTO decisions(decision_id,market_ticker,action,side,price_cents,count,"
            "ev_cents,kelly,notional_cents,probability_yes,sources_used,created_at) "
            "VALUES ('lanes-d','LANES','BUY','yes',50,1,1.0,0.1,50,0.7,'[]',"
            "'2026-01-01T00:00:03+00:00')"
        )
        led._conn.commit()
        led.record_settlement(ticker, True)

        before_live = {
            row["source"]: row["probability_yes"]
            for row in led.calibration_signals_for_market(ticker)
        }
        before_retro = {
            row["source"]: row["probability_yes"]
            for row in led.calibration_signals_for_market(ticker, evidence_mode="retro")
        }
        assert before_live == {"market_prior": 0.50, "sharp": 0.70}
        assert before_retro == {"market_prior": 0.45, "sharp": 0.90}

        ids = {
            (str(source), str(mode), round(float(probability), 2)): int(sid)
            for sid, source, mode, probability in led._conn.execute(
                "SELECT id,source,mode,probability_yes FROM signals "
                "WHERE market_ticker='LANES'"
            )
        }
        plan = plan_prune(led, settled_before_days=-1)
        prunable = set(plan["prunable_ids"])
        assert ids[("sharp", "live", 0.60)] in prunable
        assert ids[("sharp", "retro", 0.80)] in prunable
        assert ids[("late", "live", 0.95)] in prunable
        assert ids[("sharp", "live", 0.70)] not in prunable
        assert ids[("sharp", "retro", 0.90)] not in prunable

        assert apply_prune(led, plan["prunable_ids"]) == plan["prunable"]
        after_live = {
            row["source"]: row["probability_yes"]
            for row in led.calibration_signals_for_market(ticker)
        }
        after_retro = {
            row["source"]: row["probability_yes"]
            for row in led.calibration_signals_for_market(ticker, evidence_mode="retro")
        }
        assert after_live == before_live
        assert after_retro == before_retro
    finally:
        led.close()


def test_prune_skips_recent_and_unsettled(tmp_path):
    led = AutonomyLedger(db_path=tmp_path / "l2.db")
    try:
        _seed(led)
        # Unsettled market C with re-pricings: must be untouched.
        led.record_signal(_sig("sharp", "C", 0.6, "2026-01-01T00:00:01+00:00"))
        led.record_signal(_sig("sharp", "C", 0.7, "2026-01-01T00:00:02+00:00"))
        # settled_before_days huge -> even A/B are "too recent" -> nothing prunes.
        plan = plan_prune(led, settled_before_days=100000)
        assert plan["prunable"] == 0
    finally:
        led.close()
