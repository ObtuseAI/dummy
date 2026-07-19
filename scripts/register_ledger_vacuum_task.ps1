# Wave-48: register DummyLedgerVacuum -- the weekly ledger VACUUM that reclaims
# the freed pages the daily prune/retention leave in the freelist and
# defragments the file, so the ledger's disk footprint stays bounded with zero
# human intervention. The script self-skips when the freelist is below its
# threshold, so most weeks this is a no-op with no runtime pause; when it does
# run it briefly pauses the Dummy tasks (~minutes) and always re-enables them.
#
# Weekly, Sunday 03:00 local (a quiet overnight window). Windowless via the VBS
# launcher. Rerunnable/idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyLedgerVacuum"
$launcher = "$repo\scripts\tasks\launch_ledger_vacuum.vbs"

if (-not (Test-Path $launcher)) { throw "launcher missing: $launcher" }

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`""
$trigger = New-ScheduledTaskTrigger -Weekly -DaysOfWeek Sunday -At 3:00AM
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 30)

try {
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -User $env:USERNAME -Force -ErrorAction Stop | Out-Null
    Write-Host "REGISTERED $name (weekly Sun 03:00, windowless, self-skips when little to reclaim)"
} catch {
    Write-Host "DENIED $name -- rerun as administrator: $($_.Exception.Message)"
}
