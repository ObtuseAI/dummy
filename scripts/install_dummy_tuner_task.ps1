param(
    [string]$TaskName = "DummyParamTuner",
    [string]$DailyTime = "09:45"
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\python.exe"
$tunerScript = Join-Path $repo "scripts\run_dummy_tuner.py"

if (-not (Test-Path -LiteralPath $tunerScript)) {
    throw "Parameter tuner not found: $tunerScript"
}

# SEPARATE task from DummyStrategyMiner (09:15, chained with the CLV grader),
# not a third sequential action appended to it: the tuner reads the same
# settled-signal ledger but is otherwise independent of the miner's rule
# proposals (no output dependency either way), and the brief's own 09:45 slot
# -- 30 minutes after the miner task's 09:15 -- already gives the miner+
# grader pass room to finish before the tuner's own read-only pass starts.
# Editing the already-shipped install_strategy_miner_task.ps1 to bolt on a
# third action was avoided on purpose: that script/task is out of scope for
# WS-9 and touching it risks an unrelated regression to a task that already
# works. Single action, same schtasks.exe + New-ScheduledTaskAction pattern
# as every other installer in this directory (see install_strategy_miner_task.ps1).
$tunerArguments = "`"$tunerScript`""
$bootstrapAction = "cmd /c cd /d $repo && $python $tunerArguments"

& schtasks.exe /Create /TN $TaskName /TR $bootstrapAction /SC DAILY `
    /ST $DailyTime /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "schtasks.exe failed with exit code $LASTEXITCODE"
}

$tunerAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $tunerArguments `
    -WorkingDirectory $repo
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
Set-ScheduledTask -TaskName $TaskName -Action @($tunerAction) -Settings $settings | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State.ToString()
    NextRunTime = $info.NextRunTime
    Action = "$python $tunerArguments"
    WorkingDirectory = $repo
    Schedule = "DAILY $DailyTime"
    ReadOnlyLedgerAccess = $true
    ProposalArtifactOnly = $true
    WritesNoSourceFiles = $true
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
