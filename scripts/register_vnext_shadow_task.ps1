# Wave-27: register the DummyVnextShadow scheduled task -- one windowless vNext
# shadow-runtime ignition pass every 15 minutes, launched via the hidden VBS
# (wscript, cwd + append-redirect, zero console). Runs as the current user with
# the same fire-and-exit contract as the other Dummy* loops: each fire is a
# fresh process, so merged code and HKCU env activate on the next fire with no
# restart.
#
# Rerunnable and idempotent: re-registers the task in place. Shadow-only by
# construction -- the pass simulates execution, holds no capital or session
# authority, and never changes promotion state (human-only).

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyVnextShadow"
$launcher = "$repo\scripts\tasks\launch_vnext_shadow.vbs"

if (-not (Test-Path $launcher)) { throw "launcher missing: $launcher" }

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`""

# Repeat every 15 minutes, indefinitely. A time-based trigger with a repetition
# pattern; MaxValue is invalid XML on this build, so bound the duration at
# 3650 days (effectively forever for this loop).
$start = (Get-Date).AddMinutes(2)
$trigger = New-ScheduledTaskTrigger -Once -At $start `
    -RepetitionInterval (New-TimeSpan -Minutes 15) `
    -RepetitionDuration (New-TimeSpan -Days 3650)

$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Minutes 10)

try {
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -User $env:USERNAME -Force -ErrorAction Stop | Out-Null
    Write-Host "REGISTERED $name (every 15 min, windowless, as $env:USERNAME)"
} catch {
    # A task previously registered elevated refuses modification from a normal
    # shell. Rerun this script from an elevated PowerShell to finish it.
    Write-Host "DENIED $name -- rerun this script as administrator: $($_.Exception.Message)"
}
