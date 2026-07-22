from __future__ import annotations

import json
import sqlite3

from autonomy.exit_policy_evaluator import (
    ExitEvidenceSnapshot,
    evaluate_exit_policies,
    load_exit_evidence,
)


def _snapshot(
    decision_id: str,
    *,
    at: str,
    bid: int = 60,
    hold_pnl: int = -41,
    mark: int = -5,
    action: str = "EXIT",
    group: str | None = None,
) -> ExitEvidenceSnapshot:
    return ExitEvidenceSnapshot(
        decision_id=decision_id,
        market_ticker=f"KXTEST-{decision_id}",
        event_group=group or f"event-{decision_id}",
        snapshot_at=at,
        side="yes",
        filled_count=1,
        quoted_exit_bid_cents=bid,
        entry_cost_cents=41,
        entry_cost_source="witnessed_fill_cost",
        hold_pnl_cents=hold_pnl,
        action=action,
        mark_change_cents=mark,
        time_to_close_hours=4.0,
        exit_advantage_cents=8.0,
        exit_depth_verified=True,
    )


def test_evaluator_uses_first_trigger_and_stresses_fee_and_slippage():
    rows = [
        _snapshot("d1", at="2026-07-20T01:00:00+00:00", bid=60),
        _snapshot("d1", at="2026-07-20T02:00:00+00:00", bid=90),
        _snapshot("d2", at="2026-07-20T01:00:00+00:00", bid=55),
    ]
    report = evaluate_exit_policies(rows)
    model = report["policies"]["model_value_v1"]
    assert model["triggered_decisions"] == 2
    base = model["scenarios"]["0"]
    stressed = model["scenarios"]["5"]
    # First d1 trigger is the 60c quote; the later 90c mark is not cherry-picked.
    assert base["early_exit_pnl_cents"] < 100
    assert stressed["incremental_pnl_cents"] < base["incremental_pnl_cents"]
    assert base["quoted_bid_is_fill"] is False
    assert model["passes_forward_research_gate"] is False
    assert report["live_sell_authorized"] is False


def _features(decision_id: str) -> dict:
    return {
        "evidence_version": "exit_advisor_v2",
        "observational_only": True,
        "policy_evidence_only": True,
        "probability_authority": False,
        "decision_id": decision_id,
        "position_side": "yes",
        "action": "EXIT",
        "filled_count": 2,
        "quoted_exit_bid_cents": 60,
        "exit_quote_observed_at": "2026-07-20T01:59:00+00:00",
        "exit_quote_age_seconds": 60.0,
        "exit_quote_fresh": True,
        "exit_depth_verified": True,
        "entry_order_active": False,
        "entry_cost_cents": 82,
        "entry_cost_source": "witnessed_fill_cost",
        "mark_change_cents": 20,
        "time_to_close_hours": 4.0,
        "exit_advantage_cents": 5.0,
    }


def _connection() -> sqlite3.Connection:
    connection = sqlite3.connect(":memory:")
    connection.executescript(
        """
        CREATE TABLE decisions(
            decision_id TEXT, market_ticker TEXT, side TEXT, created_at TEXT
        );
        CREATE TABLE outcomes(
            id INTEGER PRIMARY KEY, decision_id TEXT, kind TEXT, fill_count INTEGER,
            fill_price_cents INTEGER, pnl_cents INTEGER, detail TEXT, created_at TEXT
        );
        CREATE TABLE settlements(
            market_ticker TEXT, result_yes INTEGER, settled_at TEXT
        );
        CREATE TABLE signals(
            id INTEGER PRIMARY KEY, source TEXT, market_ticker TEXT,
            features TEXT, created_at TEXT, ingested_at TEXT, mode TEXT
        );
        CREATE TEMP VIEW signal_history AS SELECT * FROM signals;
        """
    )
    return connection


def _seed_lifecycle(connection: sqlite3.Connection, decision_id: str, receipt: str) -> None:
    ticker = f"KXTEST-{decision_id}"
    connection.execute(
        "INSERT INTO decisions VALUES (?,?,?,?)",
        (decision_id, ticker, "yes", "2026-07-20T00:00:00+00:00"),
    )
    connection.execute(
        "INSERT INTO outcomes VALUES (?,?,?,?,?,?,?,?)",
        (
            None, decision_id, "FILLED", 2, 40, None,
            json.dumps({"fill_cost_cents": 82}),
            "2026-07-20T01:00:00+00:00",
        ),
    )
    connection.execute(
        "INSERT INTO settlements VALUES (?,?,?)",
        (ticker, 1, "2026-07-20T03:00:00+00:00"),
    )
    connection.execute(
        "INSERT INTO outcomes VALUES (?,?,?,?,?,?,?,?)",
        (
            None, decision_id, "SETTLED_WIN", 2, 40, 118,
            json.dumps({"fill_cost_cents": 82}),
            "2026-07-20T03:01:00+00:00",
        ),
    )
    connection.execute(
        "INSERT INTO signals VALUES (?,?,?,?,?,?,?)",
        (
            None, "exit_advisor_shadow", ticker,
            json.dumps(_features(decision_id)),
            "2026-07-20T02:00:00+00:00", receipt, "live",
        ),
    )


def test_loader_is_receipt_bounded_and_does_not_use_settlement_as_fill_time():
    connection = _connection()
    _seed_lifecycle(connection, "valid", "2026-07-20T02:01:00+00:00")
    _seed_lifecycle(connection, "late", "2026-07-20T03:01:00+00:00")
    rows, exclusions = load_exit_evidence(connection)
    assert [row.decision_id for row in rows] == ["valid"]
    assert exclusions["point_in_time_ordering_violation"] == 1


def test_loader_rejects_active_entry_and_unwitnessed_entry_cost():
    connection = _connection()
    _seed_lifecycle(connection, "active", "2026-07-20T02:01:00+00:00")
    _seed_lifecycle(connection, "estimated", "2026-07-20T02:01:00+00:00")
    active = _features("active")
    active["entry_order_active"] = True
    estimated = _features("estimated")
    estimated["entry_cost_source"] = "unverified"
    connection.execute(
        "UPDATE signals SET features=? WHERE market_ticker='KXTEST-active'",
        (json.dumps(active),),
    )
    connection.execute(
        "UPDATE signals SET features=? WHERE market_ticker='KXTEST-estimated'",
        (json.dumps(estimated),),
    )
    rows, exclusions = load_exit_evidence(connection)
    assert rows == []
    assert exclusions["entry_order_active_or_unknown"] == 1
    assert exclusions["entry_cost_not_witnessed"] == 1


def test_loader_rejects_timezone_naive_evidence_timestamps():
    connection = _connection()
    _seed_lifecycle(connection, "naive", "2026-07-20T02:01:00+00:00")
    connection.execute(
        "UPDATE signals SET created_at=? WHERE market_ticker='KXTEST-naive'",
        ("2026-07-20T02:00:00",),
    )
    rows, exclusions = load_exit_evidence(connection)
    assert rows == []
    assert exclusions["invalid_timestamp"] == 1
