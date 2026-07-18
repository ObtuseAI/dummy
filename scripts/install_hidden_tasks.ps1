# Wave-15: make every Dummy* scheduled task run WITHOUT a console window.
#
# The loops fire every few minutes as interactive tasks, so each fire popped a
# terminal over whatever the operator was doing. This retargets, idempotently:
#   * plain `python.exe <script> ...` actions      -> pythonw.exe (windowless;
#     these scripts log via --log flags or not at all, so no output is lost)
#   * the two `cmd /c ... >> log 2>&1` actions     -> wscript.exe + the
#     matching hidden .vbs launcher in scripts\tasks\ (cwd + append-redirect
#     preserved, zero window)
# It also drops a desktop shortcut that opens the dashboard as an app window
# (Edge --app mode): the operator-facing surface without a browser chrome.
#
# Rerunnable any time; prints what it changed. Triggers, schedules, and the
# running user are untouched.

$ErrorActionPreference = "Stop"
$python = "C:\Python314\python.exe"
$pythonw = "C:\Python314\pythonw.exe"
$repo = "C:\src\engine\dummy"

if (-not (Test-Path $pythonw)) { throw "pythonw.exe not found at $pythonw" }

$vbs = @{
    "DummyShadowPredator"   = "$repo\scripts\tasks\launch_shadow_predator.vbs"
    "DummySimulationTrainer" = "$repo\scripts\tasks\launch_simulation_trainer.vbs"
}

foreach ($task in Get-ScheduledTask -TaskName "Dummy*") {
    $action = $task.Actions[0]
    $name = $task.TaskName
    if ($vbs.ContainsKey($name)) {
        $target = $vbs[$name]
        if (-not (Test-Path $target)) { Write-Host "SKIP $name (launcher missing: $target)"; continue }
        if ($action.Execute -eq "wscript.exe" -and $action.Arguments -eq "`"$target`"") {
            Write-Host "OK   $name (already hidden)"; continue
        }
        $new = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$target`""
    }
    elseif ($action.Execute -ieq $python) {
        $new = New-ScheduledTaskAction -Execute $pythonw -Argument $action.Arguments `
            -WorkingDirectory $action.WorkingDirectory
    }
    elseif ($action.Execute -ieq $pythonw) {
        Write-Host "OK   $name (already hidden)"; continue
    }
    else {
        Write-Host "SKIP $name (unrecognized action: $($action.Execute))"; continue
    }
    Set-ScheduledTask -TaskName $name -Action $new | Out-Null
    Write-Host "HID  $name"
}

# Desktop shortcut: dashboard as an app window.
$edge = "${env:ProgramFiles(x86)}\Microsoft\Edge\Application\msedge.exe"
if (-not (Test-Path $edge)) { $edge = "$env:ProgramFiles\Microsoft\Edge\Application\msedge.exe" }
if (Test-Path $edge) {
    $desktop = [Environment]::GetFolderPath("Desktop")
    $lnk = (New-Object -ComObject WScript.Shell).CreateShortcut("$desktop\Dummy Dashboard.lnk")
    $lnk.TargetPath = $edge
    $lnk.Arguments = "--app=http://127.0.0.1:8787/"
    $lnk.Description = "Dummy predator dashboard (app window)"
    $lnk.Save()
    Write-Host "SHORTCUT Dummy Dashboard.lnk -> app window at 127.0.0.1:8787"
} else {
    Write-Host "SKIP shortcut (Edge not found)"
}
