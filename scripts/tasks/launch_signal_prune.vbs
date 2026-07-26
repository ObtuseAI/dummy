' Hidden launcher (Wave-46b): daily prune of redundant intra-market signal
' re-pricings for markets settled more than 2 days ago (keeps a 2-day trajectory
' window). Bounds the ledger's row count so every scan stays fast. Only deletes
' when DUMMY_SIGNAL_PRUNE_ENABLED=1 -- the script self-gates -- otherwise it is a
' harmless dry run. Weight-neutral (kept id == the backtester-selected id). No
' console window. The child is supervised and its real exit code is propagated.
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
exitCode = shell.Run("cmd /c C:\Python314\python.exe scripts\run_dummy_signal_prune.py --apply --settled-before-days 2 >> runtime\autonomy\signal_prune_stdout.log 2>&1", 0, True)
WScript.Quit exitCode
