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


def test_gate_regression_fires_on_falling_edge(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=True, now_iso="t1")
    fired = alerts.evaluate_alerts(
        {"status": "CYCLE_OK"}, None, gate_ready=False, now_iso="t2",
    )
    assert [item["kind"] for item in fired] == ["GATE_REGRESSION"]
    assert fired[0]["severity"] == "warning"


def test_drawdown_ladder_deepening(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    def rs(dd):
        return {"equity_peak_cents": 100000,
                "bankroll_cents": int(100000 * (1 - dd))}

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


def test_signal_quality_rejection_alert_is_episode_deduplicated(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    first = alerts.evaluate_alerts(
        {"status": "CYCLE_OK", "signals_rejected": 2}, None, False, now_iso="t1",
    )
    repeated = alerts.evaluate_alerts(
        {"status": "CYCLE_OK", "signals_rejected": 1}, None, False, now_iso="t2",
    )
    alerts.evaluate_alerts(
        {"status": "CYCLE_OK", "signals_rejected": 0}, None, False, now_iso="t3",
    )
    next_episode = alerts.evaluate_alerts(
        {"status": "CYCLE_OK", "signals_rejected": 1}, None, False, now_iso="t4",
    )
    assert [item["kind"] for item in first] == ["SIGNAL_QUALITY_REJECTION"]
    assert repeated == []
    assert [item["kind"] for item in next_episode] == ["SIGNAL_QUALITY_REJECTION"]


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
    (tmp_path / "simulation_training_latest.json").write_text(
        json.dumps({"forecast_status": "HOLD", "execution_authority": False}),
        encoding="utf-8",
    )
    # The dashboard snapshot artifact supplies the ledger-derived panels now:
    # the dashboard no longer opens the ledger by default (Wave-42).
    (tmp_path / "latest_dashboard_snapshot.json").write_text(json.dumps({
        "ledger_summary": {"settled": 3},
        "statistics_intake": {},
        "backtest": {"settled_markets": 3, "sources": {}},
        "canary": {"ready": False, "blockers": ["insufficient settlements"]},
    }), encoding="utf-8")

    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["heartbeat"]["alive"] is True
    assert len(state["bankroll_curve"]) == 1
    assert "ready" in state["canary"]
    assert state["settled_markets"] == 3
    assert state["simulation_training"]["forecast_status"] == "HOLD"


def test_dashboard_app_serves(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient

    monkeypatch.setattr("autonomy.dashboard.RUNTIME_DIR", tmp_path)
    from autonomy.dashboard import build_app

    client = TestClient(build_app())
    assert client.get("/").status_code == 200
    r = client.get("/api/autonomy")
    assert r.status_code == 200
    assert "heartbeat" in r.json()


def test_session_authorization_absent(tmp_path):
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["session"]["present"] is False
    assert state["session"]["status"] == "NO_SESSION_FILE"
    fleet = state["scheduler_fleet"]
    assert len(fleet) == 8
    assert {t["role"] for t in fleet} == {
        "retired shadow research (non-authoritative)",
        "retired crypto paper research (non-authoritative)",
        "sports research simulation (non-authoritative)",
        "authoritative sports model seed", "authoritative sports quote board",
        "simulation trainer", "legacy mispricing research (non-authoritative)",
        "dashboard",
    }
    # Alternate runtimes never touch the Windows scheduler.
    assert all(t["state"] == "ALTERNATE_RUNTIME" for t in fleet)


def test_session_authorization_expired_is_loud(tmp_path):
    (tmp_path / "session.json").write_text(
        json.dumps({
            "mode": "LIVE",
            "operator": "chris",
            "started_at": "2026-07-09T08:49:31+00:00",
            "expires_at": "2026-07-10T08:49:31+00:00",
            "limit_orders_only": True,
        }),
        encoding="utf-8",
    )
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    session = state["session"]
    assert session["status"] == "LIVE_AUTHORIZATION_EXPIRED"
    assert session["expired"] is True
    assert session["seconds_remaining"] < 0
    assert session["limit_orders_only"] is True


def test_session_authorization_active_live(tmp_path):
    from datetime import datetime, timedelta, timezone

    expires = (datetime.now(timezone.utc) + timedelta(hours=6)).isoformat()
    (tmp_path / "session.json").write_text(
        json.dumps({"mode": "LIVE", "operator": "chris", "expires_at": expires}),
        encoding="utf-8",
    )
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    session = state["session"]
    assert session["status"] == "LIVE_AUTHORIZED"
    assert session["expired"] is False
    assert session["seconds_remaining"] > 0


def test_session_shadow_mode_is_not_live(tmp_path):
    (tmp_path / "session.json").write_text(
        json.dumps({"mode": "SHADOW", "operator": "chris"}), encoding="utf-8",
    )
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["session"]["status"] == "SHADOW"
    assert state["session"]["mode"] == "SHADOW"


# ---------------------------------------------------------------- council (WS-13)


def test_council_panel_absent_snapshot_is_empty_and_does_not_raise(tmp_path):
    """Fail-closed: no council_snapshot.json -> empty panel, never a crash."""
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["council"] == []


def test_council_panel_assembles_from_snapshot_and_season_state(tmp_path):
    (tmp_path / "council_snapshot.json").write_text(json.dumps({
        "generated_at": "2026-07-13T00:00:00Z",
        "specialists": [
            {"name": "mlb", "status": "ok", "details": {"games_seen": 900},
             "open_opportunities": 3},
            {"name": "nba", "status": "dormant",
             "details": {"in_season": False, "score_games_seen": 0},
             "open_opportunities": 0},
            {"name": "crypto", "status": "ok", "details": {"has_champion": True},
             "open_opportunities": 1},
        ],
    }), encoding="utf-8")
    # mlb's health() doesn't stamp in_season (autonomy/specialists/mlb.py);
    # the dashboard falls back to the persisted season_state.json, the same
    # file SeasonMonitor.snapshot() would return.
    (tmp_path / "season_state.json").write_text(json.dumps({
        "mlb": {"active": True, "checked_at": "2026-07-13T00:00:00+00:00"},
    }), encoding="utf-8")

    from autonomy.ledger import AutonomyLedger

    led = AutonomyLedger(db_path=tmp_path / "ledger.db")
    led.close()

    state = assemble_dashboard_state(runtime_dir=tmp_path)
    rows = {row["name"]: row for row in state["council"]}
    assert set(rows) == {"mlb", "nba", "crypto"}
    assert rows["mlb"]["status"] == "ok"
    assert rows["mlb"]["in_season"] is True  # filled from season_state.json
    assert rows["mlb"]["games_seen"] == 900
    assert rows["mlb"]["open_opportunities"] == 3
    assert rows["nba"]["in_season"] is False  # stamped directly in details
    assert rows["nba"]["games_seen"] == 0
    assert rows["crypto"]["open_opportunities"] == 1
    # No settlements in this ledger -> no contested-Brier or CLV evidence yet,
    # never a fabricated value.
    assert rows["mlb"]["contested_brier"] is None
    assert rows["mlb"]["clv_bps"] is None


def test_council_panel_never_raises_on_malformed_snapshot(tmp_path):
    (tmp_path / "council_snapshot.json").write_text("not valid json", encoding="utf-8")
    state = assemble_dashboard_state(runtime_dir=tmp_path)
    assert state["council"] == []
