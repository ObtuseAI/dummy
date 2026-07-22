from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_dashboard_snapshot_launcher_supervises_real_child():
    launcher = (
        ROOT / "scripts" / "tasks" / "launch_dashboard_snapshot.vbs"
    ).read_text(encoding="utf-8")

    assert "Set child = shell.Exec" in launcher
    assert 'DateAdd("n", 10, Now)' in launcher
    assert "child.Terminate" in launcher
    assert "taskkill /PID " in launcher
    assert ' /T /F"' in launcher
    assert "WScript.Quit child.ExitCode" in launcher
    assert "DASHBOARD_SNAPSHOT_TIMEOUT" in launcher
    assert ">> runtime\\autonomy\\dashboard_snapshot_stdout.log 2>&1" in launcher
    assert ".StdOut.ReadAll" not in launcher
    assert ".StdErr.ReadAll" not in launcher
    assert 'shell.Run "cmd /c' not in launcher
    assert ", 0, False" not in launcher
