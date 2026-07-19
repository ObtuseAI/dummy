# Wave-39: install/refresh the Dummy Tote native desktop app.
#
# Creates an isolated venv (so the trading interpreter stays clean), installs
# PySide6 + pyqtgraph (abi3 wheels -- work on Python 3.14), and drops a desktop
# shortcut that launches the native window with pythonw (no console). The app
# reads only the runtime artifacts, so it needs none of dummy's own deps.
#
# Rerunnable and idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$venv = "C:\Users\$env:USERNAME\.dummy-desktop\venv"
$py = "C:\Python314\python.exe"
$pythonw = "$venv\Scripts\pythonw.exe"

if (-not (Test-Path "$venv\Scripts\python.exe")) {
    Write-Host "Creating venv at $venv ..."
    & $py -m venv $venv
}
Write-Host "Installing PySide6 + pyqtgraph (abi3 wheels) ..."
& "$venv\Scripts\python.exe" -m pip install --quiet --upgrade --only-binary=:all: PySide6 pyqtgraph
& "$venv\Scripts\python.exe" -c "import PySide6; print('PySide6', PySide6.__version__, 'ready')"

# Desktop shortcut -> native app window.
$desktop = [Environment]::GetFolderPath("Desktop")
$lnk = (New-Object -ComObject WScript.Shell).CreateShortcut("$desktop\Dummy Tote.lnk")
$lnk.TargetPath = $pythonw
$lnk.Arguments = "`"$repo\desktop\run_dummy_tote.py`""
$lnk.WorkingDirectory = $repo
$lnk.IconLocation = "$pythonw,0"
$lnk.Description = "Dummy Tote - native evidence board"
$lnk.Save()
Write-Host "SHORTCUT  $desktop\Dummy Tote.lnk -> native app"
Write-Host "Launch now with:  & '$pythonw' '$repo\desktop\run_dummy_tote.py'"
