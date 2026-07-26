' Hidden supervised launcher: Task Scheduler stays attached to the actual
' retention child and receives its real exit code. A REFUSED/lock-timeout run
' can no longer update a log while Task Scheduler falsely records success.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
exitCode = shell.Run("cmd /c C:\Python314\python.exe scripts\run_dummy_ledger_retention.py --apply >> runtime\autonomy\ledger_retention_stdout.log 2>&1", 0, True)
WScript.Quit exitCode
