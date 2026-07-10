from __future__ import annotations

import json

from autonomy.drift import adwin_drift_report
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import OutcomeKind, Signal, TradeOutcome
from autonomy.portfolio_challenger import PortfolioCandidate, solve_portfolio_challenger
from autonomy.research_snapshot import export_research_snapshot


def test_adwin_identifies_material_negative_shift():
    report = adwin_drift_report([0.0] * 200 + [0.2] * 200)
    assert report["available"] is True
    assert report["drift_detected"] is True
    assert report["negative_drift"] is True


def test_adwin_stationary_stream_does_not_false_alarm():
    report = adwin_drift_report([0.01] * 400)
    assert report["drift_detected"] is False
    assert report["negative_drift"] is False


def test_portfolio_challenger_respects_budget_positions_and_groups():
    candidates = [
        PortfolioCandidate("a", "KXBTC-A", "BUY_YES", 60, 30.0, "crypto", "1"),
        PortfolioCandidate("b", "KXBTC-B", "BUY_YES", 40, 25.0, "crypto", "2"),
        PortfolioCandidate("c", "KXHIGHNY-C", "BUY_NO", 50, 20.0, "weather", "3"),
    ]
    report = solve_portfolio_challenger(
        candidates, budget_cents=100, max_positions=2, max_group_cost_cents=60,
    )
    assert report["execution_authority"] is False
    assert report["total_cost_cents"] <= 100
    assert report["selected_count"] <= 2
    assert {row["decision_id"] for row in report["selected"]} == {"b", "c"}


def test_snapshot_reads_ledger_and_writes_hash_manifest(tmp_path):
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    try:
        ledger.record_signal(Signal(
            source="test", market_ticker="KXTEST", probability_yes=0.6,
            uncertainty=0.1, rationale="fixture",
        ))
    finally:
        ledger.close()
    manifest_path, _manifest = export_research_snapshot(db, tmp_path / "snapshots")
    assert manifest_path.exists()
    stored = json.loads(manifest_path.read_text(encoding="utf-8"))
    signals = next(row for row in stored["tables"] if row["table"] == "signals")
    assert signals["rows"] == 1
    assert len(signals["sha256"]) == 64
    assert (manifest_path.parent / signals["file"]).exists()


def test_execution_summary_reports_fill_uncertainty(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    try:
        for decision_id, final_kind, final_fill in (
            ("filled", OutcomeKind.FILLED, 1),
            ("expired", OutcomeKind.EXPIRED, 0),
        ):
            ledger.record_outcome(TradeOutcome(
                decision_id=decision_id, market_ticker="KXTEST",
                kind=OutcomeKind.SHADOW, order_id=decision_id,
                fill_count=0, fill_price_cents=None, pnl_cents=None,
                broker_contacted=False,
            ))
            ledger.record_outcome(TradeOutcome(
                decision_id=decision_id, market_ticker="KXTEST",
                kind=final_kind, order_id=decision_id, fill_count=final_fill,
                fill_price_cents=50 if final_fill else None, pnl_cents=None,
                broker_contacted=False,
            ))
        summary = ledger.execution_summary("shadow")
        interval = summary["observed_fill_rate_ci95"]
        assert summary["observed_fill_rate"] == 0.5
        assert interval["lower"] < 0.5 < interval["upper"]
        assert summary["orders_with_known_outcome"] == 2
    finally:
        ledger.close()
