param(
    [string]$TaskName = "DummySimulationTrainer",
    [int]$IntervalMinutes = 60,
    [int]$StartDelayMinutes = 5
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\python.exe"
$script = Join-Path $repo "scripts\run_dummy_simulation_training.py"
$log = Join-Path $repo "runtime\autonomy\simulation_training_stdout.log"

if (-not (Test-Path -LiteralPath $script)) {
    throw "Simulation trainer not found: $script"
}

$start = (Get-Date).AddMinutes([Math]::Max(1, $StartDelayMinutes)).ToString("HH:mm")
$action = "cmd /c cd /d $repo && $python $script --summary >> $log 2>&1"

& schtasks.exe /Create /TN $TaskName /TR $action /SC MINUTE `
    /MO ([Math]::Max(15, $IntervalMinutes)) /ST $start /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "schtasks.exe failed with exit code $LASTEXITCODE"
}

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State.ToString()
    NextRunTime = $info.NextRunTime
    Action = $action
    ExecutionAuthority = $false
    LedgerAccess = "read-only"
}
