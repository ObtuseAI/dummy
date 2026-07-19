' Hidden launcher (Wave-48): weekly ledger VACUUM maintenance. The script skips
' itself cheaply when the freelist is small (no runtime pause); when there is
' enough to reclaim it briefly pauses the Dummy tasks, VACUUMs the ledger, and
' re-enables them. No console window.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
shell.Run "cmd /c powershell -ExecutionPolicy Bypass -File scripts\run_dummy_ledger_vacuum.ps1 >> runtime\autonomy\vacuum_stdout.log 2>&1", 0, False
