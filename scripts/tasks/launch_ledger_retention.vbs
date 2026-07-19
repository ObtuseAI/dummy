' Hidden launcher (Wave-41): the daily ledger retention pass -- archive settled
' rows older than the retention window into the companion archive DB (atomic,
' non-WAL), NO vacuum (vacuum needs an exclusive lock; run it in a maintenance
' window). No console window. Regular python.exe so stdout redirects to the log.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
shell.Run "cmd /c C:\Python314\python.exe scripts\run_dummy_ledger_retention.py --apply >> runtime\autonomy\ledger_retention_stdout.log 2>&1", 0, False
