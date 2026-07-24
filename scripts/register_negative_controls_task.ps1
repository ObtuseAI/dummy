# Wave-84: register DummyNegativeControls -- the falsification battery on the
# BACKTEST cadence. The 2026-07-24 audit found the battery CLEAN but ~40h stale
# because its only home was the nightly self-improvement chain, while the
# backtest that produces the evidence it grades refreshes every 6h
# (autonomy/daemon.py RECAL_INTERVAL_HOURS, the DummyWeightsRecal task). Stale
# controls mean the fabrication tripwires and the NO_EDGE_MAP that feeds the
# fusion floor are a day-and-a-half behind the weights they are supposed to
# police.
#
# This does NOT remove the step from the nightly chain (scripts/
# run_dummy_self_improvement.py) -- coverage is added, never moved. The runner
# self-skips when the report on disk is younger than its rerun guard (half the
# cadence), so the two callers can never run the same battery twice in a row.
#
# Every 6h, windowless via the VBS launcher. Read-only against the ledger.
# Rerunnable/idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyNegativeControls"
$launcher = "$repo\scripts\tasks\launch_negative_controls.vbs"

if (-not (Test-Path $launcher)) { throw "launcher missing: $launcher" }

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 6) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

try {
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -User $env:USERNAME -Force -ErrorAction Stop | Out-Null
    Write-Host "REGISTERED $name (every 6h = backtest cadence, windowless, read-only)"
} catch {
    Write-Host "DENIED $name -- rerun as administrator: $($_.Exception.Message)"
}
