# Install/refresh the Dummy desktop app + its ONE all-in-one launcher.
#
# Creates an isolated venv (so the trading interpreter stays clean), installs
# PySide6 + pyqtgraph (abi3 wheels -- work on Python 3.14), and drops a SINGLE
# branded desktop shortcut ("Dummy") that launches the native window with
# pythonw (no console). The app reads only the runtime artifacts, so it needs
# none of dummy's own deps. Any older split shortcuts are removed so exactly one
# launcher remains.
#
# Rerunnable and idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$venv = "C:\Users\$env:USERNAME\.dummy-desktop\venv"
$py = "C:\Python314\python.exe"
$pythonw = "$venv\Scripts\pythonw.exe"
$entry = "$repo\desktop\run_dummy_tote.py"
$icon = "$repo\desktop\assets\dummy.ico"

if (-not (Test-Path "$venv\Scripts\python.exe")) {
    Write-Host "Creating venv at $venv ..."
    & $py -m venv $venv
}
Write-Host "Installing PySide6 + pyqtgraph (abi3 wheels) ..."
& "$venv\Scripts\python.exe" -m pip install --quiet --upgrade --only-binary=:all: PySide6 pyqtgraph
& "$venv\Scripts\python.exe" -c "import PySide6; print('PySide6', PySide6.__version__, 'ready')"

$desktop = [Environment]::GetFolderPath("Desktop")
$sh = New-Object -ComObject WScript.Shell

# Remove any older split shortcuts -- exactly one launcher should remain.
foreach ($old in @("Dummy Tote.lnk", "Dummy Dashboard.lnk", "Dummy Operator Control.lnk")) {
    if (Test-Path "$desktop\$old") { Remove-Item "$desktop\$old" -Force; Write-Host "removed old  $old" }
}

# The one all-in-one launcher -> native app window, branded icon.
$lnk = $sh.CreateShortcut("$desktop\Dummy.lnk")
$lnk.TargetPath = $pythonw
$lnk.Arguments = "`"$entry`""
$lnk.WorkingDirectory = $repo
$lnk.IconLocation = "$icon,0"
$lnk.Description = "Dummy - trading intelligence board"
$lnk.Save()
Write-Host "SHORTCUT  $desktop\Dummy.lnk -> native app (icon: dummy.ico)"
Write-Host "Launch now with:  & '$pythonw' '$entry'"
