# Wave-41: register DummyLedgerRetention -- the daily archive pass the system
# was designed to have but never got. It moves settled rows older than the
# retention window from the hot ledger into the companion archive DB
# (atomically, which is why the ledger stays non-WAL), keeping the hot ledger
# bounded so reads stay fast and the "database is locked" contention shrinks.
#
# Daily; NO vacuum (that needs an exclusive lock -- a rare maintenance op, not
# a recurring task). Windowless via the VBS launcher. Rerunnable/idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyLedgerRetention"
$launcher = "$repo\scripts\tasks\launch_ledger_retention.vbs"

if (-not (Test-Path $launcher)) { throw "launcher missing: $launcher" }

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`""
# 08:10 local daily -- a lighter window, after the overnight halt cycles.
$trigger = New-ScheduledTaskTrigger -Daily -At 8:10AM
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

try {
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -User $env:USERNAME -Force -ErrorAction Stop | Out-Null
    Write-Host "REGISTERED $name (daily 08:10, windowless, archive-only)"
} catch {
    Write-Host "DENIED $name -- rerun as administrator: $($_.Exception.Message)"
}
