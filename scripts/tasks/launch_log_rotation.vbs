' Hidden launcher (Wave-49): the daily runtime-telemetry rotation -- bound the
' process stdout logs and the two verified tail-only tapes (cycles.jsonl,
' live_events.jsonl) so disk footprint stays bounded with zero intervention.
' Rewrites only over-cap disposable telemetry; never touches organism state,
' open positions, the audit trail, or the CLV order-book tape. No console
' window. Regular python.exe so stdout redirects to the log (which this task
' also bounds, skipping the currently-open file).
Set shell = CreateObject("WScript.Shell")
shell.CurrentDirectory = "C:\src\engine\dummy"
shell.Run "cmd /c C:\Python314\python.exe scripts\run_dummy_log_rotation.py >> runtime\autonomy\log_rotation_stdout.log 2>&1", 0, False
