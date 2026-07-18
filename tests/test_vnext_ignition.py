"""Wave-26: the vNext shadow runtime ignition -- board-driven episodes, real
settlement completion, real held-out cases. Wave-27: ledger-contention
resilience -- a busy single-writer ledger defers, never fails the pass."""
from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timedelta, timezone

import autonomy.vnext_runtime as runtime
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def _board_row(ticker="KXBTC15M-26JUL18173000-15", league="btc",
               close_minutes=10, yes_ask=52, no_bid=48):
    close = datetime.now(timezone.utc) + timedelta(minutes=close_minutes)
    return {
        "ticker": ticker, "league": league, "bet_type": "market",
        "probability": 0.61, "market_probability": 0.50, "edge": 0.11,
        "uncertainty": 0.18,
        "yes_bid": 48, "yes_ask": yes_ask, "no_bid": no_bid, "no_ask": 52,
        "liquidity": 120, "close_time": close.isoformat(),
    }


def _board(*rows):
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "groups": {"btc": {"market": list(rows)}},
    }


def _seed_fused_history(ledger, n=6):
    for i in range(n):
        ticker = f"KXBTC15M-26JUL18{i:02d}0000-15"
        ledger.record_signal(Signal(
            source="fused_forecast", market_ticker=ticker,
            probability_yes=0.6, uncertainty=0.1, rationale="r",
            features={"challenger_only": False, "market_implied_yes": 0.5}))
        ledger.record_settlement(ticker, i % 2 == 0)


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(runtime, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(runtime, "PENDING_PATH", tmp_path / "vnext_pending.jsonl")
    monkeypatch.setattr(runtime, "EPISODES_PATH", tmp_path / "vnext_episodes.jsonl")
    monkeypatch.setattr(runtime, "STATUS_PATH", tmp_path / "vnext_status.json")


def test_eligible_rows_demand_a_coherent_open_book():
    good = _board_row()
    incoherent = _board_row(ticker="KXBTC15M-26JUL18174500-15", yes_ask=55, no_bid=48)
    missing = dict(_board_row(ticker="KXBTC15M-26JUL18180000-15"))
    missing["yes_ask"] = None
    closed = _board_row(ticker="KXBTC15M-26JUL18160000-15", close_minutes=-5)
    rows = runtime.eligible_rows(_board(good, incoherent, missing, closed), set())
    assert [r["ticker"] for r in rows] == [good["ticker"]]


def test_full_ignition_issue_then_complete_on_settlement(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    _seed_fused_history(ledger)

    row = _board_row()
    first = runtime.run_shadow_pass(
        board=_board(row), db_path=str(tmp_path / "ledger.db"))
    assert first["issued"] == 1 and first["pending"] == 1
    assert first["errors"] == []
    pending = runtime.load_pending()
    assert pending[0]["market_id"] == row["ticker"]
    issued_payload = pending[0]["issued"]
    assert issued_payload["status"] == "ISSUED"

    # The market settles YES in the autonomy ledger; the next pass completes
    # the episode against verified truth with REAL held-out cases.
    ledger.record_settlement(row["ticker"], True)
    second = runtime.run_shadow_pass(
        board=_board(), db_path=str(tmp_path / "ledger.db"))
    assert second["completed"] == 1 and second["pending"] == 0
    assert second["episodes_on_ledger"] == 1
    completed = json.loads(
        (tmp_path / "vnext_episodes.jsonl").read_text().strip())
    assert completed["status"] == "DISSOLVED"
    assert completed["settlement"]["result_yes"] is True
    status = json.loads((tmp_path / "vnext_status.json").read_text())
    assert status["completed"] == 1


def test_pending_expires_after_the_window(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    _seed_fused_history(ledger)
    row = _board_row()
    runtime.run_shadow_pass(board=_board(row), db_path=str(tmp_path / "ledger.db"))
    pending = runtime.load_pending()
    stale = (datetime.now(timezone.utc) - timedelta(hours=49)).isoformat()
    pending[0]["issued_at"] = stale
    runtime.save_pending(pending)
    result = runtime.run_shadow_pass(
        board=_board(), db_path=str(tmp_path / "ledger.db"))
    assert result["expired"] == 1 and result["pending"] == 0


def test_held_out_cases_come_from_real_settlements(tmp_path):
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    _seed_fused_history(ledger, n=8)
    cases = runtime.held_out_cases_from_ledger(ledger._conn)
    assert 1 <= len(cases) <= runtime.HELD_OUT_COUNT
    assert all(c.settlement_verified for c in cases)
    assert len({c.event_cluster_id for c in cases}) == len(cases)


def test_pass_survives_missing_board_and_ledger(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    summary = runtime.run_shadow_pass(
        board={}, db_path=str(tmp_path / "absent.db"))
    assert summary["issued"] == 0 and summary["completed"] == 0
    assert (tmp_path / "vnext_status.json").exists()


def test_locked_ledger_reads_as_busy(monkeypatch, tmp_path):
    # A concurrent EXCLUSIVE writer makes the read-only settlement read raise
    # OperationalError("database is locked"); the helper classifies it "busy".
    monkeypatch.setattr(runtime, "_LEDGER_BUSY_TIMEOUT_MS", 150)
    db = tmp_path / "ledger.db"
    AutonomyLedger(db)  # create the schema
    holder = sqlite3.connect(db)
    holder.execute("BEGIN EXCLUSIVE")
    holder.execute(
        "CREATE TABLE IF NOT EXISTS _lock_probe (x INTEGER)")
    try:
        settled, held, note = runtime._read_ledger_state(str(db), ["KXBTC15M-x-15"])
    finally:
        holder.rollback()
        holder.close()
    assert note == "busy" and settled == {} and held == ()


def test_busy_ledger_defers_completion_but_still_issues(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    ledger = AutonomyLedger(tmp_path / "ledger.db")
    _seed_fused_history(ledger)
    # Simulate a busy ledger: the read soft-fails, so completion is deferred,
    # but issuing (board-only) still runs and no hard error is recorded.
    monkeypatch.setattr(
        runtime, "_read_ledger_state", lambda *a, **k: ({}, (), "busy"))
    summary = runtime.run_shadow_pass(
        board=_board(_board_row()), db_path=str(tmp_path / "ledger.db"))
    assert summary["ledger_busy"] is True
    assert summary["errors"] == []
    assert summary["issued"] == 1 and summary["pending"] == 1
    assert summary["completed"] == 0
