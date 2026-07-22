from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone

import pytest

from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Decision, DecisionAction, Forecast
from autonomy.simulation_training import (
    bounded_database_liveness,
    compounding_stress,
    connect_readonly,
    execution_curriculum,
    forecast_curriculum,
    load_order_rows,
    run_simulation_training,
    write_simulation_training_report,
)


def _rows(count: int = 120) -> list[dict]:
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    rows = []
    for index in range(count):
        result = index % 4 != 0
        created = start + timedelta(days=index)
        rows.append({
            "ticker": f"SIM-{index:04d}",
            "cluster": f"cluster-{index:04d}",
            "forecast": 0.75 if result else 0.25,
            "market": 0.50,
            "uncertainty": 0.10,
            "result": int(result),
            "created_at": created,
            "settled_at": created + timedelta(hours=1),
        })
    return rows


def test_forecast_curriculum_is_report_only_and_out_of_sample():
    report, trades = forecast_curriculum(_rows())
    assert report["available"] is True
    assert len(report["folds"]) >= 3
    assert report["auto_apply"] is False
    assert trades
    for fold in report["folds"]:
        assert fold["training_latest_settlement"] < fold["test_start"]


def test_compounding_stress_is_deterministic_and_never_live():
    _report, trades = forecast_curriculum(_rows())
    first = compounding_stress(trades, simulations=100, seed=7)
    second = compounding_stress(trades, simulations=100, seed=7)
    assert first == second
    assert first["live_application"] is False
    assert {row["extra_slippage_cents"] for row in first["results"]} == {0, 2, 5}
    assert first["minimum_median_positions"] >= 10


def test_compounding_does_not_call_underdeployment_safe():
    _report, trades = forecast_curriculum(_rows())
    result = compounding_stress(trades, simulations=100, seed=7)
    low = next(row for row in result["results"]
               if row["risk_fraction"] == 0.0025 and row["extra_slippage_cents"] == 5)
    if low["median_positions_used"] < result["minimum_median_positions"]:
        assert result["highest_stress_safe_fraction"] != 0.0025


def test_execution_curriculum_refuses_low_settled_evidence():
    rows = [{
        "decision_id": str(index), "ticker": f"SIM-{index}",
        "price_cents": 20, "ev_cents": 10.0, "uncertainty": 0.1,
        "submitted_at": "2025-01-01T00:00:00+00:00", "queue_ahead": 0.0,
        "filled": index < 10, "known": True,
        "settled_pnl_cents": -20 if index < 5 else None,
    } for index in range(30)]
    report = execution_curriculum(rows)
    assert report["status"] == "HOLD"
    assert report["auto_apply"] is False
    assert report["overall"]["settled_net_pnl_cents"] == -100


def test_execution_loader_rejects_settlement_without_prior_fill(tmp_path):
    from autonomy.ontology import OutcomeKind, TradeOutcome

    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    try:
        forecast = Forecast(
            market_ticker="SIM-ORDER", probability_yes=0.7, uncertainty=0.1,
            sources_used={"fixture": 1.0}, market_implied_yes=0.5,
            edge_yes=0.2, rationale="fixture",
        )
        ledger.record_decision(Decision(
            decision_id="d", market_ticker="SIM-ORDER", action=DecisionAction.BUY_YES,
            side="yes", price_cents=40, count=1, ev_cents_per_contract=10,
            kelly_fraction=0.1, notional_cents=40, forecast=forecast,
            risk_snapshot={},
        ))
        ledger.record_outcome(TradeOutcome(
            decision_id="d", market_ticker="SIM-ORDER", kind=OutcomeKind.SHADOW,
            order_id="shadow-d", fill_count=0, fill_price_cents=None, pnl_cents=None,
            broker_contacted=False,
        ))
        # A legacy/phantom settlement row may carry a requested count. It is
        # not transport or market evidence that the resting order filled.
        ledger.record_outcome(TradeOutcome(
            decision_id="d", market_ticker="SIM-ORDER", kind=OutcomeKind.SETTLED_WIN,
            order_id="shadow-d", fill_count=1, fill_price_cents=40, pnl_cents=60,
            broker_contacted=False,
        ))
    finally:
        ledger.close()
    from autonomy.simulation_training import connect_readonly

    connection = connect_readonly(db)
    try:
        rows = load_order_rows(connection)
    finally:
        connection.close()
    assert len(rows) == 1
    assert rows[0]["filled"] is False
    assert rows[0]["settled_pnl_cents"] is None


def test_training_opens_ledger_read_only_and_quarantines_simulation(
    tmp_path, monkeypatch,
):
    from autonomy import simulation_training

    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    start = datetime(2025, 1, 1, tzinfo=timezone.utc)
    try:
        for index in range(80):
            result = index % 3 != 0
            ticker = f"SIM-{index:04d}"
            created = start + timedelta(days=index)
            forecast = Forecast(
                market_ticker=ticker, probability_yes=0.75 if result else 0.25,
                uncertainty=0.1, sources_used={"fixture": 1.0},
                market_implied_yes=0.5,
                edge_yes=(0.25 if result else -0.25), rationale="fixture",
            )
            ledger.record_decision(Decision(
                decision_id=f"d-{index}", market_ticker=ticker,
                action=DecisionAction.BUY_YES if result else DecisionAction.BUY_NO,
                side="yes" if result else "no", price_cents=50, count=1,
                ev_cents_per_contract=10.0, kelly_fraction=0.1,
                notional_cents=50, forecast=forecast, risk_snapshot={},
                created_at=created.isoformat(),
            ))
            ledger.record_settlement(ticker, result)
            ledger._conn.execute(  # noqa: SLF001 - point-in-time fixture
                "UPDATE settlements SET settled_at=? WHERE market_ticker=?",
                ((created + timedelta(hours=1)).isoformat(), ticker),
            )
        ledger._conn.commit()  # noqa: SLF001 - fixture setup
    finally:
        ledger.close()
    before = hashlib.sha256(db.read_bytes()).hexdigest()
    traced_statements: list[str] = []

    def _traced_readonly(path):
        connection = connect_readonly(path)
        connection.set_trace_callback(traced_statements.append)
        return connection

    monkeypatch.setattr(simulation_training, "connect_readonly", _traced_readonly)
    report = run_simulation_training(db, simulations=100)
    after = hashlib.sha256(db.read_bytes()).hexdigest()
    assert before == after
    assert report["sqlite_access"] == "mode=ro; PRAGMA query_only=ON"
    assert report["database_liveness"]["status"] == "PASS"
    assert report["database_liveness"]["global_integrity_scan_performed"] is False
    assert report["database_liveness"]["structural_integrity_verified"] is False
    assert report["integrity_check"] == "NOT_RUN"
    assert report["integrity_check_method"] == "offline_maintenance_only"
    assert (
        report["offline_integrity_attestation"]["status"]
        == "NOT_VERIFIED_BY_HOURLY_TRAINER"
    )
    assert report["offline_integrity_attestation"]["full_scan_performed"] is False
    assert report["offline_integrity_attestation"]["counts_toward_readiness"] is False
    traced = "\n".join(traced_statements).casefold()
    assert "quick_check" not in traced
    assert "integrity_check" not in traced
    assert report["execution_authority"] is False
    assert report["weights_written"] is False
    assert report["readiness_evidence_written"] is False
    assert report["evidence_quarantine"]["counts_toward_canary"] is False
    assert "crypto_execution_truth" in report
    assert report["evolution_lab"]["authority"]["execution_authority"] is False
    assert report["evolution_lab"]["evidence_quarantine"]["counts_toward_scale"] is False
    assert report["execution_trace_replay"]["execution_authority"] is False
    assert report["improvement_queue"]["status"] == "ATTACKING_WEAKNESSES"
    assert report["improvement_queue"]["execution_authority"] is False
    assert "order_submission" in report["improvement_queue"]["automatic_actions_forbidden"]


def test_hourly_liveness_probe_is_bounded_and_never_runs_global_integrity(tmp_path):
    db = tmp_path / "ledger.db"
    ledger = AutonomyLedger(db)
    ledger.close()
    connection = connect_readonly(db)
    statements: list[str] = []
    connection.set_trace_callback(statements.append)
    try:
        result = bounded_database_liveness(connection)
    finally:
        connection.close()

    assert result["status"] == "PASS"
    assert result["global_integrity_scan_performed"] is False
    assert result["structural_integrity_verified"] is False
    traced = "\n".join(statements).casefold()
    assert "quick_check" not in traced
    assert "integrity_check" not in traced


def test_hourly_liveness_probe_fails_closed_when_required_schema_is_missing():
    import sqlite3

    connection = sqlite3.connect(":memory:")
    try:
        with pytest.raises(RuntimeError, match="missing tables"):
            bounded_database_liveness(connection)
    finally:
        connection.close()


def test_training_report_writes_atomic_latest_pointer(tmp_path):
    report = {"report_name": "DUMMY_SIMULATION_TRAINING", "execution_authority": False}
    path = write_simulation_training_report(report, tmp_path)
    assert path.exists()
    assert not path.with_suffix(".tmp").exists()
    latest = json.loads((tmp_path / "LATEST.json").read_text(encoding="utf-8"))
    assert latest["execution_authority"] is False
