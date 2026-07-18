' Hidden launcher (Wave-15): runs the shadow predator with a working
' directory and append-redirected log, with NO console window. The scheduled
' task points here instead of `cmd /c ...` so nothing flashes on the desktop.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
shell.Run "cmd /c C:\Python314\python.exe scripts\run_dummy_shadow_daemon.py >> runtime\autonomy\daemon_stdout.log 2>&1", 0, False
