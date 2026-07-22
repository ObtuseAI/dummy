"""Tests for the first-class adverse-selection instrumentation (WS-A1).

Builds a synthetic ledger through the real ``AutonomyLedger`` API so the
reconstruction SQL is exercised against the production schema, then asserts the
adverse-selection signature: the maker-filled subset is worse than both the
unfilled subset and a taker counterfactual, every interval is cluster-level,
and the pass is deterministic and read-only.
"""
from __future__ import annotations

import sqlite3

from autonomy.adverse_selection import (
    adverse_selection_report,
    load_execution_rows,
    write_report,
)
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import (
    Decision,
    DecisionAction,
    Forecast,
    OutcomeKind,
    Signal,
    TradeOutcome,
)
from autonomy.reconciler import settlement_pnl_cents

T0 = "2026-06-01T00:00:00+00:00"
T_FILL = "2026-06-01T00:05:00+00:00"  # 300s after submit
T_SETTLE = "2026-06-02T00:00:00+00:00"


def _ticker(index: int) -> str:
    return f"KXTESTMKT{index:03d}-26JUN01-A"


def _record_decision(
    ledger: AutonomyLedger, decision_id: str, ticker: str, *, side: str,
    price: int, forecast_p: float, market_p: float, count: int = 1,
) -> None:
    forecast = Forecast(
        market_ticker=ticker, probability_yes=forecast_p, uncertainty=0.1,
        sources_used={"market_prior": 1.0}, market_implied_yes=market_p,
        edge_yes=forecast_p - market_p, rationale="",
    )
    action = DecisionAction.BUY_YES if side == "yes" else DecisionAction.BUY_NO
    ledger.record_decision(Decision(
        decision_id=decision_id, market_ticker=ticker, action=action, side=side,
        price_cents=price, count=count, ev_cents_per_contract=1.0, kelly_fraction=0.1,
        notional_cents=price * count, forecast=forecast, risk_snapshot={}, created_at=T0,
    ))


def _submit(ledger: AutonomyLedger, decision_id: str, ticker: str, price: int) -> None:
    ledger.record_outcome(TradeOutcome(
        decision_id=decision_id, market_ticker=ticker, kind=OutcomeKind.SHADOW,
        order_id=f"shadow-{decision_id}", fill_count=0, fill_price_cents=price,
        pnl_cents=None, broker_contacted=False,
        detail={"state": "resting"}, created_at=T0,
    ))


def _fill_and_settle(
    ledger: AutonomyLedger, decision_id: str, ticker: str, *, side: str,
    price: int, result_yes: bool, count: int = 1, fill_witness_at: str = T_FILL,
    observed_ask_cents: int | None = None,
) -> None:
    detail = {"reason": "shadow_maker_observed_cross", "fill_witness_at": fill_witness_at,
              "conservative_fill_price_cents": price}
    if observed_ask_cents is not None:
        detail["observed_ask_cents"] = observed_ask_cents
    ledger.record_outcome(TradeOutcome(
        decision_id=decision_id, market_ticker=ticker, kind=OutcomeKind.FILLED,
        order_id=f"shadow-{decision_id}", fill_count=count, fill_price_cents=price,
        pnl_cents=None, broker_contacted=False, detail=detail, created_at=fill_witness_at,
    ))
    pnl = settlement_pnl_cents(side, price, count, result_yes, ticker, "maker")
    ledger.record_outcome(TradeOutcome(
        decision_id=decision_id, market_ticker=ticker,
        kind=OutcomeKind.SETTLED_WIN if pnl > 0 else OutcomeKind.SETTLED_LOSS,
        order_id=f"shadow-{decision_id}", fill_count=count, fill_price_cents=price,
        pnl_cents=pnl, broker_contacted=False, detail={"result_yes": result_yes},
        created_at=T_SETTLE,
    ))
    ledger.record_settlement(ticker, result_yes)


def _expire_and_settle(
    ledger: AutonomyLedger, decision_id: str, ticker: str, result_yes: bool,
) -> None:
    ledger.record_outcome(TradeOutcome(
        decision_id=decision_id, market_ticker=ticker, kind=OutcomeKind.EXPIRED,
        order_id=f"shadow-{decision_id}", fill_count=0, fill_price_cents=None,
        pnl_cents=None, broker_contacted=False,
        detail={"reason": "shadow_maker_ttl_expired_unfilled"}, created_at=T_SETTLE,
    ))
    ledger.record_settlement(ticker, result_yes)


def _adverse_ledger(tmp_path) -> AutonomyLedger:
    """12 confidently-wrong fills + 12 confidently-right expiries.

    Filled: BUY YES at forecast 0.8 while the market says 0.5, price 48, and the
    market resolves NO -> the maker keeps filling exactly when the model is
    wrong. Unfilled: same forecast/market but the market resolves YES and the
    quote expires -> the model's edge is real precisely on the trades it never
    gets. This is the adverse-selection signature in miniature.
    """
    ledger = AutonomyLedger(db_path=tmp_path / "adverse.db")
    for i in range(12):
        ticker = _ticker(i)
        did = f"fill{i:03d}"
        ledger.record_signal(Signal(source="market_prior", market_ticker=ticker,
                                     probability_yes=0.5, uncertainty=0.1, rationale="",
                                     created_at=T0))
        _record_decision(ledger, did, ticker, side="yes", price=48,
                         forecast_p=0.8, market_p=0.5)
        _submit(ledger, did, ticker, 48)
        _fill_and_settle(ledger, did, ticker, side="yes", price=48, result_yes=False,
                         observed_ask_cents=46)
    for i in range(12, 24):
        ticker = _ticker(i)
        did = f"miss{i:03d}"
        ledger.record_signal(Signal(source="market_prior", market_ticker=ticker,
                                     probability_yes=0.5, uncertainty=0.1, rationale="",
                                     created_at=T0))
        _record_decision(ledger, did, ticker, side="yes", price=48,
                         forecast_p=0.8, market_p=0.5)
        _submit(ledger, did, ticker, 48)
        _expire_and_settle(ledger, did, ticker, result_yes=True)
    return ledger


def test_load_execution_rows_partitions_filled_and_unfilled(tmp_path):
    ledger = _adverse_ledger(tmp_path)
    try:
        rows = load_execution_rows(ledger._conn)
    finally:
        ledger.close()
    assert len(rows) == 24
    filled = [r for r in rows if r["filled"]]
    unfilled = [r for r in rows if not r["filled"]]
    assert len(filled) == 12
    assert len(unfilled) == 12
    # Filled rows carry a realized P&L and a fill latency; unfilled carry none.
    assert all(r["realized_pnl_cents"] is not None for r in filled)
    assert all(r["delay_seconds"] == 300.0 for r in filled)
    assert all(r["realized_pnl_cents"] is None for r in unfilled)


def test_fill_conditioned_slice_shows_maker_worse_than_taker_and_unfilled(tmp_path):
    ledger = _adverse_ledger(tmp_path)
    try:
        report = adverse_selection_report(ledger._conn)
    finally:
        ledger.close()

    slice_ = report["fill_conditioned_slice"]
    maker = slice_["maker_filled"]
    unfilled = slice_["unfilled"]
    full = slice_["full_surface_actionable"]

    # The filled subset is calibrated far worse than the unfilled subset.
    assert maker["forecast_brier"] > unfilled["forecast_brier"]
    assert maker["brier_skill_vs_market"] < 0.0  # maker fills trail the market
    assert unfilled["brier_skill_vs_market"] > 0.0  # the model's edge lives here

    # Realized maker P&L is negative; a taker over the whole actionable set,
    # which also captures the winning trades the maker never fills, does better.
    maker_pnl = maker["maker_execution_realized"]["net_pnl_cents"]
    taker_pnl = full["taker_execution_per_contract"]["net_pnl_cents"]
    assert maker_pnl < 0
    assert taker_pnl > maker_pnl
    assert maker["maker_execution_realized"]["win_rate"] == 0.0


def test_fill_vs_nofill_delta_is_the_direct_adverse_number(tmp_path):
    ledger = _adverse_ledger(tmp_path)
    try:
        report = adverse_selection_report(ledger._conn)
    finally:
        ledger.close()
    delta = report["adverse_selection_metrics"]["fill_vs_nofill_outcome_delta"]
    assert delta["filled_minus_unfilled_brier"] > 0.0
    # Filled edge vs market is negative, unfilled positive -> selection of errors.
    assert delta["filled_cluster_robust_brier_edge_vs_market"]["mean"] < 0.0
    assert delta["unfilled_cluster_robust_brier_edge_vs_market"]["mean"] > 0.0


def test_slippage_is_illusory_model_bargain(tmp_path):
    ledger = _adverse_ledger(tmp_path)
    try:
        report = adverse_selection_report(ledger._conn)
    finally:
        ledger.close()
    slip = report["adverse_selection_metrics"]["per_fill_slippage"]
    assert slip["fills"] == 12
    # Model thinks it fills ~32c below fair (0.8*100 - 48); the market prices the
    # fill nearly fairly (~2c). The model "bargain" is adverse information.
    assert slip["model_slippage_cents"]["mean"] > 25.0
    assert abs(slip["market_slippage_cents"]["mean"]) < 5.0
    # Slippage does not separate winners from losers (here: all losers present).
    assert slip["mean_model_slippage_on_losing_fills"] is not None


def test_all_intervals_are_cluster_level(tmp_path):
    ledger = _adverse_ledger(tmp_path)
    try:
        report = adverse_selection_report(ledger._conn)
    finally:
        ledger.close()
    assert report["adverse_selection_metrics"]["all_intervals_are_cluster_level"] is True
    maker = report["fill_conditioned_slice"]["maker_filled"]
    ci = maker["maker_execution_realized"]["cluster_robust_mean_pnl_ci95"]
    assert ci["method"] == "event_cluster_bootstrap_95"
    # 12 distinct event clusters -> a real (non-collapsed) interval.
    assert ci["clusters"] == 12
    assert ci["lower"] <= ci["mean"] <= ci["upper"]
    edge_ci = maker["cluster_robust_brier_edge_vs_market"]
    assert edge_ci["clusters"] == 12


def test_time_to_fill_buckets_present(tmp_path):
    ledger = _adverse_ledger(tmp_path)
    try:
        report = adverse_selection_report(ledger._conn)
    finally:
        ledger.close()
    ttf = report["adverse_selection_metrics"]["time_to_fill_vs_market_move"]
    labels = {bucket["bucket"] for bucket in ttf["by_latency_bucket"]}
    assert labels == {"fast_le_60s", "mid_60_300s", "slow_gt_300s"}
    # Every synthetic fill is witnessed 300s out -> the mid bucket (60 <= t < 300)
    # since 300 is the exclusive upper edge -> lands in slow.
    slow = next(b for b in ttf["by_latency_bucket"] if b["bucket"] == "slow_gt_300s")
    assert slow["fills"] == 12
    assert ttf["market_cross_depth_cents"]["mean"] is not None


def test_report_is_deterministic_and_readonly(tmp_path):
    ledger = _adverse_ledger(tmp_path)
    try:
        first = adverse_selection_report(ledger._conn)
        second = adverse_selection_report(ledger._conn)
    finally:
        ledger.close()
    first.pop("generated_at")
    second.pop("generated_at")
    assert first == second


def test_empty_ledger_is_well_formed(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "empty.db")
    try:
        report = adverse_selection_report(ledger._conn)
    finally:
        ledger.close()
    assert report["actionable_settled_decisions"] == 0
    assert "note" in report


def test_write_report_round_trips(tmp_path):
    import json

    ledger = _adverse_ledger(tmp_path)
    try:
        report = adverse_selection_report(ledger._conn)
    finally:
        ledger.close()
    out = tmp_path / "adverse_selection.json"
    write_report(report, out)
    assert out.exists()
    assert not out.with_suffix(".tmp").exists()
    loaded = json.loads(out.read_text(encoding="utf-8"))
    assert loaded["report_name"] == "EXECUTION_ADVERSE_SELECTION"


def test_backtest_summary_embeds_adverse_selection(tmp_path):
    from autonomy.backtest import run_backtest

    ledger = _adverse_ledger(tmp_path)
    try:
        report = run_backtest(ledger)
    finally:
        ledger.close()
    adverse = report["execution_adverse_selection"]
    assert adverse["report_name"] == "EXECUTION_ADVERSE_SELECTION"
    assert adverse["maker_filled_decisions"] == 12
    assert adverse["headline"]["maker_realized_net_pnl_cents"] < 0
    taker = adverse["fill_conditioned_slice"]["full_surface_actionable"][
        "taker_execution_per_contract"
    ]
    assert adverse["headline"]["taker_full_surface_net_pnl_cents"] == taker[
        "net_pnl_cents"
    ]
    assert adverse["headline"][
        "taker_full_surface_mean_pnl_cents_per_contract"
    ] == taker["average_pnl_cents"]
    assert (
        "taker_full_surface_net_pnl_cents_per_contract" not in adverse["headline"]
    )


def _readonly_conn(path) -> sqlite3.Connection:
    return sqlite3.connect(f"file:{path}?mode=ro", uri=True)


def test_runs_against_readonly_connection(tmp_path):
    ledger = _adverse_ledger(tmp_path)
    db_path = ledger.db_path
    ledger.close()
    conn = _readonly_conn(db_path)
    try:
        report = adverse_selection_report(conn)
    finally:
        conn.close()
    assert report["maker_filled_decisions"] == 12
