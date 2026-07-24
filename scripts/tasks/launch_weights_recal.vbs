' Hidden launcher (Wave-81): out-of-band trust-weight recalibration. The daemon
' defers the in-cycle recal once the ledger is large (a full backtest cannot
' finish inside the 13-min cycle watchdog), so this task refreshes weights with
' NO watchdog. Regular python.exe so stdout redirects to the log. No console.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
shell.Run "cmd /c C:\Python314\python.exe scripts\run_dummy_weights_recal.py >> runtime\autonomy\weights_recal_stdout.log 2>&1", 0, False
