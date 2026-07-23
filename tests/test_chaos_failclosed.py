"""Chaos drills (Netflix discipline): inject faults, assert fail-closed degradation.

Every injection asserts the same contract: no exception escapes, no fabricated
data lands, the component abstains/rejects and the system stays coherent.
"""
from __future__ import annotations

import math
from datetime import datetime, timedelta, timezone

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import MarketView, Signal, Vertical


def _market(**overrides):
    base = dict(
        ticker="KXBTC1H-26JUL231500-15", title="", vertical=Vertical.CRYPTO,
        status="active",
        close_time=(datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
        yes_bid=48, yes_ask=52, no_bid=48, no_ask=52,
        volume=100, liquidity=1000, raw={},
    )
    base.update(overrides)
    return MarketView(**base)


def test_ledger_rejects_nan_and_inf_probabilities_without_crashing(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        for bad in (float("nan"), float("inf"), -0.2, 1.7):
            ok = ledger.record_signal(Signal(
                source="chaos", market_ticker="KXBTC1H-26JUL231500-15",
                probability_yes=bad, uncertainty=0.1, rationale="", features={},
            ))
            assert ok is False
        # Quarantined, not crashed; and nothing landed in signals.
        n = ledger._conn.execute("SELECT COUNT(*) FROM signals").fetchone()[0]
        assert n == 0
    finally:
        ledger.close()


def test_reconciler_ignores_garbage_trade_payloads(tmp_path):
    from autonomy.reconciler import Reconciler

    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        def garbage_trades(*_a):
            return [
                {"trade_id": None, "yes_price_dollars": "NaN", "count_fp": "x"},
                {"taker_book_side": "ask", "yes_price_dollars": None, "count_fp": -5},
                "not even a dict lookalike" and {},
            ]

        rec = Reconciler(ledger, fetch_shadow_trades=garbage_trades)
        # No open decisions -> no outcomes; but exercise the fill witness path
        # directly with a fake pending order too.
        pending = {
            "decision_id": "d", "market_ticker": "KXBTC1H-26JUL231500-15",
            "side": "yes", "price_cents": 50, "count": 2,
            "submission_detail": {"queue_snapshot_available": True,
                                  "queue_ahead_contracts": 1.0},
        }
        detail = rec._shadow_trade_fill(pending, 0, 10_000_000_000)
        assert detail is None  # garbage witnesses no fill, raises nothing
    finally:
        ledger.close()


def test_tier_assessment_fails_closed_on_corrupt_market_fields():
    from autonomy.tier_policy import assess_market_tier

    class _Forecast:
        probability_yes = 0.6
        uncertainty = 0.1

    corrupt = _market(
        yes_bid="junk", yes_ask=None, no_bid=float("nan"), no_ask=1e9,
        close_time="not-a-timestamp", raw={"yes_ask_size_fp": "garbage"},
    )
    assessment = assess_market_tier(corrupt, _Forecast())
    assert assessment.tier is None  # never a letter tier from corrupt quotes


def test_matchup_and_board_readers_survive_corrupt_json(tmp_path):
    from autonomy.matchup_lens import build_matchup_report
    from autonomy.recruiting_board import build_recruiting_board
    from autonomy.sports.pbp_params import load_pbp_params

    for name in ("bet_board.json", "last_recalibration.json",
                 "mined_rule_forward_registry.json", "strategy_claims.json",
                 "no_edge_map.json"):
        (tmp_path / name).write_text("{corrupt json!!", encoding="utf-8")
    report = build_matchup_report(
        board_path=tmp_path / "bet_board.json",
        recal_path=tmp_path / "last_recalibration.json",
    )
    assert report["graded"] == []           # degrade, don't die
    board = build_recruiting_board(runtime=tmp_path)
    assert board["class_size"] >= 0
    assert load_pbp_params("nba", path=tmp_path / "bet_board.json") is None


def test_crypto_onchain_signal_survives_feed_exceptions():
    from autonomy.signals.crypto_onchain import CryptoOnchainLiquiditySignal

    def exploding_supply():
        raise RuntimeError("feed down")

    def exploding_state(_asset):
        raise ConnectionError("exchange down")

    signal = CryptoOnchainLiquiditySignal(
        fetch_state=exploding_state,
        fetch_supply=exploding_supply,
        hours_to_close=lambda m: 12.0,
    )
    assert signal.generate(_market()) is None   # abstain, never raise


def test_fee_engine_never_returns_negative_or_nonfinite():
    from autonomy.fees import kalshi_taker_fee_cents

    for price in (1, 50, 99):
        fee = kalshi_taker_fee_cents(price, 1, "KXWHATEVER-1")
        assert isinstance(fee, int) and fee >= 0 and math.isfinite(fee)
