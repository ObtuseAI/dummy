param(
    [string]$TaskName = "DummySportsSimulation",
    [int]$IntervalMinutes = 10,
    [int]$StartDelayMinutes = 1
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\python.exe"
$script = Join-Path $repo "scripts\run_dummy_sports_simulation.py"
$log = Join-Path $repo "runtime\autonomy\sports_simulation_stdout.log"

if (-not (Test-Path -LiteralPath $script)) {
    throw "Sports simulation runner not found: $script"
}

$start = (Get-Date).AddMinutes([Math]::Max(1, $StartDelayMinutes)).ToString("HH:mm")
$cadence = [Math]::Max(5, $IntervalMinutes)
$timeoutMinutes = [Math]::Max(1, $cadence - 1)
$lockStaleSeconds = $timeoutMinutes * 60
$arguments = "`"$script`" --log `"$log`" --lock-stale-seconds $lockStaleSeconds"
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
    LockStaleSeconds = $lockStaleSeconds
    StartWhenAvailable = $task.Settings.StartWhenAvailable
    MultipleInstances = $task.Settings.MultipleInstances.ToString()
    RotatingLog = $log
    PublicGetOnly = $true
    ChallengerOnly = $true
    RecursiveCodeRewrite = $false
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
