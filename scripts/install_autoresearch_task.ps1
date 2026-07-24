param(
    [string]$TaskName = "DummyAutoresearch",
    [int]$IntervalMinutes = 60,
    [int]$StartDelayMinutes = 5,
    [int]$MaxSeconds = 600
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\python.exe"
$script = Join-Path $repo "scripts\run_dummy_autoresearch.py"
# Health is read from the status artifact, not a stdout tail: the runner
# records status, duration, last_success_at, and the error/traceback tail
# there on every run. (The previous installer redirected stdout to a log the
# registered action never actually wrote to.)
$status = Join-Path $repo "runtime\autonomy\autoresearch_status.json"

if (-not (Test-Path -LiteralPath $script)) {
    throw "Autoresearch runner not found: $script"
}
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python runtime not found: $python"
}

# Bounded real-ledger research cycle. A measured full run over the live
# 15.9GB ledger is ~34s (13.5k evidence rows, 14 cohort campaigns), so an
# hourly cadence leaves the slot ~99% idle; the runner is read-only over
# ledger.db, makes no network calls, and spends nothing. The runner's own
# --max-seconds deadline stops scheduling new cohorts, and ExecutionTimeLimit
# below is the hard backstop. MultipleInstances IgnoreNew means a slow run is
# never overlapped by the next fire.
$start = (Get-Date).AddMinutes([Math]::Max(1, $StartDelayMinutes)).ToString("HH:mm")
$cadence = [Math]::Max(15, $IntervalMinutes)
$deadlineSeconds = [Math]::Max(60, $MaxSeconds)
# Hard limit stays above the cooperative deadline so the runner gets the
# chance to finish and write its status artifact before the scheduler kills it.
$timeoutMinutes = [Math]::Max(5, [int][Math]::Ceiling($deadlineSeconds / 60.0) + 5)
$arguments = "`"$script`" --max-seconds $deadlineSeconds"
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
    CooperativeDeadlineSeconds = $deadlineSeconds
    ExecutionTimeLimitMinutes = $timeoutMinutes
    StatusArtifact = $status
    LedgerAccess = "read-only"
    NetworkCalls = $false
    CandidateAuthority = "proposal-and-shadow-evaluation-only"
    AutomaticPromotion = $false
    ExecutionAuthority = $false
    CapitalAuthority = $false
    BrokerContact = $false
}
