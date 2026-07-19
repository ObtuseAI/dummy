# Wave-46b: register DummyLedgerPrune -- the daily prune that keeps the ledger's
# row count bounded so scans (recal, diagnostics, cycle) stay fast. It deletes
# the redundant intra-market signal re-pricings for markets settled more than 2
# days ago, keeping exactly the one the backtester selects per (source, market)
# -- so it is weight-neutral (proven by test + re-checked live each run). Keeps a
# 2-day trajectory window for any in-flight analysis.
#
# Only deletes when DUMMY_SIGNAL_PRUNE_ENABLED=1 (the script self-gates); until
# then it is a harmless daily dry run. Daily, windowless. Rerunnable/idempotent.

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$name = "DummyLedgerPrune"
$launcher = "$repo\scripts\tasks\launch_signal_prune.vbs"

if (-not (Test-Path $launcher)) { throw "launcher missing: $launcher" }

$action = New-ScheduledTaskAction -Execute "wscript.exe" -Argument "`"$launcher`""
# 08:40 local daily -- just after the ledger-retention pass (08:10).
$trigger = New-ScheduledTaskTrigger -Daily -At 8:40AM
$settings = New-ScheduledTaskSettingsSet -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries -StartWhenAvailable `
    -MultipleInstances IgnoreNew -ExecutionTimeLimit (New-TimeSpan -Hours 2) `
    -RestartCount 2 -RestartInterval (New-TimeSpan -Minutes 10)

try {
    Register-ScheduledTask -TaskName $name -Action $action -Trigger $trigger `
        -Settings $settings -User $env:USERNAME -Force -ErrorAction Stop | Out-Null
    Write-Host "REGISTERED $name (daily 08:40, windowless; deletes only when DUMMY_SIGNAL_PRUNE_ENABLED=1)"
} catch {
    Write-Host "DENIED $name -- rerun as administrator: $($_.Exception.Message)"
}
