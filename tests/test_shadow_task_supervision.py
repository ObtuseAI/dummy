from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]


def test_shadow_launcher_waits_and_propagates_child_exit_code():
    launcher = (ROOT / "scripts" / "tasks" / "launch_shadow_predator.vbs").read_text(
        encoding="utf-8"
    )
    assert "Set child = shell.Exec" in launcher
    assert 'DateAdd("n", 13, Now)' in launcher
    assert 'DateAdd("n", 15, Now)' not in launcher
    assert "child.Terminate" in launcher
    assert "taskkill.exe /PID " in launcher
    assert ' & " /T /F"' in launcher
    assert "WScript.Quit child.ExitCode" in launcher
    assert "WScript.Quit 124" in launcher
    assert 'shell.Exec("C:\\Python314\\python.exe' in launcher
    assert 'shell.Exec("cmd /c ' not in launcher
    assert ", 0, False)" not in launcher
    assert 'processEnvironment("DUMMY_SHADOW_STDIO_LOG")' in launcher
    assert "child.StdOut" not in launcher
    assert "child.StdErr" not in launcher
    assert "ReadAll" not in launcher


def test_shadow_daemon_redirects_os_descriptors_before_autonomy_imports():
    daemon = (ROOT / "scripts" / "run_dummy_shadow_daemon.py").read_text(
        encoding="utf-8"
    )
    redirect = daemon.index("_SUPERVISED_LOG_HANDLE = _redirect_supervised_stdio()")
    autonomy_import = daemon.index("from autonomy.daemon import run_one_cycle")
    assert redirect < autonomy_import
    assert 'os.environ.get("DUMMY_SHADOW_STDIO_LOG"' in daemon
    assert "os.dup2(handle.fileno(), 1)" in daemon
    assert "os.dup2(handle.fileno(), 2)" in daemon


def test_shadow_installer_bounds_and_supervises_task():
    installer = (ROOT / "scripts" / "install_shadow_predator_task.ps1").read_text(
        encoding="utf-8"
    )
    assert 'ExecutionTimeLimitMinutes = 15' in installer
    assert "-MultipleInstances IgnoreNew" in installer
    assert 'wscript.exe' in installer
    assert 'WaitsForChild = $true' in installer
