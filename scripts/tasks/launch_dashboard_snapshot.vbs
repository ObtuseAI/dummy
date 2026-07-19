' Hidden launcher (Wave-42): refresh the dashboard snapshot artifact so the web
' dashboard reads a file instead of holding a SHARED lock on the ledger for a
' minutes-long backtest. --light refreshes only the cheap summaries most runs;
' the backtest refreshes when the prior one ages past the bound. No console
' window. Regular python.exe so stdout redirects to the log.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
shell.Run "cmd /c C:\Python314\python.exe scripts\run_dummy_dashboard_snapshot.py --light >> runtime\autonomy\dashboard_snapshot_stdout.log 2>&1", 0, False
