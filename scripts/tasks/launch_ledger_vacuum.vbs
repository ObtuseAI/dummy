' Hidden supervised launcher for the cooperative verified VACUUM. It never
' disables tasks or kills processes. The Python runner requires the backup
' manifest named by DUMMY_MAINTENANCE_BACKUP_MANIFEST and returns non-zero when
' backup, lease, checkpoint, integrity, or free-space checks fail.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
exitCode = shell.Run("cmd /c C:\Python314\python.exe scripts\run_dummy_ledger_vacuum.py --backup-manifest ""%DUMMY_MAINTENANCE_BACKUP_MANIFEST%"" >> runtime\autonomy\vacuum_stdout.log 2>&1", 0, True)
WScript.Quit exitCode
