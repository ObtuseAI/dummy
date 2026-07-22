param(
    [string]$TaskName = "DummySportsBoardRefresh",
    [int]$IntervalMinutes = 5,
    # Keep the board one minute behind the authoritative seed producer so a
    # scheduled refresh cannot bind yesterday's/previous-cycle seed while a
    # new seed is being published in the same minute.
    [int]$StartDelayMinutes = 2,
    [int]$TimeoutMinutes = 2
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\pythonw.exe"
$script = Join-Path $repo "scripts\run_sports_board_refresh.py"

if (-not (Test-Path -LiteralPath $script)) {
    throw "Sports board refresher not found: $script"
}

$start = (Get-Date).AddMinutes([Math]::Max(1, $StartDelayMinutes)).ToString("HH:mm")
$cadence = [Math]::Max(5, $IntervalMinutes)
$timeout = [Math]::Max(2, $TimeoutMinutes)
$arguments = "`"$script`""
$bootstrapAction = "cmd /c cd /d $repo && $python $arguments"

& schtasks.exe /Create /TN $TaskName /TR $bootstrapAction /SC MINUTE `
    /MO $cadence /ST $start /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "schtasks.exe failed with exit code $LASTEXITCODE"
}

$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $arguments `
    -WorkingDirectory $repo
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes $timeout) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
Set-ScheduledTask -TaskName $TaskName -Action $action -Settings $settings | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State.ToString()
    NextRunTime = $info.NextRunTime
    Action = "$python $arguments"
    WorkingDirectory = $repo
    CadenceMinutes = $cadence
    ExecutionTimeLimitMinutes = $timeout
    MultipleInstances = "IgnoreNew"
    PublicGetOnly = $true
    NoLedgerReads = $true
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
