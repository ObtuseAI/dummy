param(
    [string]$TaskName = "DummyMispricingMonitor",
    [int]$IntervalMinutes = 5,
    [int]$StartDelayMinutes = 1,
    [int]$LiveBurstSeconds = 0,
    [int]$TimeoutMinutes = 10
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\python.exe"
$script = Join-Path $repo "scripts\run_dummy_mispricing_monitor.py"

if (-not (Test-Path -LiteralPath $script)) {
    throw "Mispricing monitor not found: $script"
}

# The current public universe takes roughly 3-4 minutes for a cold full sweep.
# A 2-minute timeout killed every run before it could publish an artifact.
# Five minutes plus IgnoreNew keeps one bounded worker alive without overlap;
# the 10-minute ceiling still terminates a genuinely wedged source call.  The
# scheduled default omits the optional live burst because a cold burst can run
# past its wall-clock budget; the dedicated live poller already captures those
# public events, and operators can still opt in explicitly for diagnostics.
$start = (Get-Date).AddMinutes([Math]::Max(1, $StartDelayMinutes)).ToString("HH:mm")
$cadence = [Math]::Max(5, $IntervalMinutes)
$timeoutMinutes = [Math]::Max($cadence + 2, $TimeoutMinutes)
$burstSeconds = [Math]::Max(0, $LiveBurstSeconds)
$arguments = "`"$script`" --live-burst-seconds $burstSeconds"
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
    LiveBurstSeconds = $burstSeconds
    PublicGetOnly = $true
    IndependentOfShadowOrLiveSession = $true
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
