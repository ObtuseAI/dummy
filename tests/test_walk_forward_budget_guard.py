"""Wave-85: the walk-forward runner must survive a model it cannot afford.

DummyWF_ncaamb was killed at its PT20M limit on every run and, because the
artifact was written only after the whole loop, discarded every model it had
already computed. Persisting per model fixed the loss; these tests pin the
parts that make it actually CONVERGE rather than dying in the same place daily.
"""
from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "run_dummy_sports_walk_forward.py"


@pytest.fixture()
def wf(tmp_path, monkeypatch):
    spec = importlib.util.spec_from_file_location("wf_under_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["wf_under_test"] = module
    spec.loader.exec_module(module)
    # Never touch the live artifact.
    monkeypatch.setattr(module, "ARTIFACT", tmp_path / "sports_walk_forward.json")
    return module


def _write(wf, blob):
    wf.ARTIFACT.parent.mkdir(parents=True, exist_ok=True)
    wf.ARTIFACT.write_text(json.dumps(blob), encoding="utf-8")


def _read(wf):
    return json.loads(wf.ARTIFACT.read_text(encoding="utf-8"))


def test_kill_markers_accumulate_instead_of_oscillating(wf):
    """A single-slot marker makes a two-bad-model league loop forever.

    ncaamb has exactly that shape: four_factors AND epa each outrun the budget.
    With one slot, the run skips the remembered model, dies in the other, the
    marker swaps, and the next run repeats it mirrored -- forever.
    """
    _write(wf, {"in_flight": {"league": "ncaamb", "model": "four_factors"}})
    assert wf._harvest_kill_marker() == {"ncaamb": ["four_factors"]}
    assert "in_flight" not in _read(wf)

    blob = _read(wf)
    blob["in_flight"] = {"league": "ncaamb", "model": "epa"}
    _write(wf, blob)
    assert wf._harvest_kill_marker() == {"ncaamb": ["four_factors", "epa"]}


def test_persist_preserves_kill_forensics(wf):
    """_persist rebuilt the blob and silently disarmed the guard.

    It only ever looked safe because a KILLED run never reaches _persist.
    """
    _write(wf, {"overran": {"ncaamb": ["four_factors"]}, "leagues": {}})
    wf._persist({}, [], "OK", [])
    assert _read(wf)["overran"] == {"ncaamb": ["four_factors"]}


def test_completing_a_model_earns_it_back(wf):
    """A bigger budget or a faster model must not need a manual reset."""
    _write(wf, {"overran": {"ncaamb": ["four_factors", "epa"]}})
    wf._mark_in_flight("ncaamb", "epa", clear=True)
    assert _read(wf)["overran"] == {"ncaamb": ["four_factors"]}
    wf._mark_in_flight("ncaamb", "four_factors", clear=True)
    assert _read(wf).get("overran") == {}


def test_persist_never_drops_a_model_it_did_not_rerun(wf):
    """Per-league merge: a single-league run must not erase other leagues."""
    _write(wf, {"leagues": {
        "nhl": {"glicko": {"n": 16577}},
        "mlb": {"glicko": {"n": 7651}, "epa": {"n": 3}},
    }})
    wf._persist({"mlb": {"glicko": {"n": 9999}}}, [], "OK", ["mlb"])
    leagues = _read(wf)["leagues"]
    assert leagues["mlb"]["glicko"]["n"] == 9999      # refreshed
    assert leagues["mlb"]["epa"]["n"] == 3            # untouched model kept
    assert leagues["nhl"]["glicko"]["n"] == 16577     # untouched league kept


def test_per_league_status_does_not_speak_for_other_leagues(wf):
    """Every DummyWF_<league> task writes this one shared artifact."""
    _write(wf, {"leagues": {}})
    wf._persist({}, [{"league": "ncaamb", "model": "epa", "reason": "x"}],
                "PARTIAL", ["ncaamb"])
    wf._persist({}, [], "OK", ["nhl"])
    blob = _read(wf)
    assert blob["runs"]["ncaamb"]["status"] == "PARTIAL"
    assert blob["runs"]["nhl"]["status"] == "OK"
    # A later success must not clear an earlier league's partial verdict.
    assert blob["status"] == "PARTIAL"


def test_stale_running_status_is_marked_interrupted(wf):
    """A league left mid-flight must not read as "in progress" forever.

    _persist writes RUNNING before each model and the final status after the
    loop, so a process that dies leaves RUNNING behind until that league's next
    scheduled run -- which for a per-league daily task is a full day of an
    operator seeing work that is not happening.
    """
    _write(wf, {"runs": {
        "nhl": {"status": "RUNNING", "skipped": [], "at": "t"},
        "mlb": {"status": "OK", "skipped": [], "at": "t"},
    }})
    wf._harvest_kill_marker()
    runs = _read(wf)["runs"]
    assert runs["nhl"]["status"] == "INTERRUPTED"
    assert runs["mlb"]["status"] == "OK"      # a finished league is untouched
