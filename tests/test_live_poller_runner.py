"""Wave-16: the bounded live-poll session that mounts the Wave-3 poller."""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
spec = importlib.util.spec_from_file_location(
    "run_dummy_live_poller", ROOT / "scripts" / "run_dummy_live_poller.py")
runner = importlib.util.module_from_spec(spec)
sys.modules["run_dummy_live_poller"] = runner
spec.loader.exec_module(runner)


class _Result:
    def __init__(self, events=(), next_interval=20.0, live=()):
        self.events = tuple(events)
        self.next_interval = next_interval
        self.live_event_ids = tuple(live)


class _FakePoller:
    def __init__(self, results, enabled=True):
        self._results = list(results)
        self.enabled = enabled
        self.polls = 0

    def poll_once(self):
        self.polls += 1
        return self._results.pop(0) if self._results else _Result()


def _patch_paths(monkeypatch, tmp_path):
    monkeypatch.setattr(runner, "RUNTIME_DIR", tmp_path)
    monkeypatch.setattr(runner, "EVENTS_PATH", tmp_path / "live_events.jsonl")
    monkeypatch.setattr(runner, "STATUS_PATH", tmp_path / "live_poller_status.json")
    monkeypatch.setattr(runner, "LOCK_PATH", tmp_path / "live_poller.lock")


def test_idle_slate_exits_on_first_poll(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    poller = _FakePoller([_Result(live=())])
    summary = runner.run_session(
        budget_seconds=270, leagues=("mlb",), poller=poller,
        sleep_fn=lambda s: None)
    assert summary["status"] == "IDLE_NO_LIVE_GAMES"
    assert poller.polls == 1
    written = json.loads((tmp_path / "live_poller_status.json").read_text())
    assert written["status"] == "IDLE_NO_LIVE_GAMES"


def test_live_games_poll_until_budget(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    clock = {"t": 0.0}

    def now():
        return clock["t"]

    def sleep(seconds):
        clock["t"] += seconds

    live_result = _Result(events=(), live=("g1",), next_interval=100.0)
    poller = _FakePoller([
        _Result(events=("e1", "e2"), live=("g1",), next_interval=100.0),
        _Result(events=("e3",), live=("g1",), next_interval=100.0),
        live_result, live_result,
    ])
    summary = runner.run_session(
        budget_seconds=250, leagues=("mlb",), poller=poller,
        sleep_fn=sleep, now_fn=now)
    assert summary["status"] == "BUDGET_EXHAUSTED"
    assert summary["events_recorded"] == 3
    assert summary["live_games"] == 1
    assert poller.polls == 4       # budget cut after the 4th poll (t=250)


def test_games_ending_completes_session_early(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    poller = _FakePoller([
        _Result(events=("e1",), live=("g1",), next_interval=1.0),
        _Result(events=(), live=()),                      # slate went dark
    ])
    summary = runner.run_session(
        budget_seconds=270, leagues=("mlb",), poller=poller,
        sleep_fn=lambda s: None)
    assert summary["status"] == "SESSION_COMPLETE"
    assert poller.polls == 2


def test_disabled_poller_reports_disabled(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    poller = _FakePoller([_Result()], enabled=False)
    summary = runner.run_session(
        budget_seconds=270, leagues=("mlb",), poller=poller,
        sleep_fn=lambda s: None)
    assert summary["status"] == "DISABLED"


def test_sink_appends_tape_and_records_observation(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    recorded = []

    class _Ledger:
        def record_external_observation(self, **kwargs):
            recorded.append(kwargs)
            return True

    sink = runner._make_sink(ledger_factory=_Ledger)
    sink({"kind": "score", "event_id": "g1", "league": "mlb",
          "home_score": 3, "away_score": 1, "detail": {}})
    lines = (tmp_path / "live_events.jsonl").read_text().strip().splitlines()
    assert len(lines) == 1 and json.loads(lines[0])["kind"] == "score"
    assert recorded[0]["source"] == "live_poller"
    assert recorded[0]["series_id"] == "mlb|g1|score"
    assert recorded[0]["value"] == 2.0


def test_sink_survives_ledger_failure(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)

    class _Boom:
        def record_external_observation(self, **kwargs):
            raise RuntimeError("database is locked")

    sink = runner._make_sink(ledger_factory=_Boom)
    sink({"kind": "score", "event_id": "g1", "league": "mlb",
          "home_score": 1, "away_score": 0, "detail": {}})
    sink({"kind": "score", "event_id": "g1", "league": "mlb",
          "home_score": 2, "away_score": 0, "detail": {}})
    lines = (tmp_path / "live_events.jsonl").read_text().strip().splitlines()
    assert len(lines) == 2       # tape survives; ledger backed off after one try


def test_lock_prevents_overlapping_sessions(monkeypatch, tmp_path):
    _patch_paths(monkeypatch, tmp_path)
    assert runner._acquire_lock(stale_seconds=420) is True
    assert runner._acquire_lock(stale_seconds=420) is False   # fresh lock held
    runner._release_lock()
    assert runner._acquire_lock(stale_seconds=420) is True
    runner._release_lock()
