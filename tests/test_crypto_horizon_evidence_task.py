"""The crypto horizon evidence job is scheduled, supervised, and bounded."""
from __future__ import annotations

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def test_runner_redirects_os_descriptors_before_autonomy_imports():
    runner = (ROOT / "scripts" / "run_dummy_crypto_horizon_evidence.py").read_text(
        encoding="utf-8"
    )
    redirect = runner.index("_SUPERVISED_LOG_HANDLE = _redirect_supervised_stdio()")
    autonomy_import = runner.index("from autonomy.crypto_horizon_evidence import")
    assert redirect < autonomy_import
    assert 'os.environ.get("DUMMY_CRYPTO_HORIZON_STDIO_LOG"' in runner
    assert "os.dup2(handle.fileno(), 1)" in runner
    assert "os.dup2(handle.fileno(), 2)" in runner


def test_reconciliation_caps_raised_but_still_bounded():
    from scripts.run_dummy_crypto_horizon_evidence import (
        DEFAULT_MAX_SETTLEMENT_TICKERS,
        DEFAULT_SETTLEMENT_TIME_BUDGET_SECONDS,
    )

    # High enough to drain a ~500-ticker backlog in ~11 sweeps, low enough
    # that one segment stays a bounded, fair, cooperative slice.
    assert DEFAULT_MAX_SETTLEMENT_TICKERS == 48
    assert DEFAULT_SETTLEMENT_TIME_BUDGET_SECONDS == 120.0


def test_launcher_supervises_child_directly():
    launcher = (ROOT / "scripts" / "tasks" / "launch_crypto_horizon_evidence.vbs").read_text(
        encoding="utf-8"
    )
    assert 'shell.Exec("C:\\Python314\\python.exe scripts\\run_dummy_crypto_horizon_evidence.py' in launcher
    assert 'shell.Exec("cmd /c ' not in launcher
    assert ", 0, False)" not in launcher
    assert 'processEnvironment("DUMMY_CRYPTO_HORIZON_STDIO_LOG")' in launcher
    assert "child.StdOut" not in launcher
    assert "ReadAll" not in launcher
    assert "taskkill.exe /PID" in launcher
    assert "WScript.Quit child.ExitCode" in launcher


def test_installer_bounds_and_supervises_task():
    installer = (ROOT / "scripts" / "install_crypto_horizon_evidence_task.ps1").read_text(
        encoding="utf-8"
    )
    assert '"DummyCryptoHorizonEvidence"' in installer
    assert "-MultipleInstances IgnoreNew" in installer
    assert "ExecutionTimeLimit" in installer
    assert "launch_crypto_horizon_evidence.vbs" in installer
    assert "wscript.exe" in installer
