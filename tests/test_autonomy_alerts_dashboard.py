"""Tests for operator alerts + dashboard state assembler."""

from __future__ import annotations

import json

import autonomy.alerts as alerts
from autonomy.dashboard import assemble_dashboard_state


def _wire_alert_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(alerts, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(alerts, "ALERTS_LOG", tmp_path / "alerts.jsonl")
    monkeypatch.setattr(alerts, "ALERTS_LATEST", tmp_path / "alerts_latest.json")
    monkeypatch.setattr(alerts, "ALERT_STATE", tmp_path / "alert_state.json")


def test_self_stop_alert_fires_once(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    rec = {"status": "HALTED_SELF_STOP: drawdown 31% breached"}
    fired1 = alerts.evaluate_alerts(rec, None, gate_ready=False, now_iso="t1")
    fired2 = alerts.evaluate_alerts(rec, None, gate_ready=False, now_iso="t2")
    assert len(fired1) == 1 and fired1[0]["kind"] == "SELF_STOP"
    assert fired1[0]["severity"] == "critical"
    assert fired2 == []  # de-duplicated while still stopped


def test_gate_green_rising_edge(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    a = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False, now_iso="t1")
    b = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=True, now_iso="t2")
    c = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=True, now_iso="t3")
    assert a == []
    assert len(b) == 1 and b[0]["kind"] == "GATE_GREEN"
    assert c == []  # only on the rising edge


def test_drawdown_ladder_deepening(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    rs = lambda dd: {"equity_peak_cents": 100000, "bankroll_cents": int(100000 * (1 - dd))}
    a = alerts.evaluate_alerts({"status": "CYCLE_OK"}, rs(0.05), False, now_iso="t1")
    b = alerts.evaluate_alerts({"status": "CYCLE_OK"}, rs(0.12), False, now_iso="t2")
    c = alerts.evaluate_alerts({"status": "CYCLE_OK"}, rs(0.12), False, now_iso="t3")
    d = alerts.evaluate_alerts({"status": "CYCLE_OK"}, rs(0.22), False, now_iso="t4")
    assert a == []
    assert len(b) == 1 and b[0]["kind"] == "DRAWDOWN_LADDER"
    assert c == []  # same rung, no repeat
    assert len(d) == 1  # deeper rung fires again


def test_error_streak_alert(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    for i in range(2):
        assert alerts.evaluate_alerts({"status": "CYCLE_ERROR:X"}, None, False, now_iso=f"t{i}") == []
    fired = alerts.evaluate_alerts({"status": "CYCLE_ERROR:X"}, None, False, now_iso="t3")
    assert len(fired) == 1 and fired[0]["kind"] == "CYCLE_ERROR_STREAK"
    # A good cycle resets the streak.
    alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, False, now_iso="t4")
    state = json.loads((tmp_path / "alert_state.json").read_text())
    assert state["error_streak"] == 0


def test_recent_alerts_reads_log(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    alerts.emit_alert("GATE_GREEN", "ready", now_iso="t1")
    alerts.emit_alert("SELF_STOP", "stopped", now_iso="t2")
    recent = alerts.recent_alerts(limit=5)
    assert [r["kind"] for r in recent] == ["GATE_GREEN", "SELF_STOP"]


# ---------------------------------------------------------------- dashboard


def test_dashboard_state_empty_runtime(tmp_path):
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["heartbeat"] == {"alive": False}
    assert state["settled_markets"] == 0
    assert state["scoreboard"] == []


def test_dashboard_state_assembles_from_artifacts(tmp_path):
    (tmp_path / "heartbeat.json").write_text(json.dumps({"alive": True, "last_status": "CYCLE_OK"}), encoding="utf-8")
    (tmp_path / "cycles.jsonl").write_text(
        json.dumps({"at": "2026-07-09T01:00:00Z", "status": "CYCLE_OK", "bankroll_cents": 10000, "stage": 1}) + "\n",
        encoding="utf-8",
    )
    # A real ledger so the backtest/canary branch runs.
    from autonomy.ledger import AutonomyLedger

    led = AutonomyLedger(db_path=tmp_path / "ledger.db")
    led.close()

    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["heartbeat"]["alive"] is True
    assert len(state["bankroll_curve"]) == 1
    assert "ready" in state["canary"]


def test_dashboard_app_serves(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr("autonomy.dashboard.RUNTIME_DIR", tmp_path)
    from autonomy.dashboard import build_app

    client = TestClient(build_app())
    assert client.get("/").status_code == 200
    r = client.get("/api/autonomy")
    assert r.status_code == 200
    assert "heartbeat" in r.json()
