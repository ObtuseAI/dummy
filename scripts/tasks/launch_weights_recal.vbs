' Hidden launcher (Wave-81): out-of-band trust-weight recalibration. The daemon
' defers the in-cycle recal once the ledger is large (a full backtest cannot
' finish inside the 13-min cycle watchdog), so this task refreshes weights with
' NO watchdog. Regular python.exe so stdout redirects to the log. No console.
'
' Wave-89: WAIT for the child and propagate its exit code. The previous
' fire-and-forget launch (bWaitOnReturn = False) returned immediately, so Task
' Scheduler recorded LastTaskResult 0 no matter what the recal did -- observed
' 2026-07-25 reporting success over
' "RECAL_ERROR OperationalError: database is locked". Waiting is safe here and
' only here among the fire-and-forget launchers: this task's
' ExecutionTimeLimit is PT1H against a run that takes ~5-40 min, so enforcing
' the limit cannot truncate it. Do NOT copy this to the PT2H ledger jobs or the
' PT4M healer without checking that margin first -- while a launcher exits
' immediately its orphaned child outlives the limit entirely.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
exitCode = shell.Run("cmd /c C:\Python314\python.exe scripts\run_dummy_weights_recal.py >> runtime\autonomy\weights_recal_stdout.log 2>&1", 0, True)
WScript.Quit exitCode
