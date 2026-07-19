# Wave-49: register DummyLogRotation -- the daily runtime-telemetry rotation
# that bounds the process stdout logs and the two verified tail-only tapes
# (cycles.jsonl, live_events.jsonl), so the ledger-hardened stack's on-disk
# footprint stays bounded with zero human intervention. It rewrites only
# over-cap disposable telemetry and leaves all state/audit files alone, so it
# needs no exclusive access and never pauses the runtime.
#
# Daily, 03:30 local (a quiet overnight window, after the weekly 03:00 vacuum).
# Windowless via the VBS launcher. Rerunnable/idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyLogRotation"
$launcher = "$repo\scripts\tasks\launch_log_rotation.vbs"

if (-not (Test-Path $launcher)) { throw "launcher missing: $launcher" }

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`""
$trigger = New-ScheduledTaskTrigger -Daily -At 3:30AM
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

try {
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -User $env:USERNAME -Force -ErrorAction Stop | Out-Null
    Write-Host "REGISTERED $name (daily 03:30, windowless, bounds logs + verified tapes)"
} catch {
    Write-Host "DENIED $name -- rerun as administrator: $($_.Exception.Message)"
}
