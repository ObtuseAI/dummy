"""Wave-42: the dashboard reads a persisted snapshot, not the live ledger.

The web dashboard used to open the ledger and run a full backtest on every
poll -- a minutes-long SHARED-lock hold that blocked the shadow brain's commit
("database is locked"). These tests pin the decoupling: the brain builds the
snapshot while it already holds the ledger, and the dashboard assembles its
ledger-derived panels from that artifact without touching the ledger at all.
"""
from __future__ import annotations

import json

from autonomy.dashboard import assemble_dashboard_state
from autonomy.dashboard_snapshot import (
    build_dashboard_snapshot,
    read_dashboard_snapshot,
    write_dashboard_snapshot,
)
from autonomy.ledger import AutonomyLedger
from autonomy.ontology import Signal


def _signal(source, ticker, p):
    return Signal(source=source, market_ticker=ticker, probability_yes=p, uncertainty=0.1, rationale="")


def _seed(ledger):
    for ticker, result in [("A", True), ("B", True), ("C", False)]:
        ledger.record_signal(_signal("market_prior", ticker, 0.5))
        ledger.record_signal(_signal("sharp", ticker, 0.9 if result else 0.1))
        ledger.record_settlement(ticker, result)


def test_build_snapshot_carries_all_dashboard_panels(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed(ledger)
        snap = build_dashboard_snapshot(ledger)
    finally:
        ledger.close()
    assert snap["backtest"]["settled_markets"] == 3
    assert "sharp" in snap["backtest"]["sources"]
    assert "ready" in snap["canary"]
    assert isinstance(snap["ledger_summary"], dict)
    assert isinstance(snap["statistics_intake"], dict)


def test_snapshot_write_read_roundtrip(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed(ledger)
        snap = build_dashboard_snapshot(ledger)
    finally:
        ledger.close()
    path = write_dashboard_snapshot(snap, path=tmp_path / "snap.json")
    assert path.exists()
    assert read_dashboard_snapshot(tmp_path / "snap.json") == snap


def test_light_refresh_reuses_prior_backtest(tmp_path):
    ledger = AutonomyLedger(db_path=tmp_path / "l.db")
    try:
        _seed(ledger)
        full = build_dashboard_snapshot(ledger)
        # Light refresh must NOT recompute the heavy backtest: it carries the
        # prior report + canary verbatim and only refreshes the cheap summaries.
        light = build_dashboard_snapshot(ledger, prior=full, refresh_backtest=False)
    finally:
        ledger.close()
    assert light["backtest"] == full["backtest"]
    assert light["canary"] == full["canary"]
    assert light["backtest_generated_at"] == full["backtest_generated_at"]


def test_read_missing_snapshot_is_none(tmp_path):
    assert read_dashboard_snapshot(tmp_path / "nope.json") is None


def test_dashboard_reads_snapshot_without_touching_ledger(monkeypatch, tmp_path):
    monkeypatch.delenv("DUMMY_DASHBOARD_LIVE_LEDGER", raising=False)
    # Snapshot present, but NO ledger.db on disk: if the dashboard tried to open
    # the ledger it would produce an error/empty canary. It must read the file.
    (tmp_path / "latest_dashboard_snapshot.json").write_text(json.dumps({
        "ledger_summary": {"settled": 7},
        "statistics_intake": {"observed": 4},
        "backtest": {"settled_markets": 7, "sources": {
            "sharp": {"beat_market_rate": 1.0, "n": 7, "mean_brier": 0.02},
        }, "derived_weights": {"sharp": 1.3}},
        "canary": {"ready": False, "blockers": ["insufficient settlements"]},
    }), encoding="utf-8")

    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["ledger"] == {"settled": 7}
    assert state["settled_markets"] == 7
    assert state["canary"]["ready"] is False
    assert [row["source"] for row in state["scoreboard"]] == ["sharp"]
    assert not (tmp_path / "ledger.db").exists()  # never created -> never opened


def test_dashboard_live_ledger_opt_in_uses_ledger(monkeypatch, tmp_path):
    monkeypatch.setenv("DUMMY_DASHBOARD_LIVE_LEDGER", "1")
    ledger = AutonomyLedger(db_path=tmp_path / "ledger.db")
    try:
        _seed(ledger)
    finally:
        ledger.close()
    # No snapshot artifact -> only the live path can populate settled_markets.
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["settled_markets"] == 3
    assert "ready" in state["canary"]
