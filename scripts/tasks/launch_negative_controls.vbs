' Hidden launcher (Wave-84): the negative-control battery on the BACKTEST
' cadence instead of only inside the nightly chain -- the 2026-07-24 audit found
' the battery CLEAN but ~40h stale while the backtest refreshes every 6h. The
' runner self-skips when the report on disk is younger than its rerun guard, so
' firing here never duplicates the nightly chain's run. Read-only against the
' ledger. No console window. Regular python.exe so stdout redirects to the log.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
exitCode = shell.Run("cmd /c C:\Python314\python.exe scripts\run_negative_controls.py >> runtime\autonomy\negative_controls_stdout.log 2>&1", 0, True)
WScript.Quit exitCode
