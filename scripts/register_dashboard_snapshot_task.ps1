# Wave-42: register DummyDashboardSnapshot -- the loop that keeps the web
# dashboard off the live ledger. It rebuilds runtime\autonomy\latest_dashboard_
# snapshot.json (ledger summaries every run; full backtest only when the prior
# one ages past the bound) so the dashboard reads an artifact instead of holding
# a SHARED lock on the ledger for a minutes-long scan -- the root of the chronic
# "database is locked" contention with the shadow brain.
#
# Every 20 min; windowless via the VBS launcher. Rerunnable/idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyDashboardSnapshot"
$launcher = "$repo\scripts\tasks\launch_dashboard_snapshot.vbs"

if (-not (Test-Path $launcher)) { throw "launcher missing: $launcher" }

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`""
$trigger = New-ScheduledTaskTrigger -Once -At (Get-Date) `
    -RepetitionInterval (New-TimeSpan -Minutes 20) -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 5)

try {
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -User $env:USERNAME -Force -ErrorAction Stop | Out-Null
    Write-Host "REGISTERED $name (every 20 min, windowless, light refresh)"
} catch {
    Write-Host "DENIED $name -- rerun as administrator: $($_.Exception.Message)"
}
