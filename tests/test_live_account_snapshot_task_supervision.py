from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_live_account_launcher_supervises_exact_hidden_child() -> None:
    launcher = (
        ROOT / "scripts" / "tasks" / "launch_live_account_snapshot.vbs"
    ).read_text(encoding="utf-8")

    assert "Set child = shell.Exec" in launcher
    assert 'shell.Exec("C:\\Python314\\python.exe' in launcher
    assert "run_dummy_live_account_snapshot.py" in launcher
    assert 'DateAdd("n", 2, Now)' in launcher
    assert "taskkill.exe /PID " in launcher
    assert ' & " /T /F"' in launcher
    assert "child.Terminate" in launcher
    assert "WScript.Quit 124" in launcher
    assert "WScript.Quit child.ExitCode" in launcher
    assert "DUMMY_LIVE_ACCOUNT_STDIO_LOG" in launcher
    assert "child.StdOut" not in launcher
    assert "child.StdErr" not in launcher
    assert "ReadAll" not in launcher
    assert 'shell.Exec("cmd /c ' not in launcher


def test_live_account_installer_is_bounded_read_only_and_ignore_new() -> None:
    installer = (
        ROOT / "scripts" / "install_live_account_snapshot_task.ps1"
    ).read_text(encoding="utf-8")

    assert 'TaskName = "DummyLiveAccountSnapshot"' in installer
    assert "-MultipleInstances IgnoreNew" in installer
    assert 'ExecutionTimeLimitMinutes = 3' in installer
    assert 'wscript.exe' in installer
    assert 'ReadOnly = $true' in installer
    assert 'GetOnly = $true' in installer
    assert 'ExecutionAuthority = $false' in installer
    assert 'MutatesLiveSubmit = $false' in installer
    assert 'MutatesCaps = $false' in installer


def test_live_account_script_redirects_before_project_imports() -> None:
    script = (
        ROOT / "scripts" / "run_dummy_live_account_snapshot.py"
    ).read_text(encoding="utf-8")

    redirect = script.index("_SUPERVISED_LOG_HANDLE = _redirect_supervised_stdio()")
    project_import = script.index("from autonomy.live_account_snapshot import")
    assert redirect < project_import
    assert 'os.environ.get("DUMMY_LIVE_ACCOUNT_STDIO_LOG"' in script
    assert "os.dup2(handle.fileno(), 1)" in script
    assert "os.dup2(handle.fileno(), 2)" in script
    assert "create_order" not in script
    assert "cancel_order" not in script
