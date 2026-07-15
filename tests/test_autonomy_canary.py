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


def _seed_shadow_fills(ledger, n=5):
    from autonomy.ontology import OutcomeKind, TradeOutcome

    for i in range(n):
        decision_id = f"shadow-fill-{i}"
        ledger.record_outcome(TradeOutcome(
            decision_id=decision_id, market_ticker=f"FILL-{i}", kind=OutcomeKind.SHADOW,
            order_id=f"shadow-{decision_id}", fill_count=0, fill_price_cents=40,
            pnl_cents=None, broker_contacted=False,
        ))
        ledger.record_outcome(TradeOutcome(
            decision_id=decision_id, market_ticker=f"FILL-{i}", kind=OutcomeKind.FILLED,
            order_id=f"shadow-{decision_id}", fill_count=1, fill_price_cents=40,
            pnl_cents=None, broker_contacted=False,
        ))


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
        _seed_shadow_fills(ledger)
        run_backtest(ledger, bootstrap_weights=True)  # writes weights
        # This fixture isolates the source/fill/balance gates; decision-policy
        # evidence has its own dedicated coverage.
        r = evaluate_canary_readiness(
            ledger, min_settled=20, min_policy_settled=0, min_canary_graded=0,
            balance_cents=5000,
        )
        assert r.ready is True, r.blockers
        assert r.evidence["settled_markets"] == 25
        assert "sharp" in r.evidence["market_beating_sources"]
    finally:
        ledger.close()


def test_default_gate_blocks_negative_fill_conditioned_operating_record(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        report = {
            "settled_markets": 0,
            "sources": {},
            "execution_quality_by_book": {"shadow": {"orders_with_confirmed_fill": 5}},
            "realized_trade_statistics": {"trades": 5, "net_pnl_cents": -100},
            "fill_conditioned_decision_policy": {
                "n": 5, "brier_skill_vs_market": -0.2,
            },
        }
        result = evaluate_canary_readiness(
            ledger, min_settled=0, min_policy_settled=0, backtest_report=report,
        )
        assert result.ready is False
        assert any("shadow PnL" in blocker for blocker in result.blockers)
        assert any("fill-conditioned" in blocker for blocker in result.blockers)
    finally:
        ledger.close()


def test_canary_blocks_negative_crypto_even_when_aggregate_fill_skill_is_positive(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        report = {
            "settled_markets": 0,
            "sources": {},
            "execution_quality_by_book": {"shadow": {"orders_with_confirmed_fill": 10}},
            "realized_trade_statistics": {"trades": 10, "net_pnl_cents": 100},
            "fill_conditioned_decision_policy": {
                "n": 10,
                "brier_skill_vs_market": 0.1,
                "by_vertical": {
                    "CRYPTO": {"n": 5, "brier_skill_vs_market": -0.2},
                    "SPORTS": {"n": 5, "brier_skill_vs_market": 0.3},
                },
            },
        }
        result = evaluate_canary_readiness(
            ledger, min_settled=0, min_policy_settled=0, backtest_report=report,
        )
        assert result.ready is False
        assert any("crypto fill-conditioned" in blocker for blocker in result.blockers)
    finally:
        ledger.close()


def test_blocks_without_observed_shadow_fills(tmp_path):
    from autonomy.backtest import run_backtest

    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed_beating_history(ledger, 25)
        run_backtest(ledger, bootstrap_weights=True)
        r = evaluate_canary_readiness(ledger, min_settled=20, balance_cents=5000)
        assert r.ready is False
        assert any("shadow fills" in blocker for blocker in r.blockers)
    finally:
        ledger.close()


def test_default_gate_requires_settled_decision_policy_evidence(tmp_path):
    from autonomy.backtest import run_backtest

    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed_beating_history(ledger, 25)
        _seed_shadow_fills(ledger)
        run_backtest(ledger, bootstrap_weights=True)
        result = evaluate_canary_readiness(ledger, min_settled=20, balance_cents=5000)
        assert result.ready is False
        assert any("decision-policy snapshots" in blocker for blocker in result.blockers)
    finally:
        ledger.close()


def test_blocks_on_low_balance(tmp_path):
    from autonomy.backtest import run_backtest

    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed_beating_history(ledger, 25)
        _seed_shadow_fills(ledger)
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
