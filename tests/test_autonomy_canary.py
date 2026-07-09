"""Tests for the live-canary evidence gate."""

from __future__ import annotations

from autonomy.canary import evaluate_canary_readiness
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def _seed_beating_history(ledger, n, correct=True):
    """n settled markets where 'sharp' beats the market prior."""
    for i in range(n):
        ticker = f"M{i}"
        result = (i % 2 == 0)
        ledger.record_signal(Signal(source="market_prior", market_ticker=ticker,
                                    probability_yes=0.5, uncertainty=0.1, rationale=""))
        p = (0.9 if result else 0.1) if correct else 0.5
        ledger.record_signal(Signal(source="sharp", market_ticker=ticker,
                                    probability_yes=p, uncertainty=0.1, rationale=""))
        ledger.record_settlement(ticker, result)


def test_blocks_with_no_history(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        r = evaluate_canary_readiness(ledger)
        assert r.ready is False
        assert any("settlements" in b for b in r.blockers)
    finally:
        ledger.close()


def test_blocks_when_below_min_settlements(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed_beating_history(ledger, 5)
        r = evaluate_canary_readiness(ledger, min_settled=20)
        assert r.ready is False
        assert any("5/20" in b for b in r.blockers)
    finally:
        ledger.close()


def test_blocks_without_bootstrapped_weights(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed_beating_history(ledger, 25)  # enough settlements + a beater
        r = evaluate_canary_readiness(ledger, min_settled=20)
        # Beater present + settlements present, but weights never bootstrapped.
        assert r.ready is False
        assert any("weights never bootstrapped" in b for b in r.blockers)
    finally:
        ledger.close()


def test_ready_when_all_conditions_met(tmp_path):
    from autonomy.backtest import run_backtest

    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed_beating_history(ledger, 25)
        run_backtest(ledger, bootstrap_weights=True)  # writes weights
        r = evaluate_canary_readiness(ledger, min_settled=20, balance_cents=5000)
        assert r.ready is True, r.blockers
        assert r.evidence["settled_markets"] == 25
        assert "sharp" in r.evidence["market_beating_sources"]
    finally:
        ledger.close()


def test_blocks_on_low_balance(tmp_path):
    from autonomy.backtest import run_backtest

    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed_beating_history(ledger, 25)
        run_backtest(ledger, bootstrap_weights=True)
        r = evaluate_canary_readiness(ledger, min_settled=20, balance_cents=10)
        assert r.ready is False
        assert any("balance" in b for b in r.blockers)
    finally:
        ledger.close()


def test_start_session_live_blocked_by_gate(tmp_path, monkeypatch):
    import autonomy.session as sess
    from autonomy.executor import AUTONOMY_ACK
    from autonomy.ontology import SessionMode

    # Point the gate's ledger at an empty temp db -> not ready.
    monkeypatch.setattr(sess, "AutonomyLedger", lambda *a, **k: AutonomyLedger(db_path=tmp_path / "l.db"))
    result = sess.start_session(SessionMode.LIVE, ack=AUTONOMY_ACK, session_path=tmp_path / "s.json")
    assert result["started"] is False
    assert result["reason"] == "LIVE blocked by evidence gate"
    assert not (tmp_path / "s.json").exists()
