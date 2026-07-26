# Install or refresh the single thin Dummy desktop launcher.
#
# The launcher opens the loopback-only board at http://127.0.0.1:8787 in an
# Edge/Chrome app window and starts its read-only notification worker. It uses
# only the standard library: no Android, PySide, Node, or private desktop venv.
#
# Rerunnable and idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$pythonw = "C:\Python314\pythonw.exe"
$entry = "$repo\desktop\launch_dummy.py"
$icon = "$repo\desktop\assets\dummy.ico"

if (-not (Test-Path -LiteralPath $pythonw)) {
    $resolved = Get-Command pythonw.exe -ErrorAction SilentlyContinue
    if ($resolved) { $pythonw = $resolved.Source }
}
if (-not (Test-Path -LiteralPath $pythonw)) {
    throw "pythonw.exe not found; install a supported project Python first"
}
if (-not (Test-Path -LiteralPath $entry)) {
    throw "desktop launcher not found: $entry"
}

$desktop = [Environment]::GetFolderPath("Desktop")
$sh = New-Object -ComObject WScript.Shell

# Remove any older split shortcuts -- exactly one launcher should remain.
foreach ($old in @("Dummy Tote.lnk", "Dummy Dashboard.lnk", "Dummy Operator Control.lnk")) {
    if (Test-Path "$desktop\$old") { Remove-Item "$desktop\$old" -Force; Write-Host "removed old  $old" }
}

# The one launcher -> canonical local web board, branded icon.
$lnk = $sh.CreateShortcut("$desktop\Dummy.lnk")
$lnk.TargetPath = $pythonw
$lnk.Arguments = "`"$entry`""
$lnk.WorkingDirectory = $repo
$lnk.IconLocation = "$icon,0"
$lnk.Description = "Dummy - trading intelligence board"
$lnk.Save()
Write-Host "SHORTCUT  $desktop\Dummy.lnk -> Dummy operator board (icon: dummy.ico)"
Write-Host "Launch now with:  & '$pythonw' '$entry'"
