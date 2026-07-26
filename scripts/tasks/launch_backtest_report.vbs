' Hidden launcher (Wave-44): the heavy backtest DIAGNOSTICS, split out of the 6h
' weight recal. Runs the full backtest (the ~11 full-ledger-scan sub-reports) and
' writes summary/self-improvement/dashboard-snapshot. No console window. Regular
' python.exe so stdout redirects to the log.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
exitCode = shell.Run("cmd /c C:\Python314\python.exe scripts\run_dummy_backtest_report.py >> runtime\autonomy\backtest_report_stdout.log 2>&1", 0, True)
WScript.Quit exitCode
