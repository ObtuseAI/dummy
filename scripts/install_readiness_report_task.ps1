param(
    [string]$TaskName = "DummyReadinessReport",
    [string]$DailyTime = "09:30"
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\python.exe"
$script = Join-Path $repo "scripts\run_dummy_readiness_report.py"

if (-not (Test-Path -LiteralPath $script)) {
    throw "Readiness report runner not found: $script"
}

# Nightly, just after the strategy miner (09:15) so both read the same settled
# history. Read-only; proposes promotions and writes auto-demotions only.
$arguments = "`"$script`""
$bootstrapAction = "cmd /c cd /d $repo && $python $arguments"

& schtasks.exe /Create /TN $TaskName /TR $bootstrapAction /SC DAILY `
    /ST $DailyTime /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "schtasks.exe failed with exit code $LASTEXITCODE"
}

$taskAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $arguments `
    -WorkingDirectory $repo
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
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
    Schedule = "DAILY $DailyTime"
    ReadOnlyLedgerAccess = $true
    PromotionAuthority = "human-only (promotions.json)"
    WritesAutoDemotionsOnly = $true
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
