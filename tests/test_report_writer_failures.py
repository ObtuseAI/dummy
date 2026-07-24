"""Report-writer failures are LOUD, isolated, and recorded (2026-07-24 audit).

Eight report artifacts (film_room.json, self_scout.json, fusion_ablation.json,
recruiting_board.json, development_tracker.json, edge_concentration.json,
model_authority_eligibility.json, llm_value_report.json) were entirely missing
from runtime/autonomy/ because their writers in
scripts/run_dummy_readiness_report.py crashed silently behind
``except Exception: pass`` (mostly sqlite "database is locked") while the
scheduled task stayed green. These tests pin the fix:

* one writer raising never stops the others (isolation was always right --
  only the silence was wrong);
* every failure lands in runtime/autonomy/report_writer_failures.json with
  the writer name, repr(exc), a bounded traceback tail, and a UTC stamp;
* the failures artifact is written EVERY run, even when empty, so a stale
  artifact is itself detectable;
* any writer failure exits EXIT_WRITER_FAILED (3) so Task Scheduler shows
  red, while every surviving artifact is still written first;
* a picks failure marks the section {"status": "UNAVAILABLE", ...} instead
  of shipping a bare error string inside readiness_report.json.

Also: scripts/run_dummy_self_improvement.py must propagate step failures
(on Jul 23 all three steps exited 1 while the wrapper exited 0).
"""
from __future__ import annotations

import importlib.util
import json
import sqlite3
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _load_script(filename: str, alias: str):
    spec = importlib.util.spec_from_file_location(
        alias, REPO_ROOT / "scripts" / filename,
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _load_readiness():
    return _load_script(
        "run_dummy_readiness_report.py", "run_dummy_readiness_report_under_test",
    )


def _load_self_improvement():
    return _load_script(
        "run_dummy_self_improvement.py", "run_dummy_self_improvement_under_test",
    )


# ---------------------------------------------------------------------------
# WriterFailureRail unit behavior
# ---------------------------------------------------------------------------

def test_rail_records_failure_shape_and_keeps_going():
    module = _load_readiness()
    rail = module.WriterFailureRail()

    def _boom():
        raise sqlite3.OperationalError("database is locked")

    assert rail.run("film_room", _boom, default="fallback") == "fallback"
    assert rail.run("recruiting_board", lambda: {"by_stage": {}}) == {
        "by_stage": {},
    }

    assert rail.ok_writers == ["recruiting_board"]
    assert len(rail.failures) == 1
    failure = rail.failures[0]
    assert failure["writer"] == "film_room"
    assert "database is locked" in failure["error"]
    assert isinstance(failure["traceback"], list)
    assert 0 < len(failure["traceback"]) <= module.TRACEBACK_TAIL_LINES
    assert any("OperationalError" in line for line in failure["traceback"])
    # ISO-8601 UTC stamp, parseable.
    parsed = datetime.fromisoformat(failure["at"])
    assert parsed.tzinfo is not None
    assert rail.error_for("film_room") == failure["error"]
    assert rail.error_for("recruiting_board") is None


def test_failures_artifact_written_even_when_empty(tmp_path):
    module = _load_readiness()
    rail = module.WriterFailureRail()
    rail.run("picks", lambda: {"sources": []})
    target = tmp_path / "report_writer_failures.json"
    module.write_failures_artifact(rail, path=target)
    payload = json.loads(target.read_text(encoding="utf-8"))
    assert payload["failures"] == []
    assert payload["ok_writers"] == ["picks"]
    assert payload["generated_at"]


# ---------------------------------------------------------------------------
# main() end-to-end (stubbed writers, real rail + artifacts + exit codes)
# ---------------------------------------------------------------------------

def _scaffold_runtime(tmp_path, monkeypatch):
    """Minimal on-disk world for main(): fresh backtest stamp + empty ledger.

    Every artifact path in the runner is cwd-relative, so chdir(tmp_path)
    keeps the whole run inside the test sandbox.
    """
    monkeypatch.chdir(tmp_path)
    runtime = tmp_path / "runtime" / "autonomy"
    runtime.mkdir(parents=True)
    (runtime / "latest_backtest_summary.json").write_text(
        json.dumps({
            "generated_at": datetime.now(timezone.utc).isoformat(),
        }),
        encoding="utf-8",
    )
    db = runtime / "ledger.db"
    conn = sqlite3.connect(db)
    conn.executescript(
        """
        CREATE TABLE signals(
            id INTEGER PRIMARY KEY AUTOINCREMENT, source TEXT, market_ticker TEXT,
            probability_yes REAL, uncertainty REAL, rationale TEXT, created_at TEXT,
            mode TEXT, features TEXT, ingested_at TEXT, ingest_version INTEGER
        );
        CREATE TABLE settlements(
            market_ticker TEXT PRIMARY KEY, result_yes INTEGER, settled_at TEXT
        );
        """
    )
    conn.commit()
    conn.close()
    return db


class _FakeHistoryStore:
    """Stands in for SportsHistoryStore in the holdout + development writers."""

    def __init__(self, *args, **kwargs):
        pass

    def evaluation_eligibility(self, league):
        return {
            "eligible": False,
            "final_candidates": 0,
            "rejection_reasons": ["insufficient_seasons"],
        }

    def close(self):
        pass


def _stub_writers(monkeypatch, ran: list[str], *, raising: dict | None = None):
    """Replace every heavyweight writer with a recording stub.

    ``raising`` maps a target name to an exception instance that stub raises
    instead of returning its canned value.
    """
    raising = raising or {}
    targets = {
        "autonomy.development_tracker.write_development_tracker": (
            "development_tracker", {"warnings": []}),
        "autonomy.self_scout.write_self_scout": (
            "self_scout", {"warnings": []}),
        "autonomy.film_room.write_film_room": ("film_room", None),
        "autonomy.recruiting_board.write_recruiting_board": (
            "recruiting_board", {"by_stage": {"commit": 1}}),
        "autonomy.fusion_ablation.write_fusion_ablation": (
            "fusion_ablation", {"redundancy_candidates": []}),
        "autonomy.edge_concentration.write_edge_concentration": (
            "edge_concentration", {"narrow_edge_sources": []}),
        "forecasting.model_evidence_builder.build_and_write": (
            "model_authority_evidence",
            {"scopes": [], "governance_eligible_scopes": [],
             "dossier_authored": False}),
        "autonomy.llm_value_report.write_llm_value_report": (
            "llm_value_report", {"voices": []}),
    }

    def _make(name, result):
        def _stub(*args, **kwargs):
            ran.append(name)
            if name in raising:
                raise raising[name]
            return result
        return _stub

    for dotted, (name, result) in targets.items():
        monkeypatch.setattr(dotted, _make(name, result))

    monkeypatch.setattr(
        "autonomy.picks.llm_voice_sources", lambda conn, **kwargs: (),
    )
    monkeypatch.setattr(
        "autonomy.picks.pick_accuracy_report", _make("picks", {"sources": []}),
    )
    monkeypatch.setattr(
        "autonomy.sports.history_store.SportsHistoryStore", _FakeHistoryStore,
    )


def _run_main(module, monkeypatch, db):
    monkeypatch.setattr(sys, "argv", [
        "run_dummy_readiness_report.py",
        "--db", str(db),
        "--skip-auto-promotion",
    ])
    return module.main()


def test_all_writers_ok_exit_zero_and_empty_failures_artifact(
        tmp_path, monkeypatch, capsys):
    module = _load_readiness()
    db = _scaffold_runtime(tmp_path, monkeypatch)
    ran: list[str] = []
    _stub_writers(monkeypatch, ran)

    rc = _run_main(module, monkeypatch, db)

    assert rc == 0
    failures_path = tmp_path / "runtime" / "autonomy" / "report_writer_failures.json"
    payload = json.loads(failures_path.read_text(encoding="utf-8"))
    assert payload["failures"] == []
    for writer in (
        "picks", "holdout_eligibility", "age_curve_watch",
        "development_tracker", "self_scout", "film_room", "recruiting_board",
        "fusion_ablation", "edge_concentration", "model_authority_evidence",
        "llm_value_report", "fused_picks_summary",
    ):
        assert writer in payload["ok_writers"], writer
    report = json.loads(
        (tmp_path / "runtime" / "autonomy" / "readiness_report.json")
        .read_text(encoding="utf-8"))
    assert report["picks"] == {"sources": []}
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["status"] == "OK"
    assert "writer_failures" not in summary


def test_one_writer_raising_never_stops_the_others(
        tmp_path, monkeypatch, capsys):
    module = _load_readiness()
    db = _scaffold_runtime(tmp_path, monkeypatch)
    ran: list[str] = []
    _stub_writers(monkeypatch, ran, raising={
        "film_room": sqlite3.OperationalError("database is locked"),
    })

    rc = _run_main(module, monkeypatch, db)

    # Distinct nonzero code so Task Scheduler shows the run red (1 = no DB,
    # 2 = stale backtest are already taken).
    assert rc == module.EXIT_WRITER_FAILED == 3

    # Everything after the crashing writer still ran.
    film_at = ran.index("film_room")
    for later in ("recruiting_board", "fusion_ablation", "edge_concentration",
                  "model_authority_evidence", "llm_value_report"):
        assert ran.index(later) > film_at

    failures_path = tmp_path / "runtime" / "autonomy" / "report_writer_failures.json"
    payload = json.loads(failures_path.read_text(encoding="utf-8"))
    assert [entry["writer"] for entry in payload["failures"]] == ["film_room"]
    failure = payload["failures"][0]
    assert "database is locked" in failure["error"]
    assert failure["traceback"]
    assert failure["at"]
    assert "recruiting_board" in payload["ok_writers"]
    assert "film_room" not in payload["ok_writers"]

    # The readiness report itself (written before the writers) survived.
    assert (tmp_path / "runtime" / "autonomy" / "readiness_report.json").exists()

    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["status"] == "WRITER_FAILURES"
    assert summary["writer_failures"] == ["film_room"]


def test_picks_failure_marks_section_unavailable_not_error_string(
        tmp_path, monkeypatch):
    module = _load_readiness()
    db = _scaffold_runtime(tmp_path, monkeypatch)
    ran: list[str] = []
    _stub_writers(monkeypatch, ran, raising={
        "picks": sqlite3.OperationalError("database is locked"),
    })

    rc = _run_main(module, monkeypatch, db)

    assert rc == module.EXIT_WRITER_FAILED
    report = json.loads(
        (tmp_path / "runtime" / "autonomy" / "readiness_report.json")
        .read_text(encoding="utf-8"))
    assert report["picks"]["status"] == "UNAVAILABLE"
    assert "database is locked" in report["picks"]["reason"]
    # The old shape shipped a bare 'ERROR: ...' string; it must be gone.
    assert report["picks"].get("error") is None
    payload = json.loads(
        (tmp_path / "runtime" / "autonomy" / "report_writer_failures.json")
        .read_text(encoding="utf-8"))
    assert "picks" in [entry["writer"] for entry in payload["failures"]]


# ---------------------------------------------------------------------------
# run_dummy_self_improvement.py: step failures propagate
# ---------------------------------------------------------------------------

def _plan_capture(tmp_path, monkeypatch):
    plan_path = tmp_path / "self_improvement_plan.json"
    monkeypatch.setattr(
        "autonomy.improvement_planner.assemble_plan", lambda: {"items": []},
    )

    def _write_plan(plan, path=None):
        plan_path.write_text(json.dumps(plan), encoding="utf-8")
        return plan_path

    monkeypatch.setattr("autonomy.improvement_planner.write_plan", _write_plan)
    return plan_path


def test_self_improvement_step_failure_propagates(tmp_path, monkeypatch, capsys):
    module = _load_self_improvement()
    monkeypatch.setattr(module, "STEPS", [
        ("ok_step", ["-c", "print('fine')"], 30.0),
        ("bad_step",
         ["-c", "import sys; sys.stderr.write('boom\\n'); sys.exit(1)"], 30.0),
    ])
    plan_path = _plan_capture(tmp_path, monkeypatch)

    rc = module.main()

    # Jul 23 regression: all steps exited 1, wrapper exited 0, Task Scheduler
    # showed success. Now the wrapper is red on any step failure.
    assert rc == module.EXIT_STEP_FAILED == 3
    chain = json.loads(plan_path.read_text(encoding="utf-8"))["chain"]
    assert chain["ok"] is False
    assert chain["failed_steps"] == ["bad_step"]
    assert chain["steps"]["ok_step"]["status"] == "OK"
    assert chain["steps"]["ok_step"]["exit"] == 0
    assert chain["steps"]["bad_step"]["status"] == "FAILED"
    assert chain["steps"]["bad_step"]["exit"] == 1
    assert "boom" in chain["steps"]["bad_step"]["stderr_last"]
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["status"] == "STEP_FAILURES"
    assert summary["failed_steps"] == ["bad_step"]


def test_self_improvement_all_steps_ok_exits_zero(tmp_path, monkeypatch, capsys):
    module = _load_self_improvement()
    monkeypatch.setattr(module, "STEPS", [
        ("ok_step", ["-c", "print('fine')"], 30.0),
    ])
    plan_path = _plan_capture(tmp_path, monkeypatch)

    rc = module.main()

    assert rc == 0
    chain = json.loads(plan_path.read_text(encoding="utf-8"))["chain"]
    assert chain["ok"] is True
    assert chain["failed_steps"] == []
    assert chain["steps"]["ok_step"]["status"] == "OK"
    summary = json.loads(capsys.readouterr().out.strip().splitlines()[-1])
    assert summary["status"] == "OK"
