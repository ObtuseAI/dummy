' Hidden launcher (Wave-89): autoresearch lab with NO console window.
'
' The task previously invoked C:\Python314\python.exe directly, which as a
' console application allocated a visible console on every run. See
' launch_watchdog.vbs for the full note; these two tasks were the only ones in
' the fleet still spawning a terminal.
'
' pythonw.exe is not a drop-in: run_dummy_autoresearch.py writes to stdout, and
' under pythonw sys.stdout is None so print() raises. Redirect through a hidden
' cmd instead.
'
' Supervised (bWaitOnReturn = True) so a failure reaches Task Scheduler rather
' than reporting 0. Safe here: the script self-bounds at --max-seconds 600
' against an ExecutionTimeLimit of PT15M.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
exitCode = shell.Run("cmd /c C:\Python314\python.exe scripts\run_dummy_autoresearch.py --max-seconds 600 >> runtime\autonomy\autoresearch_stdout.log 2>&1", 0, True)
WScript.Quit exitCode
