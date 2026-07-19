# Wave-33: register DummyHealer -- one windowless self-heal / reconnect pass
# every 5 minutes (probe connectivity, resurrect any dead continuously-running
# task). Fire-and-exit, as the current user, durable settings baked in.
#
# Rerunnable and idempotent. Degrades to DENIED if a prior elevated
# registration blocks in-place modification.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyHealer"
$launcher = "$repo\scripts\tasks\launch_healer.vbs"

if (-not (Test-Path $launcher)) { throw "launcher missing: $launcher" }

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`""
$start = (Get-Date).AddMinutes(1)
$trigger = New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Minutes 5) `
    -RepetitionDuration (New-TimeSpan -Days 3650)
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 4) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 1)

try {
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -User $env:USERNAME -Force -ErrorAction Stop | Out-Null
    Write-Host "REGISTERED $name (every 5 min, windowless, self-heal + connectivity)"
} catch {
    Write-Host "DENIED $name -- rerun as administrator: $($_.Exception.Message)"
}
