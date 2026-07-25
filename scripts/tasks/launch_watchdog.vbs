' Hidden launcher (Wave-89): fleet watchdog with NO console window.
'
' The task previously invoked C:\Python314\python.exe directly. python.exe is a
' console application, so every run allocated a console -- a terminal flashing
' on the desktop on the most frequent task in the fleet. 43 of the other 45
' Dummy* tasks already run under pythonw.exe or a hidden wscript launcher; this
' one and DummyAutoresearch were the two that were missed.
'
' pythonw.exe is NOT a drop-in here: run_dummy_watchdog.py writes to stdout, and
' under pythonw sys.stdout is None, so print() raises (the same trap that killed
' uvicorn in #126). Redirecting to a log through a hidden cmd keeps stdout real.
'
' Supervised (bWaitOnReturn = True) so the child's exit code reaches Task
' Scheduler instead of a constant 0. Safe here: ExecutionTimeLimit is PT5M and
' the watchdog is a short artifact-age scan.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
exitCode = shell.Run("cmd /c C:\Python314\python.exe scripts\run_dummy_watchdog.py >> runtime\autonomy\watchdog_stdout.log 2>&1", 0, True)
WScript.Quit exitCode
