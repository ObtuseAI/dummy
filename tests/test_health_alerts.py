"""Alert surfaces for ledger health and backtest evidence staleness."""
from __future__ import annotations

import json

import autonomy.alerts as alerts


def _wire_alert_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(alerts, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(alerts, "ALERTS_LOG", tmp_path / "alerts.jsonl")
    monkeypatch.setattr(alerts, "ALERTS_LATEST", tmp_path / "alerts_latest.json")
    monkeypatch.setattr(alerts, "ALERT_STATE", tmp_path / "alert_state.json")


def test_ledger_health_alert_fires_once_per_episode(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    sick = {"bloat_warn": True, "size_gib": 9.25, "probe_error": None}
    a = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                               now_iso="t1", ledger_health=sick)
    b = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                               now_iso="t2", ledger_health=sick)
    assert len(a) == 1 and a[0]["kind"] == "LEDGER_HEALTH"
    assert "9.25" in a[0]["message"]
    assert b == []  # de-duplicated while the condition persists


def test_ledger_health_alert_rearms_after_recovery(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    sick = {"bloat_warn": True, "size_gib": 9.0, "probe_error": None}
    healthy = {"bloat_warn": False, "size_gib": 0.5, "probe_error": None}
    alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                           now_iso="t1", ledger_health=sick)
    alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                           now_iso="t2", ledger_health=healthy)
    again = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                                   now_iso="t3", ledger_health=sick)
    assert len(again) == 1 and again[0]["kind"] == "LEDGER_HEALTH"


def test_probe_error_also_alerts(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    sick = {"bloat_warn": False, "size_gib": 1.0,
            "probe_error": "DatabaseError:file is not a database"}
    fired = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                                   now_iso="t1", ledger_health=sick)
    assert len(fired) == 1 and fired[0]["kind"] == "LEDGER_HEALTH"


def test_healthy_ledger_never_alerts(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    healthy = {"bloat_warn": False, "size_gib": 0.5, "probe_error": None}
    fired = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                                   now_iso="t1", ledger_health=healthy)
    assert fired == []


def test_backtest_stale_alert_fires_on_rising_edge(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    stale = {"is_stale": True, "age_hours": 144.0, "reason": "stale"}
    a = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                               now_iso="t1", backtest_freshness=stale)
    b = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                               now_iso="t2", backtest_freshness=stale)
    assert len(a) == 1 and a[0]["kind"] == "BACKTEST_STALE"
    assert "144.0" in a[0]["message"]
    assert b == []  # standing staleness does not spam


def test_backtest_stale_rearms_after_refresh(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    stale = {"is_stale": True, "age_hours": 30.0, "reason": "stale"}
    fresh = {"is_stale": False, "age_hours": 1.0, "reason": None}
    alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                           now_iso="t1", backtest_freshness=stale)
    alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                           now_iso="t2", backtest_freshness=fresh)
    again = alerts.evaluate_alerts({"status": "CYCLE_OK"}, None, gate_ready=False,
                                   now_iso="t3", backtest_freshness=stale)
    assert len(again) == 1 and again[0]["kind"] == "BACKTEST_STALE"


def test_new_alert_kinds_have_severities(monkeypatch, tmp_path):
    _wire_alert_paths(monkeypatch, tmp_path)
    assert alerts.SEVERITY["RECAL_REJECTED"] == "critical"
    assert alerts.SEVERITY["BACKTEST_STALE"] == "warning"
    assert alerts.SEVERITY["LEDGER_HEALTH"] == "warning"
    record = alerts.emit_alert("RECAL_REJECTED", "test", {})
    assert record["severity"] == "critical"
    logged = (tmp_path / "alerts.jsonl").read_text(encoding="utf-8").strip()
    assert json.loads(logged)["kind"] == "RECAL_REJECTED"
