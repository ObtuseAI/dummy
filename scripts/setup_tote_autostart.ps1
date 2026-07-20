# Make Dummy open at logon: the all-in-one launcher (desktop/launch_dummy.py)
# brings up the elevated Dummy Totalizator board as a chromeless app window.
# Runs in the dedicated .dummy-desktop venv via pythonw.exe (no console).
#
# Prefers a scheduled task (fleet-integrated, relaunch-on-crash). Some boxes
# deny programmatic task creation from a normal shell ("Access is denied");
# there we fall back to a Startup-folder shortcut, which needs no elevation and
# is the canonical "run at logon" mechanism. Either way Dummy opens at logon.
# (Remove the Startup shortcut / DummyToteApp task if you don't want it to
# auto-open a window every login -- the desktop launcher still works on demand.)
#
# Rerunnable/idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyToteApp"
$pyw = "C:\Users\$env:USERNAME\.dummy-desktop\venv\Scripts\pythonw.exe"
$entry = "$repo\desktop\launch_dummy.py"
$icon = "$repo\desktop\assets\dummy.ico"

# Drop any older-named Startup shortcut so exactly one autostart entry remains.
$oldLnk = Join-Path ([Environment]::GetFolderPath('Startup')) 'Dummy Tote.lnk'
if (Test-Path $oldLnk) { Remove-Item $oldLnk -Force; Write-Host "removed old Startup shortcut" }

if (-not (Test-Path $pyw)) { throw "tote venv pythonw not found: $pyw (run scripts\setup_dummy_tote.ps1 first)" }
if (-not (Test-Path $entry)) { throw "tote entrypoint not found: $entry" }

$taskOk = $false
try {
    $action = New-ScheduledTaskAction -Execute $pyw -Argument "desktop\launch_dummy.py" -WorkingDirectory $repo
    $trigger = New-ScheduledTaskTrigger -AtLogOn
    $settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
        -DontStopIfGoingOnBatteries -StartWhenAvailable `
        -MultipleInstances IgnoreNew -ExecutionTimeLimit ([TimeSpan]::Zero) `
        -RestartCount 3 -RestartInterval (New-TimeSpan -Minutes 1)
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -User $env:USERNAME -Force -ErrorAction Stop | Out-Null
    Write-Host "REGISTERED $name (AtLogon scheduled task, relaunch-on-crash)"
    $taskOk = $true
} catch {
    Write-Host "task registration blocked ($($_.Exception.Message)) -- using Startup-folder shortcut instead"
}

# Startup-folder shortcut: the always-works fallback (and harmless alongside the
# task -- MultipleInstances=IgnoreNew keeps a single app instance).
if (-not $taskOk) {
    $lnkPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Dummy.lnk'
    $w = New-Object -ComObject WScript.Shell
    $lnk = $w.CreateShortcut($lnkPath)
    $lnk.TargetPath = $pyw
    $lnk.Arguments = "`"$entry`""
    $lnk.WorkingDirectory = $repo
    $lnk.IconLocation = "$icon,0"
    $lnk.Description = "Dummy - trading intelligence board (auto-launch at logon)"
    $lnk.Save()
    Write-Host "STARTUP SHORTCUT -> $lnkPath"
}
