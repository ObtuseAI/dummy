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
$action = "cmd /c cd /d $repo && $python $script >> $log 2>&1"

& schtasks.exe /Create /TN $TaskName /TR $action /SC MINUTE `
    /MO ([Math]::Max(5, $IntervalMinutes)) /ST $start /F | Out-Host
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
    CadenceMinutes = [Math]::Max(5, $IntervalMinutes)
    PublicGetOnly = $true
    ChallengerOnly = $true
    RecursiveCodeRewrite = $false
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
