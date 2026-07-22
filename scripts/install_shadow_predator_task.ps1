param(
    [string]$TaskName = "DummyShadowPredator",
    [int]$IntervalMinutes = 10,
    [int]$StartDelayMinutes = 1,
    [int]$ExecutionTimeLimitMinutes = 15
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$launcher = Join-Path $repo "scripts\tasks\launch_shadow_predator.vbs"

if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Shadow predator launcher not found: $launcher"
}

$start = (Get-Date).AddMinutes([Math]::Max(1, $StartDelayMinutes)).ToString("HH:mm")
$cadence = [Math]::Max(5, $IntervalMinutes)
$timeoutMinutes = [Math]::Max($cadence, $ExecutionTimeLimitMinutes)
$arguments = "`"$launcher`""

& schtasks.exe /Create /TN $TaskName /TR "wscript.exe $arguments" /SC MINUTE `
    /MO $cadence /ST $start /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "schtasks.exe failed with exit code $LASTEXITCODE"
}

$taskAction = New-ScheduledTaskAction `
    -Execute "wscript.exe" `
    -Argument $arguments
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
    Action = "wscript.exe $arguments"
    CadenceMinutes = $cadence
    ExecutionTimeLimitMinutes = $timeoutMinutes
    WaitsForChild = $true
    PropagatesChildExitCode = $true
    MultipleInstances = $task.Settings.MultipleInstances.ToString()
    ShadowOnly = $true
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
