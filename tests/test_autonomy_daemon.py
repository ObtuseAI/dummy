"""Tests for the resilient shadow daemon cycle wrapper."""

from __future__ import annotations

import json

import autonomy.daemon as daemon
from autonomy.ontology import SessionMode


def test_cycle_error_never_raises(monkeypatch, tmp_path):
    monkeypatch.setattr(daemon, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(daemon, "HEARTBEAT_PATH", tmp_path / "hb.json")
    monkeypatch.setattr(daemon, "CYCLE_LOG_PATH", tmp_path / "c.jsonl")
    monkeypatch.setattr(daemon, "kill_switch_active", lambda: False)

    def boom(mode):
        raise RuntimeError("scan exploded")

    monkeypatch.setattr("autonomy.session.build_brain", boom)
    record = daemon.run_one_cycle("2026-07-09T00:00:00+00:00", SessionMode.SHADOW)
    assert record["status"].startswith("CYCLE_ERROR")
    assert (tmp_path / "hb.json").exists()
    # Error was logged, not raised.
    lines = (tmp_path / "c.jsonl").read_text(encoding="utf-8").strip().splitlines()
    assert json.loads(lines[-1])["status"].startswith("CYCLE_ERROR")


def test_kill_switch_short_circuits(monkeypatch, tmp_path):
    monkeypatch.setattr(daemon, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(daemon, "HEARTBEAT_PATH", tmp_path / "hb.json")
    monkeypatch.setattr(daemon, "kill_switch_active", lambda: True)
    called = []
    monkeypatch.setattr("autonomy.session.build_brain", lambda m: called.append(1))
    record = daemon.run_one_cycle("2026-07-09T00:00:00+00:00")
    assert record["status"] == "HALTED_KILL_SWITCH"
    assert called == []  # never built a brain


def test_heartbeat_and_log_written_on_success(monkeypatch, tmp_path):
    monkeypatch.setattr(daemon, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(daemon, "HEARTBEAT_PATH", tmp_path / "hb.json")
    monkeypatch.setattr(daemon, "CYCLE_LOG_PATH", tmp_path / "c.jsonl")
    monkeypatch.setattr(daemon, "kill_switch_active", lambda: False)
    monkeypatch.setattr(
        daemon,
        "_utc_now_iso",
        lambda: "2026-07-09T00:08:00+00:00",
    )

    class FakeReport:
        def to_dict(self):
            return {"status": "CYCLE_OK", "orders_placed": 2, "signals_generated": 100, "settlements": 1}

    class FakeBrain:
        class _L:
            def close(self):
                pass

        ledger = _L()

        async def run_cycle(self):
            return FakeReport()

    monkeypatch.setattr("autonomy.session.build_brain", lambda m: FakeBrain())
    record = daemon.run_one_cycle("2026-07-09T00:00:00+00:00")
    assert record["status"] == "CYCLE_OK"
    hb = json.loads((tmp_path / "hb.json").read_text(encoding="utf-8"))
    assert hb["alive"] is True
    assert hb["last_orders_placed"] == 2
    assert hb["last_cycle_started_at"] == "2026-07-09T00:00:00+00:00"
    assert hb["last_cycle_at"] == "2026-07-09T00:08:00+00:00"
    assert record["completed_at"] == "2026-07-09T00:08:00+00:00"
