# Creates a "Dummy Operator Control" desktop shortcut that runs the launcher.
[CmdletBinding(SupportsShouldProcess=$true)]
param(
    [string]$ShortcutName = "Dummy Operator Control",
    [string]$RepoRoot = "C:\src\engine\dummy",
    [string]$LauncherRel = "scripts\launch_dummy_operator_control.ps1"
)

$ErrorActionPreference = "Stop"

$Desktop = [Environment]::GetFolderPath("Desktop")
if (-not $Desktop -or -not (Test-Path -LiteralPath $Desktop)) {
    Write-Error "Could not resolve Desktop folder. Manual creation required (see message)."
    Write-Host "Manual command:"
    Write-Host "  powershell -NoProfile -ExecutionPolicy Bypass -File `"$RepoRoot\$LauncherRel`""
    exit 1
}

$Launcher = Join-Path $RepoRoot $LauncherRel
if (-not (Test-Path -LiteralPath $Launcher)) {
    Write-Error "Launcher not found: $Launcher"
    exit 1
}

$Lnk = Join-Path $Desktop "$ShortcutName.lnk"

if ($PSCmdlet.ShouldProcess($Lnk, "Create shortcut")) {
    $ws = New-Object -ComObject WScript.Shell
    $s = $ws.CreateShortcut($Lnk)
    $s.TargetPath = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe"
    $s.Arguments = "-NoProfile -ExecutionPolicy Bypass -File `"$Launcher`""
    $s.WorkingDirectory = $RepoRoot
    $s.WindowStyle = 1
    $s.Description = "Launch Dummy Operator Control dashboard"
    $s.IconLocation = "$env:SystemRoot\System32\WindowsPowerShell\v1.0\powershell.exe,0"
    $s.Save()
    Write-Host "Created shortcut: $Lnk" -ForegroundColor Green
} else {
    Write-Host "WhatIf: would create $Lnk" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "Target:  powershell -NoProfile -ExecutionPolicy Bypass -File `"$Launcher`""
Write-Host "StartIn: $RepoRoot"
Write-Host "No admin required. Shortcut does not run live proof or broker commands."
