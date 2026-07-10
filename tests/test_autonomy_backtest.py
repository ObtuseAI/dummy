"""Tests for the offline backtester."""

from __future__ import annotations

from autonomy.backtest import SourceScoreTracker, run_backtest
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def _signal(source, ticker, p):
    return Signal(source=source, market_ticker=ticker, probability_yes=p, uncertainty=0.1, rationale="")


def test_tracker_scores_and_weights():
    t = SourceScoreTracker("s")
    # Perfectly confident and correct on 3 markets.
    for _ in range(3):
        t.observe(0.9, 1, market_brier=0.25, market_p=0.5)
    s = t.summary()
    assert s["n"] == 3
    assert s["mean_brier"] < 0.02
    assert t.derived_weight() > 1.1  # positive but shrunk: three wins cannot crown it


def test_tracker_penalizes_wrong_confident():
    t = SourceScoreTracker("bad")
    for _ in range(3):
        t.observe(0.95, 0, market_brier=0.25, market_p=0.5)  # confidently wrong
    assert t.derived_weight() < 0.5


def test_run_backtest_empty_ledger(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        report = run_backtest(ledger)
        assert report["settled_markets"] == 0
    finally:
        ledger.close()


def test_run_backtest_scores_sources_and_bootstraps(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        # sharp is right, dull is wrong, market_prior is the baseline.
        for ticker, result in [("A", True), ("B", True), ("C", False)]:
            ledger.record_signal(_signal("market_prior", ticker, 0.5))
            ledger.record_signal(_signal("sharp", ticker, 0.9 if result else 0.1))
            ledger.record_signal(_signal("dull", ticker, 0.1 if result else 0.9))
            ledger.record_settlement(ticker, result)

        report = run_backtest(ledger, bootstrap_weights=True)
        assert report["settled_markets"] == 3
        assert report["derived_weights"]["sharp"] > report["derived_weights"]["dull"]
        assert report["sources"]["sharp"]["beat_market_rate"] == 1.0
        # Bootstrapped weights persisted into the ledger.
        assert ledger.get_weight("sharp") == report["derived_weights"]["sharp"]
        assert ledger.get_weight("dull") < 1.0
    finally:
        ledger.close()


def test_run_backtest_reports_realized_pnl(tmp_path):
    from autonomy.ontology import OutcomeKind, TradeOutcome

    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        ledger.record_signal(_signal("market_prior", "A", 0.5))
        ledger.record_settlement("A", True)
        ledger.record_outcome(TradeOutcome(
            decision_id="d1", market_ticker="A", kind=OutcomeKind.FILLED,
            order_id="o1", fill_count=1, fill_price_cents=40, pnl_cents=None,
            broker_contacted=True,
        ))
        ledger.record_outcome(TradeOutcome(
            decision_id="d1", market_ticker="A", kind=OutcomeKind.SETTLED_WIN,
            order_id="o1", fill_count=1, fill_price_cents=40, pnl_cents=58,
            broker_contacted=True,
        ))
        report = run_backtest(ledger)
        assert report["realized_decision_pnl_cents"] == 58
        assert report["graded_decisions"] == 1
        assert report["unverified_settlement_outcomes"] == 0
    finally:
        ledger.close()
