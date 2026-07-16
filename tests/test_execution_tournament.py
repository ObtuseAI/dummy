"""Tests for the Phase-A execution-policy tournament (WS-A2/F2).

Builds a synthetic ledger through the real ``AutonomyLedger`` API (so the
actionable-surface reconstruction runs against the production schema) with a
mix of fast/slow adversely-selected maker fills and unfilled winners, then
asserts the cohort semantics: C0 reproduces the witnessed maker fills, taker
cohorts hold the full surface, C3 censors adverse fills, C4 keeps only
in-window maker fills, the C2 threshold is walk-forward-selected and disclosed,
every interval is cluster-level, and the report is evidence-only.
"""
from __future__ import annotations

import json

from autonomy.execution_policy import ExecutionPolicy
from autonomy.execution_tournament import (
    MIN_FILL_CLUSTERS,
    cohort_trades,
    summarize_tournament,
    tournament_report,
    write_report,
)
from autonomy.adverse_selection import load_execution_rows
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
T_FAST = "2026-06-01T00:00:30+00:00"  # 30s after submit (fast cross)
T_SLOW = "2026-06-01T00:05:00+00:00"  # 300s after submit
T_SETTLE = "2026-06-02T00:00:00+00:00"


def _ticker(index: int) -> str:
    return f"KXTESTMKT{index:03d}-26JUN01-A"


def _emit(
    ledger: AutonomyLedger, index: int, *, side: str, price: int, forecast_p: float,
    market_p: float, filled: bool, result_yes: bool, witness: str = T_SLOW,
) -> None:
    ticker = _ticker(index)
    did = f"d{index:04d}"
    ledger.record_signal(Signal(
        source="market_prior", market_ticker=ticker, probability_yes=market_p,
        uncertainty=0.1, rationale="", created_at=T0,
    ))
    forecast = Forecast(
        market_ticker=ticker, probability_yes=forecast_p, uncertainty=0.1,
        sources_used={"market_prior": 1.0}, market_implied_yes=market_p,
        edge_yes=forecast_p - market_p, rationale="",
    )
    ledger.record_decision(Decision(
        decision_id=did, market_ticker=ticker,
        action=DecisionAction.BUY_YES if side == "yes" else DecisionAction.BUY_NO,
        side=side, price_cents=price, count=1, ev_cents_per_contract=1.0,
        kelly_fraction=0.1, notional_cents=price, forecast=forecast,
        risk_snapshot={}, created_at=T0,
    ))
    ledger.record_outcome(TradeOutcome(
        decision_id=did, market_ticker=ticker, kind=OutcomeKind.SHADOW,
        order_id=f"s-{did}", fill_count=0, fill_price_cents=price, pnl_cents=None,
        broker_contacted=False, detail={"state": "resting"}, created_at=T0,
    ))
    if filled:
        ledger.record_outcome(TradeOutcome(
            decision_id=did, market_ticker=ticker, kind=OutcomeKind.FILLED,
            order_id=f"s-{did}", fill_count=1, fill_price_cents=price, pnl_cents=None,
            broker_contacted=False,
            detail={"fill_witness_at": witness, "observed_ask_cents": price - 2},
            created_at=witness,
        ))
        pnl = settlement_pnl_cents(side, price, 1, result_yes, ticker, "maker")
        ledger.record_outcome(TradeOutcome(
            decision_id=did, market_ticker=ticker,
            kind=OutcomeKind.SETTLED_WIN if pnl > 0 else OutcomeKind.SETTLED_LOSS,
            order_id=f"s-{did}", fill_count=1, fill_price_cents=price, pnl_cents=pnl,
            broker_contacted=False, detail={"result_yes": result_yes},
            created_at=T_SETTLE,
        ))
    else:
        ledger.record_outcome(TradeOutcome(
            decision_id=did, market_ticker=ticker, kind=OutcomeKind.EXPIRED,
            order_id=f"s-{did}", fill_count=0, fill_price_cents=None, pnl_cents=None,
            broker_contacted=False, detail={"reason": "ttl"}, created_at=T_SETTLE,
        ))
    ledger.record_settlement(ticker, result_yes)


def _tournament_ledger(tmp_path) -> AutonomyLedger:
    """Adverse-selection signature: filled maker book bleeds, unfilled wins.

    - 6 fast (30s) fills, wide divergence (0.80 vs 0.50), resolve NO -> wrong.
    - 6 slow (300s) fills, narrow divergence (0.60 vs 0.55), resolve NO -> wrong.
    - 12 unfilled quotes, wide divergence, resolve YES -> the edge we never get.
    """
    ledger = AutonomyLedger(db_path=tmp_path / "tournament.db")
    idx = 0
    for _ in range(6):
        _emit(ledger, idx, side="yes", price=48, forecast_p=0.80, market_p=0.50,
              filled=True, result_yes=False, witness=T_FAST)
        idx += 1
    for _ in range(6):
        _emit(ledger, idx, side="yes", price=54, forecast_p=0.60, market_p=0.55,
              filled=True, result_yes=False, witness=T_SLOW)
        idx += 1
    for _ in range(12):
        _emit(ledger, idx, side="yes", price=48, forecast_p=0.80, market_p=0.50,
              filled=False, result_yes=True)
        idx += 1
    return ledger


def test_report_has_all_five_cohorts_control_first(tmp_path):
    ledger = _tournament_ledger(tmp_path)
    try:
        report = tournament_report(ledger._conn)
    finally:
        ledger.close()
    assert report["report_name"] == "EXECUTION_POLICY_TOURNAMENT"
    cohorts = [c["policy"]["cohort"] for c in report["cohorts"]]
    assert cohorts == ["C0", "C1", "C2", "C3", "C4"]
    assert report["actionable_settled_decisions"] == 24
    assert report["control_cohort"] == "C0"


def test_c0_reproduces_witnessed_maker_fills(tmp_path):
    ledger = _tournament_ledger(tmp_path)
    try:
        rows = load_execution_rows(ledger._conn)
        control = next(
            c for c in tournament_report(ledger._conn)["cohorts"]
            if c["policy"]["cohort"] == "C0"
        )
    finally:
        ledger.close()
    witnessed = sum(1 for r in rows if r["filled"])
    assert control["fills"] == witnessed == 12
    # The incumbent maker book is a net loser on this surface.
    assert control["net_pnl_cents"] < 0
    assert control["win_rate"] == 0.0


def test_taker_cohort_holds_full_actionable_surface(tmp_path):
    ledger = _tournament_ledger(tmp_path)
    try:
        report = tournament_report(ledger._conn)
    finally:
        ledger.close()
    c1 = next(c for c in report["cohorts"] if c["policy"]["cohort"] == "C1")
    # A taker crosses the whole actionable set, not just the crossed subset.
    assert c1["fills"] == 24
    assert c1["fill_rate"] == 1.0


def test_c3_censors_fast_and_divergent_fills(tmp_path):
    ledger = _tournament_ledger(tmp_path)
    try:
        rows = load_execution_rows(ledger._conn)
    finally:
        ledger.close()
    c3 = ExecutionPolicy.adverse_guard_maker()
    kept = cohort_trades(rows, c3)
    # Fast fills (<=60s) and wide-divergence (>10c) fills are both dropped; only
    # the 6 slow narrow-divergence (0.60 vs 0.55 => 5c) fills survive.
    assert len(kept) == 6
    control = cohort_trades(rows, ExecutionPolicy.maker_only_control())
    assert len(kept) < len(control)


def test_c4_keeps_in_window_maker_fills_and_crosses_the_rest(tmp_path):
    ledger = _tournament_ledger(tmp_path)
    try:
        rows = load_execution_rows(ledger._conn)
    finally:
        ledger.close()
    trades = cohort_trades(rows, ExecutionPolicy.hybrid_patient_then_take())
    # 6 fast maker fills stay maker; 6 slow + 12 unfilled cross as taker => 24.
    assert len(trades) == 24


def test_c2_threshold_is_walk_forward_selected_and_disclosed(tmp_path):
    ledger = _tournament_ledger(tmp_path)
    try:
        report = tournament_report(ledger._conn)
    finally:
        ledger.close()
    wf = report["c2_walk_forward_threshold_selection"]
    assert wf["folds"] >= 1
    # Each fold discloses which threshold it picked out-of-sample.
    assert len(wf["selected_thresholds_by_fold"]) == wf["folds"]
    assert all(isinstance(t, int) for t in wf["selected_thresholds_by_fold"])
    c2 = next(c for c in report["cohorts"] if c["policy"]["cohort"] == "C2")
    assert c2["policy"]["edge_threshold_walk_forward_selected"] is True
    assert c2["evidence_basis"] == "walk_forward_out_of_sample"


def test_gate_and_ranking_and_switch_authority(tmp_path):
    ledger = _tournament_ledger(tmp_path)
    try:
        report = tournament_report(ledger._conn)
    finally:
        ledger.close()
    # Small synthetic: no cohort clears the 40-cluster gate.
    assert report["min_fill_clusters_gate"] == MIN_FILL_CLUSTERS
    assert all(
        c["gate_status"] == "insufficient_clusters" for c in report["cohorts"]
    )
    assert report["headline"]["any_cohort_gate_eligible"] is False
    # Ranking covers every cohort exactly once, ranks are 1..5.
    ranked = report["ranking"]
    assert [r["rank"] for r in ranked] == [1, 2, 3, 4, 5]
    assert {r["cohort"] for r in ranked} == {"C0", "C1", "C2", "C3", "C4"}
    # Evidence only: never an automatic switch.
    assert report["policy_switch_authority"]["auto_switch"] is False


def test_pnl_difference_vs_control_is_cluster_level(tmp_path):
    ledger = _tournament_ledger(tmp_path)
    try:
        report = tournament_report(ledger._conn)
    finally:
        ledger.close()
    c1 = next(c for c in report["cohorts"] if c["policy"]["cohort"] == "C1")
    diff = c1["pnl_vs_control_cents_ci95"]
    assert diff is not None
    assert diff["method"] == "event_cluster_bootstrap_95"
    assert "lower" in diff and "upper" in diff
    # The control's own vs-control diff is omitted.
    c0 = next(c for c in report["cohorts"] if c["policy"]["cohort"] == "C0")
    assert c0["pnl_vs_control_cents_ci95"] is None


def test_summarize_and_write_roundtrip(tmp_path):
    ledger = _tournament_ledger(tmp_path)
    try:
        report = tournament_report(ledger._conn)
    finally:
        ledger.close()
    summary = summarize_tournament(report)
    assert summary["report_name"] == "EXECUTION_POLICY_TOURNAMENT"
    assert summary["ranking"]
    assert "policy_switch_authority" in summary
    path = tmp_path / "execution_tournament.json"
    write_report(report, path)
    reloaded = json.loads(path.read_text(encoding="utf-8"))
    assert reloaded["report_name"] == report["report_name"]


def test_empty_ledger_is_handled(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "empty.db")
    try:
        report = tournament_report(ledger._conn)
    finally:
        ledger.close()
    assert report["actionable_settled_decisions"] == 0
    assert report["policy_switch_authority"]["auto_switch"] is False


def test_deterministic(tmp_path):
    ledger = _tournament_ledger(tmp_path)
    try:
        first = tournament_report(ledger._conn)
        second = tournament_report(ledger._conn)
    finally:
        ledger.close()
    # Drop the wall-clock stamp before comparing.
    first.pop("generated_at")
    second.pop("generated_at")
    assert json.dumps(first, sort_keys=True) == json.dumps(second, sort_keys=True)
