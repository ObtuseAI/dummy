# Wave-44: register DummyBacktestReport -- the heavy backtest diagnostics, split
# out of the 6-hourly weight recalibration. The recal now refreshes weights only
# (fast, non-blocking); this task runs the full backtest's ~11 full-ledger-scan
# sub-reports and writes the summary / self-improvement / dashboard-snapshot the
# dashboard + readiness surfaces read.
#
# Every 12h (safely under the summary's 24h freshness bound), windowless.
# Rerunnable/idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyBacktestReport"
$launcher = "$repo\scripts\tasks\launch_backtest_report.vbs"

if (-not (Test-Path $launcher)) { throw "launcher missing: $launcher" }

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Hours 12) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

try {
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -User $env:USERNAME -Force -ErrorAction Stop | Out-Null
    Write-Host "REGISTERED $name (every 12h, windowless, diagnostics report)"
} catch {
    Write-Host "DENIED $name -- rerun as administrator: $($_.Exception.Message)"
}
