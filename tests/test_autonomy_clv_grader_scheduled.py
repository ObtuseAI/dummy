"""WS-8: the CLV grader is actually invoked in production, not orphaned.

The adversarial review found the grader script existed but nothing ran it, so
``runtime/autonomy/clv_report.json`` was never produced and the dashboard CLV
panel was permanently empty. The grader is wired into the SAME nightly task as
the strategy miner (two sequential actions); these tests are the tripwire that
it stays wired.

Pure text assertions over the installer script -- zero network, no schtasks
execution (that needs Windows + admin; the content check is what catches a
regression that silently drops the grader from the scheduled action).
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / "scripts" / "install_strategy_miner_task.ps1"


def test_clv_grader_script_exists():
    assert (REPO / "scripts" / "run_dummy_clv_grader.py").exists()


def test_installer_references_both_miner_and_grader():
    text = INSTALLER.read_text(encoding="utf-8")
    assert "run_dummy_strategy_miner.py" in text
    assert "run_dummy_clv_grader.py" in text


def test_installer_runs_the_grader_after_the_miner():
    text = INSTALLER.read_text(encoding="utf-8")
    # In the schtasks bootstrap action the two scripts are chained with && so
    # the grader runs only after the miner, in that order.
    miner_at = text.index("run_dummy_strategy_miner.py")
    grader_at = text.index("run_dummy_clv_grader.py")
    assert miner_at < grader_at
    # And the effective ScheduledTask action is an ARRAY of two actions
    # (Task Scheduler runs array actions sequentially).
    assert "@($minerAction, $graderAction)" in text
