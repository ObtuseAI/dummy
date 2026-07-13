param(
    [string]$TaskName = "DummyStrategyMiner",
    [string]$DailyTime = "09:15"
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\python.exe"
$minerScript = Join-Path $repo "scripts\run_dummy_strategy_miner.py"
$graderScript = Join-Path $repo "scripts\run_dummy_clv_grader.py"
$lossEngineScript = Join-Path $repo "scripts\run_dummy_loss_engine.py"

if (-not (Test-Path -LiteralPath $minerScript)) {
    throw "Strategy miner not found: $minerScript"
}
if (-not (Test-Path -LiteralPath $graderScript)) {
    throw "CLV grader not found: $graderScript"
}
if (-not (Test-Path -LiteralPath $lossEngineScript)) {
    throw "Loss engine not found: $lossEngineScript"
}

# Nightly pass after the overnight settlement sweep. Three sequential task
# actions in ONE task so the CLV grader and the loss engine run right after
# the strategy miner:
#   1. strategy miner  -> mines the day's settled signal history into a
#      proposal artifact (reads the ledger).
#   2. CLV grader (WS-8) -> grades the day's persisted paper entries against
#      the de-vigged closing line into runtime/autonomy/clv_report.json (reads
#      the book-tape / paper-entry JSONL the mispricing monitor persists).
#   3. loss engine (WS-B, Phenon Harness) -> deconstructs where the system
#      loses to the market into runtime/autonomy/loss_attribution.json (an
#      optional, fail-closed LLM narration pass over that artifact), which
#      the tuner's priority read and the dashboard/readiness "where we bleed"
#      line then consume.
# All three read-only; propose / grade / attribute, never act. CLV and loss
# attribution are evidence for review, not a promotion gate (contested Brier
# stays the gate).
$minerArguments = "`"$minerScript`""
$graderArguments = "`"$graderScript`""
$lossEngineArguments = "`"$lossEngineScript`""
$bootstrapAction = (
    "cmd /c cd /d $repo && $python $minerArguments && $python $graderArguments" +
    " && $python $lossEngineArguments"
)

& schtasks.exe /Create /TN $TaskName /TR $bootstrapAction /SC DAILY `
    /ST $DailyTime /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "schtasks.exe failed with exit code $LASTEXITCODE"
}

$minerAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $minerArguments `
    -WorkingDirectory $repo
$graderAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $graderArguments `
    -WorkingDirectory $repo
$lossEngineAction = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $lossEngineArguments `
    -WorkingDirectory $repo
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes 30) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
# Task Scheduler runs multiple actions sequentially in array order -> miner
# first, then grader, then the loss engine.
Set-ScheduledTask -TaskName $TaskName `
    -Action @($minerAction, $graderAction, $lossEngineAction) -Settings $settings | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State.ToString()
    NextRunTime = $info.NextRunTime
    Action = "$python $minerArguments; then $python $graderArguments; then $python $lossEngineArguments"
    WorkingDirectory = $repo
    Schedule = "DAILY $DailyTime"
    ReadOnlyLedgerAccess = $true
    ProposalArtifactOnly = $true
    ClvGraderChained = $true
    LossEngineChained = $true
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
