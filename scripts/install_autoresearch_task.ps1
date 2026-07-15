param(
    [string]$TaskName = "DummyAutoresearch",
    [int]$IntervalMinutes = 15,
    [int]$StartDelayMinutes = 5
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\python.exe"
$script = Join-Path $repo "scripts\run_dummy_autoresearch.py"
$log = Join-Path $repo "runtime\autonomy\autoresearch_stdout.log"

if (-not (Test-Path -LiteralPath $script)) {
    throw "Autoresearch runner not found: $script"
}
if (-not (Test-Path -LiteralPath $python)) {
    throw "Python runtime not found: $python"
}

$start = (Get-Date).AddMinutes([Math]::Max(1, $StartDelayMinutes)).ToString("HH:mm")
$action = "cmd /c cd /d $repo && $python $script >> $log 2>&1"

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
    CandidateAuthority = "proposal-and-shadow-evaluation-only"
    ExecutionAuthority = $false
    BrokerContact = $false
    LedgerAccess = "read-only"
}
