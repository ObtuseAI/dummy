param(
    [string]$TaskName = "DummyDashboardTailnet"
)

# Registers a user-level task that serves the read-only operator board on this
# node's Tailscale interface (for the native Android app). It never touches the
# admin-owned loopback DummyDashboard task. Runs at logon and stays up; a short
# MINUTE keep-alive relaunches it if the process dies (MultipleInstances
# IgnoreNew means a healthy server is never double-started).

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$launcher = Join-Path $repo "scripts\tasks\launch_dashboard_tailnet.vbs"
if (-not (Test-Path -LiteralPath $launcher)) {
    throw "Tailnet dashboard launcher not found: $launcher"
}

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`""
$logon = New-ScheduledTaskTrigger -AtLogOn
$keepalive = New-ScheduledTaskTrigger -Once -At (Get-Date).AddMinutes(1) `
    -RepetitionInterval (New-TimeSpan -Minutes 5)
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries `
    -ExecutionTimeLimit ([TimeSpan]::Zero)

Register-ScheduledTask -TaskName $TaskName `
    -Action $action -Trigger @($logon, $keepalive) -Settings $settings -Force | Out-Null
Start-ScheduledTask -TaskName $TaskName

$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName      = $TaskName
    State         = (Get-ScheduledTask $TaskName).State.ToString()
    NextRunTime   = $info.NextRunTime
    Binds         = "this node's Tailscale IP :8787 (read-only)"
    LoopbackTask  = "DummyDashboard - untouched"
    Note          = "reachable only over the Tailscale tunnel"
} | Format-List
