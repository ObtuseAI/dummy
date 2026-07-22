"""Wave-39: the Dummy Tote artifact reader (pure Python, no PySide6). The GUI
itself is validated separately under the desktop venv."""
from __future__ import annotations

import json
from pathlib import Path

import pytest

from desktop.dummy_tote.data import (
    KNOWN_LEAGUES,
    RepoData,
    league_filter_options,
    resolve_runtime_dir,
)


def _seed(root, **files):
    (root / "runtime" / "autonomy").mkdir(parents=True, exist_ok=True)
    (root / "configs").mkdir(parents=True, exist_ok=True)
    for name, payload in files.items():
        if name == "switches":
            (root / "configs" / "switches.json").write_text(json.dumps(payload), encoding="utf-8")
        else:
            (root / "runtime" / "autonomy" / f"{name}.json").write_text(json.dumps(payload), encoding="utf-8")


def test_snapshot_reads_and_derives(tmp_path):
    from datetime import datetime, timezone
    now = datetime.now(timezone.utc).isoformat()
    _seed(tmp_path,
          heartbeat={"alive": True, "mode": "shadow", "last_cycle_at": now},
          bet_board={"rows": 3, "top": [
              {"rank": 1, "matchup": "A@B", "league": "mlb", "pick": "yes",
               "probability": 0.62, "edge": 0.08},
              {"rank": 2, "matchup": "C@D", "league": "nfl", "pick": "no",
               "probability": 0.41, "edge": -0.05}]},
          heal_status={"connectivity_ok": True, "reachable": ["a", "b"], "unreachable": []},
          clv_report={"scopes": {"crypto|15m": {"n_entries": 5, "clv_bps_mean": 3.1}}},
          auto_promotion_state={"status": "OK", "eligible_scopes": 4},
          readiness_report={"promotion_candidates": ["x|sol"], "scopes": [{"scope": "x"}]},
          switches={"main": True, "crypto": False, "llm": {"claude": True}})
    snap = RepoData(tmp_path).snapshot()
    assert snap.alive() and snap.mode() == "shadow"
    assert snap.pick_count() == 3 and len(snap.picks()) == 2
    assert abs(snap.top_edge() - 0.08) < 1e-9
    assert snap.connectivity_ok() is True
    assert snap.llm_state()["claude"] is True and snap.llm_state()["codex"] is False
    assert "heartbeat.json" not in snap.stale()   # fresh
    assert snap.clv["scopes"]["crypto|15m"]["clv_bps_mean"] == 3.1
    assert snap.promotion["status"] == "OK"
    assert snap.readiness["promotion_candidates"] == ["x|sol"]


def test_missing_files_are_fail_soft(tmp_path):
    snap = RepoData(tmp_path).snapshot()          # nothing seeded
    assert snap.alive() is False and snap.picks() == []
    assert snap.connectivity_ok() is True         # no heal report -> assume ok
    assert "heartbeat.json" in snap.stale()       # absent -> stale


def test_league_filter_roster_keeps_nfl_when_current_board_has_no_nfl_rows():
    options = league_filter_options([
        {"league": "mlb"},
        {"league": "wnba"},
        {"league": "newleague"},
    ])

    assert options[: len(KNOWN_LEAGUES)] == KNOWN_LEAGUES
    assert "nfl" in options
    assert options[-1] == "newleague"


def test_set_switch_writes_the_shared_file(tmp_path):
    (tmp_path / "configs").mkdir(parents=True)
    (tmp_path / "configs" / "switches.json").write_text(
        json.dumps({"main": True, "leagues": {"mlb": True}, "llm": {"codex": False}}),
        encoding="utf-8")
    data = RepoData(tmp_path)
    data.set_switch("crypto", False)
    data.set_switch("league", True, "nfl")
    data.set_switch("llm", True, "codex")
    written = json.loads((tmp_path / "configs" / "switches.json").read_text())
    assert written["crypto"] is False
    assert written["leagues"]["nfl"] is True and written["leagues"]["mlb"] is True
    assert written["llm"]["codex"] is True


def test_load_reuses_unchanged_artifact_and_refreshes_on_mtime_change(tmp_path, monkeypatch):
    _seed(tmp_path, heartbeat={"alive": True})
    target = tmp_path / "runtime" / "autonomy" / "heartbeat.json"
    original = Path.read_text
    reads = []

    def counting_read(path, *args, **kwargs):
        if path == target:
            reads.append(path)
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", counting_read)
    data = RepoData(tmp_path)
    assert data.snapshot().alive() is True
    assert data.snapshot().alive() is True
    assert len(reads) == 1

    target.write_text(json.dumps({"alive": False, "padding": "changed-size"}), encoding="utf-8")
    assert data.snapshot().alive() is False
    assert len(reads) == 2


def test_set_switch_failure_does_not_replace_source(tmp_path, monkeypatch):
    _seed(tmp_path, switches={"main": True})
    data = RepoData(tmp_path)
    original = (tmp_path / "configs" / "switches.json").read_text(encoding="utf-8")

    def fail_replace(_self, _target):
        raise OSError("write denied")

    monkeypatch.setattr(Path, "replace", fail_replace)
    with pytest.raises(OSError, match="write denied"):
        data.set_switch("main", False)
    assert (tmp_path / "configs" / "switches.json").read_text(encoding="utf-8") == original


def test_runtime_dir_uses_repo_default_or_explicit_override(tmp_path, monkeypatch):
    monkeypatch.delenv("DUMMY_RUNTIME_DIR", raising=False)
    assert resolve_runtime_dir(tmp_path) == tmp_path / "runtime" / "autonomy"
    override = tmp_path / "alternate-runtime"
    monkeypatch.setenv("DUMMY_RUNTIME_DIR", str(override))
    assert resolve_runtime_dir(tmp_path) == override
