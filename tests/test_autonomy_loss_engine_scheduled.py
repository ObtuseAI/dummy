"""WS-B: the loss engine is actually invoked in production, not orphaned.

Mirrors ``tests/test_autonomy_clv_grader_scheduled.py`` (WS-8): a script that
exists but is never scheduled means ``runtime/autonomy/loss_attribution.json``
is never produced and the tuner priority read / dashboard / readiness
"where we bleed" line stay permanently empty. The loss engine is wired into
the SAME nightly task as the strategy miner and CLV grader (three sequential
actions, loss engine last); these tests are the tripwire that it stays wired.

Pure text assertions over the installer script -- zero network, no schtasks
execution (that needs Windows + admin).
"""
from __future__ import annotations

from pathlib import Path

REPO = Path(__file__).resolve().parent.parent
INSTALLER = REPO / "scripts" / "install_strategy_miner_task.ps1"


def test_loss_engine_script_exists():
    assert (REPO / "scripts" / "run_dummy_loss_engine.py").exists()


def test_installer_references_the_loss_engine():
    text = INSTALLER.read_text(encoding="utf-8")
    assert "run_dummy_loss_engine.py" in text


def test_installer_runs_the_loss_engine_after_miner_and_grader():
    text = INSTALLER.read_text(encoding="utf-8")
    miner_at = text.index("run_dummy_strategy_miner.py")
    grader_at = text.index("run_dummy_clv_grader.py")
    engine_at = text.index("run_dummy_loss_engine.py")
    assert miner_at < grader_at < engine_at
    # The effective ScheduledTask action array includes all three actions in
    # order (Task Scheduler runs array actions sequentially).
    assert "@($minerAction, $graderAction, $lossEngineAction)" in text
