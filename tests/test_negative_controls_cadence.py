"""The negative-control battery runs on the BACKTEST cadence, not just nightly.

2026-07-24 audit §8: "Negative-control battery is CLEAN but ~40h stale while
the backtest runs ~3-hourly — run controls on the backtest cadence." The
battery's only home was the nightly self-improvement chain, so the fabrication
tripwires and the NO_EDGE_MAP that feeds the fusion floor lagged a day and a
half behind the weights they police.

Two halves, both hermetic:
  * text assertions over the installer + launcher (mirrors
    ``tests/test_autonomy_loss_engine_scheduled.py``: no schtasks execution,
    which needs Windows + admin), and
  * the runner's own cadence safety — the skip-if-recent guard that lets the
    scheduled task and the nightly chain both call it without ever grading the
    same rows twice in a row.
"""
from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from pathlib import Path

from scripts.run_negative_controls import (
    BACKTEST_CADENCE_HOURS,
    MIN_RERUN_INTERVAL_HOURS,
    _report_age_hours,
    main,
)
import scripts.run_negative_controls as runner

REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / "scripts" / "register_negative_controls_task.ps1"
LAUNCHER = REPO / "scripts" / "tasks" / "launch_negative_controls.vbs"
CHAIN = REPO / "scripts" / "run_dummy_self_improvement.py"


def _write_report(path: Path, *, age_hours: float, flagged: list[str]) -> None:
    generated_at = datetime.now(timezone.utc) - timedelta(hours=age_hours)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(
            {
                "report_name": "NEGATIVE_CONTROL_REPORT",
                "generated_at": generated_at.isoformat(),
                "status": "FLAGGED" if flagged else "CLEAN",
                "flagged_sources": flagged,
                "sources": {},
            }
        ),
        encoding="utf-8",
    )


# --------------------------------------------------------------------- task


def test_installer_and_launcher_exist():
    assert INSTALLER.exists()
    assert LAUNCHER.exists()


def test_installer_registers_a_dedicated_task_on_the_backtest_cadence():
    text = INSTALLER.read_text(encoding="utf-8")
    assert '$name = "DummyNegativeControls"' in text
    assert "launch_negative_controls.vbs" in text
    # Same repetition shape as the other recurring installers, at the backtest
    # cadence (6h == autonomy/daemon.py RECAL_INTERVAL_HOURS / DummyWeightsRecal).
    assert "-RepetitionInterval (New-TimeSpan -Hours 6)" in text
    assert "Register-ScheduledTask" in text
    assert "-MultipleInstances IgnoreNew" in text
    assert "-ExecutionTimeLimit" in text          # bounded runtime
    assert int(BACKTEST_CADENCE_HOURS) == 6


def test_launcher_is_windowless_and_runs_the_controls_runner():
    text = LAUNCHER.read_text(encoding="utf-8")
    assert "scripts\\run_negative_controls.py" in text
    assert "negative_controls_stdout.log" in text
    assert "exitCode = shell.Run(" in text
    assert ", 0, True)" in text                    # hidden window; wait for child
    assert "WScript.Quit exitCode" in text          # preserve the exact status


def test_controls_remain_in_the_nightly_chain():
    """Coverage is ADDED by the task, never moved off the nightly chain."""
    text = CHAIN.read_text(encoding="utf-8")
    assert '("negative_controls", ["scripts/run_negative_controls.py"]' in text


# ------------------------------------------------------------------- runner


def test_rerun_guard_is_under_the_backtest_cadence():
    # A guard equal to the cadence lets clock jitter skip a whole period and
    # silently halve the real cadence.
    assert 0 < MIN_RERUN_INTERVAL_HOURS < BACKTEST_CADENCE_HOURS


def test_report_age_is_read_from_the_artifact(tmp_path, monkeypatch):
    path = tmp_path / "negative_control_report.json"
    _write_report(path, age_hours=2.0, flagged=[])
    monkeypatch.setattr(runner, "REPORT_PATH", path)

    age, report = _report_age_hours(datetime.now(timezone.utc))
    assert age is not None and 1.9 < age < 2.1
    assert report["status"] == "CLEAN"


def test_missing_or_corrupt_report_never_blocks_a_run(tmp_path, monkeypatch):
    missing = tmp_path / "absent.json"
    monkeypatch.setattr(runner, "REPORT_PATH", missing)
    assert _report_age_hours(datetime.now(timezone.utc)) == (None, {})

    corrupt = tmp_path / "corrupt.json"
    corrupt.write_text("{not json", encoding="utf-8")
    monkeypatch.setattr(runner, "REPORT_PATH", corrupt)
    assert _report_age_hours(datetime.now(timezone.utc)) == (None, {})

    naive = tmp_path / "naive.json"
    naive.write_text(
        json.dumps({"generated_at": "2026-07-24T00:00:00"}), encoding="utf-8"
    )
    monkeypatch.setattr(runner, "REPORT_PATH", naive)
    assert _report_age_hours(datetime.now(timezone.utc)) == (None, {})


def test_fresh_clean_report_is_skipped_without_touching_the_ledger(
    tmp_path, monkeypatch, capsys,
):
    path = tmp_path / "negative_control_report.json"
    _write_report(path, age_hours=0.5, flagged=[])
    monkeypatch.setattr(runner, "REPORT_PATH", path)
    monkeypatch.setattr(runner, "LEDGER_PATH", tmp_path / "no_such_ledger.db")
    monkeypatch.setattr(runner.sys, "argv", ["run_negative_controls.py"])

    assert main() == 0
    assert "skipping" in capsys.readouterr().out


def test_skipped_run_still_reports_a_standing_flag(tmp_path, monkeypatch, capsys):
    """Fail-closed: skipping the rerun must not launder a FLAGGED verdict."""
    path = tmp_path / "negative_control_report.json"
    _write_report(path, age_hours=0.5, flagged=["crypto_patience_confirm"])
    monkeypatch.setattr(runner, "REPORT_PATH", path)
    monkeypatch.setattr(runner, "LEDGER_PATH", tmp_path / "no_such_ledger.db")
    monkeypatch.setattr(runner.sys, "argv", ["run_negative_controls.py"])

    assert main() == 1
    assert "FLAGGED" in capsys.readouterr().out


def test_a_report_older_than_the_guard_is_not_skipped(tmp_path, monkeypatch):
    path = tmp_path / "negative_control_report.json"
    _write_report(path, age_hours=MIN_RERUN_INTERVAL_HOURS + 0.5, flagged=[])
    monkeypatch.setattr(runner, "REPORT_PATH", path)

    age, _report = _report_age_hours(datetime.now(timezone.utc))
    assert age is not None and age >= MIN_RERUN_INTERVAL_HOURS
