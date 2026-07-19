# Wave-54: make the native Dummy Tote desktop app (PySide6) launch at logon,
# always. Runs in the dedicated .dummy-desktop venv via pythonw.exe (no console;
# the Qt window is the UI).
#
# Prefers a scheduled task (fleet-integrated, relaunch-on-crash). Some boxes
# deny programmatic task creation from a normal shell ("Access is denied");
# there we fall back to a Startup-folder shortcut, which needs no elevation and
# is the canonical "run at logon" mechanism. Either way the app starts at logon.
#
# Rerunnable/idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyToteApp"
$pyw = "C:\Users\$env:USERNAME\.dummy-desktop\venv\Scripts\pythonw.exe"
$entry = "$repo\desktop\run_dummy_tote.py"

if (-not (Test-Path $pyw)) { throw "tote venv pythonw not found: $pyw (run scripts\setup_dummy_tote.ps1 first)" }
if (-not (Test-Path $entry)) { throw "tote entrypoint not found: $entry" }

$taskOk = $false
try {
    $action = New-ScheduledTaskAction -Execute $pyw -Argument "desktop\run_dummy_tote.py" -WorkingDirectory $repo
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
    $lnkPath = Join-Path ([Environment]::GetFolderPath('Startup')) 'Dummy Tote.lnk'
    $w = New-Object -ComObject WScript.Shell
    $lnk = $w.CreateShortcut($lnkPath)
    $lnk.TargetPath = $pyw
    $lnk.Arguments = "`"$entry`""
    $lnk.WorkingDirectory = $repo
    $lnk.Description = "Dummy Tote native desktop app (auto-launch at logon)"
    $lnk.Save()
    Write-Host "STARTUP SHORTCUT -> $lnkPath"
}
