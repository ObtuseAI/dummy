param(
    [string]$TaskName = "DummyWatchdog",
    [int]$IntervalMinutes = 5,
    [int]$StartDelayMinutes = 2
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\python.exe"
$script = Join-Path $repo "scripts\run_dummy_watchdog.py"

if (-not (Test-Path -LiteralPath $script)) {
    throw "Watchdog runner not found: $script"
}

# Aggregate fleet monitor. A 5-minute cadence is tighter than every watched
# task's own stale threshold (the fastest, the mispricing monitor, goes stale
# at 4 minutes) so a dead task is surfaced within one watchdog interval. The
# watchdog is read-only over the runtime tree; it never opens ledger.db and
# never controls a scheduled task.
$start = (Get-Date).AddMinutes([Math]::Max(1, $StartDelayMinutes)).ToString("HH:mm")
$cadence = [Math]::Max(1, $IntervalMinutes)
$timeoutMinutes = [Math]::Max(1, $cadence)
$arguments = "`"$script`""
$bootstrapAction = "cmd /c cd /d $repo && $python $arguments"

& schtasks.exe /Create /TN $TaskName /TR $bootstrapAction /SC MINUTE `
    /MO $cadence /ST $start /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "schtasks.exe failed with exit code $LASTEXITCODE"
}

$taskAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $arguments `
    -WorkingDirectory $repo
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes $timeoutMinutes) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
Set-ScheduledTask -TaskName $TaskName -Action $taskAction -Settings $settings | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State.ToString()
    NextRunTime = $info.NextRunTime
    Action = "$python $arguments"
    WorkingDirectory = $repo
    CadenceMinutes = $cadence
    ExecutionTimeLimitMinutes = $timeoutMinutes
    ReadOnlyRuntimeAccess = $true
    OpensLedgerDb = $false
    ControlsScheduledTasks = $false
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
