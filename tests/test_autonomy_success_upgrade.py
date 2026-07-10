"""Regression tests for fill-truth, fee, and decision-policy upgrades."""
from __future__ import annotations

import asyncio
import json
from datetime import date, datetime, timedelta, timezone

from autonomy.backtest import run_backtest
from autonomy.brain import PredatorBrain
from autonomy.executor import Executor, order_ttl_seconds
from autonomy.fees import kalshi_maker_fee_cents, kalshi_taker_fee_cents
from autonomy.learner import Learner
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    MarketView,
    OutcomeKind,
    SessionMode,
    TradeOutcome,
    Vertical,
)
from autonomy.reconciler import Reconciler
from autonomy.risk_brain import RiskBrain


def _decision(decision_id: str, ticker: str, *, count: int = 1,
              created_at: str | None = None) -> Decision:
    forecast = Forecast(
        market_ticker=ticker,
        probability_yes=0.70,
        uncertainty=0.05,
        sources_used={"model": 1.0},
        market_implied_yes=0.40,
        edge_yes=0.30,
        rationale="test",
    )
    return Decision(
        decision_id=decision_id,
        market_ticker=ticker,
        action=DecisionAction.BUY_YES,
        side="yes",
        price_cents=40,
        count=count,
        ev_cents_per_contract=20.0,
        kelly_fraction=0.1,
        notional_cents=40 * count,
        forecast=forecast,
        risk_snapshot={},
        created_at=created_at or datetime.now(timezone.utc).isoformat(),
    )


def _market(ticker: str, ask: int) -> MarketView:
    return MarketView(
        ticker=ticker,
        title="test",
        vertical=Vertical.CRYPTO,
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        yes_bid=max(1, ask - 2),
        yes_ask=ask,
        no_bid=100 - ask,
        no_ask=100 - max(1, ask - 2),
        volume=100,
        liquidity=100,
    )


def test_current_maker_fee_schedule_and_stale_fail_closed():
    assert kalshi_maker_fee_cents(50, 10, "KXHIGHNY-26JUL10-T85") == 0
    assert kalshi_maker_fee_cents(50, 10, "KXMLBGAME-26JUL10-ABC") == 5
    assert kalshi_taker_fee_cents(50, 10, "KXMLBGAME-26JUL10-ABC") == 18
    assert kalshi_taker_fee_cents(50, 10, "KXBTCY-26DEC31") == 0
    # Once the embedded schedule is stale, maker EV uses the higher taker fee.
    assert kalshi_maker_fee_cents(
        50, 10, "KXHIGHNY-26JUL10-T85", as_of=date(2026, 9, 1)
    ) == 18


def test_pre_upgrade_live_session_is_invalidated(tmp_path):
    from autonomy.executor import AUTONOMY_ACK, load_session

    path = tmp_path / "session.json"
    path.write_text(json.dumps({
        "mode": "LIVE",
        "ack": AUTONOMY_ACK,
        "expires_at": (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
    }), encoding="utf-8")
    session = load_session(path)
    assert session["valid"] is False
    assert "fill-truth" in session["reason"]


def test_shadow_maker_requires_observed_cross_then_becomes_position(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        decision = _decision("d1", "KXBTC-26JUL10-T100")
        ledger.record_decision(decision)
        outcome = asyncio.run(Executor(SessionMode.SHADOW).execute(decision))
        ledger.record_outcome(outcome)
        reconciler = Reconciler(ledger, fetch_market_result=lambda _ticker: {})

        assert reconciler.reconcile_shadow_orders([_market(decision.market_ticker, 41)]) == []
        pending = ledger.open_decisions("shadow")[0]
        assert pending["filled_count"] == 0
        assert pending["reserved_count"] == 1
        assert pending["order_active"] == 1

        updates = reconciler.reconcile_shadow_orders([_market(decision.market_ticker, 40)])
        assert [update.kind for update in updates] == [OutcomeKind.FILLED]
        filled = ledger.open_decisions("shadow")[0]
        assert filled["filled_count"] == 1
        assert filled["reserved_count"] == 1
        assert filled["order_active"] == 0
    finally:
        ledger.close()


def test_shadow_maker_expires_without_cross(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        created = (datetime.now(timezone.utc) - timedelta(hours=1)).isoformat()
        decision = _decision("d1", "KXBTC-26JUL10-T100", created_at=created)
        ledger.record_decision(decision)
        ledger.record_outcome(asyncio.run(Executor(SessionMode.SHADOW).execute(decision)))
        updates = Reconciler(ledger).reconcile_shadow_orders(
            [_market(decision.market_ticker, 41)]
        )
        assert [update.kind for update in updates] == [OutcomeKind.EXPIRED]
        assert ledger.open_decisions("shadow") == []
    finally:
        ledger.close()


def test_shadow_maker_detects_intracycle_candle_cross(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        created = (datetime.now(timezone.utc) - timedelta(minutes=10)).isoformat()
        decision = _decision("d1", "KXBTC-26JUL10-T100", created_at=created)
        ledger.record_decision(decision)
        ledger.record_outcome(asyncio.run(Executor(SessionMode.SHADOW).execute(decision)))

        def candles(_series, _ticker, _start, end, _period):
            return [{
                "end_period_ts": end - 60,
                "yes_ask": {"low_dollars": "0.4000"},
                "yes_bid": {"high_dollars": "0.3900"},
            }]

        updates = Reconciler(ledger, fetch_shadow_candles=candles).reconcile_shadow_orders(
            [_market(decision.market_ticker, 43)]
        )
        assert [update.kind for update in updates] == [OutcomeKind.FILLED]
        assert updates[0].detail["reason"] == "shadow_maker_intracycle_candle_cross"
        summary = ledger.execution_summary("shadow")
        assert summary["average_seconds_to_first_fill"] < 120
        assert summary["fill_witness_quality"]["precise_witness_timestamps"] == 1
    finally:
        ledger.close()


def test_shadow_maker_public_print_consumes_captured_queue(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        created_dt = datetime.now(timezone.utc) - timedelta(seconds=30)
        decision = _decision("d1", "KXBTC-26JUL10-T100", count=2,
                             created_at=created_dt.isoformat())
        ledger.record_decision(decision)
        ledger.record_outcome(asyncio.run(Executor(
            SessionMode.SHADOW,
            shadow_book_fn=lambda _ticker: {
                "yes_dollars": [["0.4000", "3.00"]], "no_dollars": [],
            },
        ).execute(decision)))
        trade_time = (created_dt + timedelta(seconds=15)).isoformat().replace("+00:00", "Z")
        trades = [
            {"trade_id": "a", "created_time": trade_time, "count_fp": "2.00",
             "yes_price_dollars": "0.4000", "no_price_dollars": "0.6000",
             "taker_book_side": "ask", "is_block_trade": False},
            {"trade_id": "b", "created_time": trade_time, "count_fp": "3.00",
             "yes_price_dollars": "0.4000", "no_price_dollars": "0.6000",
             "taker_book_side": "ask", "is_block_trade": False},
        ]
        updates = Reconciler(
            ledger, fetch_shadow_trades=lambda *_args: trades,
        ).reconcile_shadow_orders([_market(decision.market_ticker, 43)])
        assert [update.kind for update in updates] == [OutcomeKind.FILLED]
        assert updates[0].detail["reason"] == "shadow_maker_public_trade_queue_consumed"
        assert updates[0].detail["matching_trade_volume"] == 5.0
    finally:
        ledger.close()


def test_shadow_maker_public_print_through_proves_fill_without_queue_snapshot(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        created_dt = datetime.now(timezone.utc) - timedelta(seconds=30)
        decision = _decision("d1", "KXBTC-26JUL10-T100", created_at=created_dt.isoformat())
        ledger.record_decision(decision)
        ledger.record_outcome(asyncio.run(Executor(SessionMode.SHADOW).execute(decision)))
        trade = {
            "trade_id": "through", "created_time": (
                created_dt + timedelta(seconds=15)
            ).isoformat().replace("+00:00", "Z"),
            "count_fp": "0.25", "yes_price_dollars": "0.3900",
            "no_price_dollars": "0.6100", "taker_book_side": "ask",
            "is_block_trade": False,
        }
        updates = Reconciler(
            ledger, fetch_shadow_trades=lambda *_args: [trade],
        ).reconcile_shadow_orders([_market(decision.market_ticker, 43)])
        assert updates[0].detail["reason"] == "shadow_maker_public_trade_through"
    finally:
        ledger.close()


def test_shadow_legacy_order_expires_when_captured_queue_exceeds_new_policy(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        decision = _decision("d1", "KXWTI-26JUL1014-T75")
        ledger.record_decision(decision)
        ledger.record_outcome(TradeOutcome(
            decision_id="d1", market_ticker=decision.market_ticker,
            kind=OutcomeKind.SHADOW, order_id="shadow-d1", fill_count=0,
            fill_price_cents=40, pnl_cents=None, broker_contacted=False,
            detail={
                "state": "resting", "queue_snapshot_available": True,
                "queue_ahead_contracts": 500.0,
            },
        ))
        updates = Reconciler(ledger).reconcile_shadow_orders([
            _market(decision.market_ticker, 50),
        ])
        assert [update.kind for update in updates] == [OutcomeKind.EXPIRED]
        assert updates[0].detail["reason"] == "shadow_queue_policy_invalidated"
        assert ledger.open_decisions("shadow") == []
    finally:
        ledger.close()


def test_crypto_order_ttl_is_shorter_than_scheduler_interval():
    assert order_ttl_seconds("KXBTC-26JUL10-T100") == 60
    assert order_ttl_seconds("KXHIGHNY-26JUL10-T85") == 45 * 60


def test_shadow_bankroll_includes_only_verified_realized_pnl(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        decision = _decision("d1", "KXBTC-26JUL10-T100")
        ledger.record_decision(decision)
        ledger.record_outcome(asyncio.run(Executor(SessionMode.SHADOW).execute(decision)))
        ledger.record_outcome(TradeOutcome(
            decision_id="d1", market_ticker=decision.market_ticker,
            kind=OutcomeKind.FILLED, order_id="shadow-d1", fill_count=1,
            fill_price_cents=40, pnl_cents=None, broker_contacted=False,
        ))
        ledger.record_outcome(TradeOutcome(
            decision_id="d1", market_ticker=decision.market_ticker,
            kind=OutcomeKind.SETTLED_LOSS, order_id="shadow-d1", fill_count=1,
            fill_price_cents=40, pnl_cents=-40, broker_contacted=False,
        ))
        brain = PredatorBrain(
            SessionMode.SHADOW, ledger, registry=None, scanner=None,
            risk_brain=RiskBrain(tmp_path / "risk.json"),
            executor=Executor(SessionMode.SHADOW),
            reconciler=Reconciler(ledger), learner=Learner(ledger),
        )
        assert ledger.realized_pnl_cents("shadow") == -40
        assert brain._bankroll_cents() == 9_960
    finally:
        ledger.close()


def test_unfilled_settlement_releases_order_without_pnl(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        decision = _decision("d1", "KXBTC-26JUL10-T100")
        ledger.record_decision(decision)
        ledger.record_outcome(asyncio.run(Executor(SessionMode.SHADOW).execute(decision)))
        ledger.record_settlement(decision.market_ticker, True)
        brain = PredatorBrain(
            SessionMode.SHADOW, ledger, registry=None, scanner=None,
            risk_brain=RiskBrain(tmp_path / "risk.json"),
            executor=Executor(SessionMode.SHADOW),
            reconciler=Reconciler(ledger), learner=Learner(ledger),
        )
        state = brain.risk_brain.load_state(10_000)
        brain._close_settled_positions(state)
        assert ledger.open_decisions("shadow") == []
        performance = ledger.performance_summary()
        assert performance["realized_pnl_cents"] == 0
        assert performance["execution_quality"]["orders_with_confirmed_fill"] == 0
        latest = ledger._conn.execute(
            "SELECT kind FROM outcomes WHERE decision_id='d1' ORDER BY id DESC LIMIT 1"
        ).fetchone()[0]
        assert latest == OutcomeKind.EXPIRED.value
    finally:
        ledger.close()


def test_partial_fill_survives_cancel_as_open_position(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        decision = _decision("d1", "KXMLBGAME-26JUL10-ABC", count=3)
        ledger.record_decision(decision)
        for kind, filled in [
            (OutcomeKind.ACCEPTED, 0),
            (OutcomeKind.PARTIALLY_FILLED, 1),
            (OutcomeKind.CANCELED, 1),
        ]:
            ledger.record_outcome(TradeOutcome(
                decision_id="d1", market_ticker=decision.market_ticker, kind=kind,
                order_id="o1", fill_count=filled, fill_price_cents=40,
                pnl_cents=None, broker_contacted=True,
            ))
        position = ledger.open_decisions("live")[0]
        assert position["filled_count"] == 1
        assert position["reserved_count"] == 1
        assert position["order_active"] == 0
    finally:
        ledger.close()


def test_backtest_reports_policy_skill_and_rejects_unverified_pnl(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        for i, result in enumerate([True, True, False, True]):
            ticker = f"KXBTC-TEST-{i}"
            decision = _decision(f"d{i}", ticker)
            ledger.record_decision(decision)
            ledger.record_settlement(ticker, result)
        ledger.record_outcome(TradeOutcome(
            decision_id="d0", market_ticker="KXBTC-TEST-0",
            kind=OutcomeKind.SETTLED_WIN, order_id="shadow-d0", fill_count=1,
            fill_price_cents=40, pnl_cents=60, broker_contacted=False,
        ))
        report = run_backtest(ledger)
        assert report["decision_policy"]["settled_markets"] == 4
        assert report["decision_policy"]["ensemble_metrics"]["n"] == 4
        assert len(report["decision_policy"]["counterfactual_mid_taker_thresholds"]) == 10
        assert report["graded_decisions"] == 0
        assert report["unverified_settlement_outcomes"] == 1
    finally:
        ledger.close()


def test_source_grading_uses_decision_time_not_near_settlement_update(tmp_path):
    from autonomy.ontology import Signal

    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        ticker = "KXBTC-DECISION-TIME"
        early = "2026-07-09T10:00:00+00:00"
        decision_time = "2026-07-09T10:01:00+00:00"
        late = "2026-07-09T11:00:00+00:00"
        ledger.record_signal(Signal(
            source="market_prior", market_ticker=ticker, probability_yes=0.40,
            uncertainty=0.05, rationale="", created_at=early,
        ))
        ledger.record_signal(Signal(
            source="model", market_ticker=ticker, probability_yes=0.80,
            uncertainty=0.05, rationale="", created_at=early,
        ))
        ledger.record_decision(_decision("d1", ticker, created_at=decision_time))
        # Near settlement the market catches up and the model degrades. These
        # are not the opinions that produced the decision and must not grade it.
        ledger.record_signal(Signal(
            source="market_prior", market_ticker=ticker, probability_yes=0.99,
            uncertainty=0.01, rationale="", created_at=late,
        ))
        ledger.record_signal(Signal(
            source="model", market_ticker=ticker, probability_yes=0.20,
            uncertainty=0.05, rationale="", created_at=late,
        ))
        ledger.record_settlement(ticker, True)
        report = run_backtest(ledger)
        assert report["sources"]["model"]["mean_brier"] == 0.04
        assert report["sources"]["model"]["contested_net_brier_edge"] > 0
    finally:
        ledger.close()


def test_signal_intake_persists_features_and_quarantines_bad_or_duplicate_rows(tmp_path):
    from autonomy.ontology import Signal

    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        created_at = datetime.now(timezone.utc).isoformat()
        good = Signal(
            source="model", market_ticker="KXBTC-INTAKE", probability_yes=0.61,
            uncertainty=0.08, rationale="point in time",
            features={"spot": 101_234.5, "window_hours": 168}, created_at=created_at,
        )
        assert ledger.record_signal(good) is True
        assert ledger.record_signal(good) is False
        bad = Signal(
            source="model", market_ticker="KXBTC-BAD", probability_yes=float("nan"),
            uncertainty=0.08, rationale="bad", created_at=created_at,
        )
        assert ledger.record_signal(bad) is False

        row = ledger._conn.execute(
            "SELECT features,ingest_version,ingested_at FROM signals WHERE market_ticker=?",
            (good.market_ticker,),
        ).fetchone()
        assert json.loads(row[0]) == good.features
        assert row[1] == 2
        assert row[2]
        quality = ledger.signal_quality_summary()
        assert quality["signals_stored"] == 1
        assert quality["feature_payload_rows"] == 1
        assert quality["quarantine_reasons"] == {
            "duplicate_signal": 1,
            "probability_out_of_range": 1,
        }
        assert quality["blocking_issues"] == []
    finally:
        ledger.close()


def test_retro_signal_pair_is_atomic_on_quality_failure(tmp_path):
    from autonomy.ontology import Signal

    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        created_at = "2026-07-08T12:00:00+00:00"
        pair = [
            Signal("market_prior", "PAIR", 0.4, 0.1, "", created_at=created_at),
            Signal("model", "PAIR", 1.2, 0.1, "", created_at=created_at),
        ]
        assert ledger.record_signals(pair, mode="retro", all_or_none=True) == [False, False]
        assert ledger._conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0] == 0
        reasons = dict(ledger._conn.execute(
            "SELECT reason,COUNT(*) FROM signal_rejections GROUP BY reason"
        ))
        assert reasons == {"batch_rejected": 1, "probability_out_of_range": 1}
    finally:
        ledger.close()


def test_backtest_adds_cluster_uncertainty_and_point_in_time_walk_forward(tmp_path):
    from autonomy.ontology import Signal

    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        start = datetime(2026, 7, 7, 0, 0, tzinfo=timezone.utc)
        for cluster_index in range(4):
            for market_index in range(10):
                ticker = f"KXBTC-{7 + cluster_index:02d}JUL2601-T{market_index:02d}"
                created = start + timedelta(hours=cluster_index * 3, minutes=market_index)
                signal_time = (created - timedelta(seconds=1)).isoformat()
                ledger.record_signal(Signal(
                    "market_prior", ticker, 0.4, 0.1, "", created_at=signal_time,
                ))
                ledger.record_signal(Signal(
                    "model", ticker, 0.8, 0.1, "", created_at=signal_time,
                ))
                ledger.record_decision(_decision(
                    f"cluster-{cluster_index}-{market_index}", ticker,
                    created_at=created.isoformat(),
                ))
                ledger.record_settlement(ticker, True)
                ledger._conn.execute(
                    "UPDATE settlements SET settled_at=? WHERE market_ticker=?",
                    ((created + timedelta(minutes=30)).isoformat(), ticker),
                )
        ledger._conn.commit()
        report = run_backtest(ledger)
        policy = report["decision_policy"]
        assert policy["settled_markets"] == 40
        assert policy["event_clusters"] == 4
        assert policy["cluster_robust_advantage"]["brier"]["lower"] > 0
        assert policy["ensemble_metrics"]["expected_calibration_error"] is not None
        walk_forward = policy["walk_forward_threshold_selection"]
        assert walk_forward["folds"] == 3
        assert walk_forward["aggregate_out_of_sample"]["trades"] > 0
        assert walk_forward["aggregate_out_of_sample"]["net_pnl_cents"] > 0
    finally:
        ledger.close()
