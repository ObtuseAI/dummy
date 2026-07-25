"""Tests for the live-canary evidence gate."""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone

from autonomy.canary import evaluate_canary_readiness
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def _seed_beating_history(ledger, n, correct=True):
    """n settled markets where 'sharp' beats the market prior."""
    for i in range(n):
        # One exact taxonomy scope with independent event clusters.
        ticker = f"MTEST-EVENT{i}-CONTRACT"
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


def test_positive_paper_result_cannot_enable_live_session(tmp_path, monkeypatch):
    import autonomy.canary as canary
    import autonomy.session as sess
    from autonomy.executor import AUTONOMY_ACK
    from autonomy.ontology import SessionMode

    class Ready:
        ready = True
        blockers = []
        evidence = {"settled_markets": 10_000}

    monkeypatch.setattr(canary, "evaluate_canary_readiness", lambda *a, **k: Ready())
    monkeypatch.setattr(sess, "live_session_readiness", lambda: {
        "execution_authority": False,
        "blocker": "DEFAULT_DISABLED",
    })
    result = sess.start_session(SessionMode.LIVE, ack=AUTONOMY_ACK, session_path=tmp_path / "s.json")
    assert result["started"] is False
    assert result["reason"] == "LIVE blocked by explicit live authority contracts"
    assert result["paper_results_authority"] == "RETIRED_NON_AUTHORITATIVE"
    assert not (tmp_path / "s.json").exists()


def test_live_start_fails_closed_when_signed_balance_read_fails(tmp_path, monkeypatch):
    import autonomy.session as sess
    from autonomy.executor import AUTONOMY_ACK
    from autonomy.ontology import SessionMode

    monkeypatch.setattr(sess, "live_session_readiness", lambda: {
        "execution_authority": True,
        "blocker": None,
    })
    monkeypatch.setattr(
        sess, "_live_balance_cents",
        lambda: (_ for _ in ()).throw(RuntimeError("signed read unavailable")),
    )
    monkeypatch.setattr(
        sess, "AutonomyLedger", lambda *a, **k: AutonomyLedger(db_path=tmp_path / "l.db")
    )

    path = tmp_path / "live-session.json"
    result = sess.start_session(SessionMode.LIVE, ack=AUTONOMY_ACK, session_path=path)
    assert result["started"] is False
    assert result["reason"] == "LIVE blocked by balance/credential readiness"
    assert result["error_type"] == "RuntimeError"
    assert not path.exists()


def test_negative_paper_result_cannot_block_explicit_live_session(tmp_path, monkeypatch):
    import autonomy.canary as canary
    import autonomy.session as sess
    from autonomy.executor import AUTONOMY_ACK
    from autonomy.ontology import SessionMode

    monkeypatch.setattr(
        canary,
        "evaluate_canary_readiness",
        lambda *a, **k: (_ for _ in ()).throw(
            AssertionError("retired paper gate was consulted")
        ),
    )
    monkeypatch.setattr(sess, "live_session_readiness", lambda: {
        "execution_authority": True,
        "blocker": None,
    })
    monkeypatch.setattr(sess, "_live_balance_cents", lambda: 500)

    path = tmp_path / "live-session.json"
    result = sess.start_session(
        SessionMode.LIVE,
        ack=AUTONOMY_ACK,
        session_path=path,
    )
    assert result["started"] is True
    assert result["mode"] == "LIVE"
    assert path.exists()


def test_canary_compatibility_report_is_retired_and_never_reads_balance(tmp_path, monkeypatch):
    import autonomy.session as sess

    monkeypatch.setattr(
        sess, "AutonomyLedger", lambda *a, **k: AutonomyLedger(db_path=tmp_path / "l.db")
    )
    monkeypatch.setattr(
        sess, "_live_balance_cents",
        lambda: (_ for _ in ()).throw(AssertionError("broker read attempted")),
    )
    result = sess.canary_readiness(check_balance=True)
    assert result["ready"] is False
    assert result["status"] == "RETIRED_NON_AUTHORITATIVE"
    assert result["execution_authority"] is False
    assert result["can_enable_live"] is False
    assert result["can_block_live"] is False
    assert result["broker_contacted"] is False


def test_cached_canary_preflight_fails_fast_on_incomplete_summary(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    summary = tmp_path / "latest.json"
    summary.write_text(json.dumps({
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "settled_markets": 100,
    }), encoding="utf-8")
    try:
        result = evaluate_canary_readiness(
            ledger,
            prefer_cached_backtest=True,
            cached_backtest_path=summary,
        )
        assert result.ready is False
        assert any("lacks canary evidence" in blocker for blocker in result.blockers)
        assert "sources" in result.evidence["cached_backtest"]["missing_fields"]
    finally:
        ledger.close()


def test_live_session_readiness_loads_credentials_that_live_only_in_dotenv(monkeypatch):
    """The readiness gate must see credentials stored in .env.

    The Kalshi refs live in .env, not the user environment.
    ``live_execution_authority_status`` reads ``os.environ`` directly, so a
    readiness check that did not load .env first reported
    ``credentials_resolved_locally: false`` while working credentials sat on
    disk -- and ``start_session`` refused the live session that arms trading.
    ``_live_balance_cents`` and ``build_brain(LIVE)`` both already load them;
    the gate that runs *before* those did not.
    """
    import autonomy.session as sess

    loads = []

    def fake_load(**kwargs):
        loads.append(kwargs)
        monkeypatch.setenv("KALSHI_API_KEY_ID", "resolved-from-dotenv")
        return {"KALSHI_API_KEY_ID": "resolved-from-dotenv"}

    monkeypatch.delenv("KALSHI_API_KEY_ID", raising=False)
    monkeypatch.setattr("core.env_loader.load_whitelisted_env", fake_load)

    readiness = sess.live_session_readiness()

    assert len(loads) == 1, "readiness must load whitelisted .env refs exactly once"
    assert os.environ.get("KALSHI_API_KEY_ID") == "resolved-from-dotenv"
    # The credential check now reads the loaded value rather than a false
    # negative.  Every other gate is untouched: live-submit stays disabled.
    assert readiness["execution_authority"] is False
    assert readiness["default_disabled"] is True
