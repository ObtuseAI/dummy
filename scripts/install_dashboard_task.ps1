param(
    [string]$TaskName = "DummyDashboard",
    [int]$Port = 8787
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\python.exe"
$script = Join-Path $repo "scripts\run_dummy_dashboard.py"

if (-not (Test-Path -LiteralPath $script)) {
    throw "Dashboard server not found: $script"
}

# Stop any plain (non-task) dashboard process so the task can bind the port.
$existing = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "run_dummy_dashboard\.py" }
foreach ($proc in $existing) {
    Write-Host "Stopping existing dashboard process PID $($proc.ProcessId)"
    Stop-Process -Id $proc.ProcessId -Force -Confirm:$false
}

$arguments = "`"$script`" --port $Port"
$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $arguments `
    -WorkingDirectory $repo
$trigger = New-ScheduledTaskTrigger -AtLogOn
# A long-running local server: no execution time limit, restart on failure.
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Seconds 0) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -RestartCount 3 `
    -RestartInterval (New-TimeSpan -Minutes 1)
Register-ScheduledTask -TaskName $TaskName -Action $action `
    -Trigger $trigger -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State.ToString()
    NextRunTime = $info.NextRunTime
    Action = "$python $arguments"
    WorkingDirectory = $repo
    Url = "http://127.0.0.1:$Port/"
    LoopbackOnly = $true
    ReadOnlyEvidenceView = $true
    ControlScope = "paper_scheduler_only"
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
