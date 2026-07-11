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

# Register-ScheduledTask needs elevation. -ExecutionPolicy Bypass is NOT
# elevation, so a plain shell fails with Access is denied. Self-elevate via a
# UAC prompt and re-run this exact script; the elevated pass does the work.
$identity = [Security.Principal.WindowsIdentity]::GetCurrent()
$principal = New-Object Security.Principal.WindowsPrincipal($identity)
$isAdmin = $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)
if (-not $isAdmin) {
    Write-Host "Not elevated - relaunching with a UAC prompt..."
    $self = $PSCommandPath
    if (-not $self) { $self = $MyInvocation.MyCommand.Path }
    $host_exe = (Get-Process -Id $PID).Path
    if (-not $host_exe) { $host_exe = "powershell.exe" }
    Start-Process -FilePath $host_exe -Verb RunAs -ArgumentList @(
        "-NoProfile", "-ExecutionPolicy", "Bypass",
        "-File", "`"$self`"", "-TaskName", "`"$TaskName`"", "-Port", "$Port"
    )
    Write-Host "Approve the UAC prompt in the new window; this shell can exit."
    return
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

# Register FIRST. Only after the task exists do we stop the plain server so it
# can rebind the port. A failed registration then never leaves 8787 dead.
Register-ScheduledTask -TaskName $TaskName -Action $action `
    -Trigger $trigger -Settings $settings -Force | Out-Null

$existing = Get-CimInstance Win32_Process -Filter "Name='python.exe'" |
    Where-Object { $_.CommandLine -match "run_dummy_dashboard\.py" }
foreach ($proc in $existing) {
    Write-Host "Stopping existing dashboard process PID $($proc.ProcessId)"
    Stop-Process -Id $proc.ProcessId -Force -Confirm:$false
}

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
