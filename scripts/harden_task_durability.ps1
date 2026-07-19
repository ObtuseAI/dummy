# Wave-33: make every Dummy* scheduled task durable through crashes, power
# loss, sleep, and network blips -- WITHOUT touching credentials.
#
# For each task, preserving its existing triggers/action/principal and its
# MultipleInstances + ExecutionTimeLimit, it sets:
#   * StartWhenAvailable = true  -> a run missed while the machine was off
#     (power loss / reboot) fires as soon as it comes back;
#   * RestartCount = 3, RestartInterval = 1 min -> a crashed run auto-retries;
#   * AllowStartIfOnBatteries + DontStopIfGoingOnBatteries -> outages on a
#     laptop/UPS don't skip or kill a run;
#   * WakeToRun (persistent + brain tasks only) -> the box wakes from sleep to
#     keep the core loops alive.
#
# NOTE: this does NOT change the logon requirement. Tasks remain "run only when
# <user> is logged on"; surviving a reboot with NO interactive session needs
# either auto-logon or "run whether logged on or not" (which stores the
# account password) -- an operator credential decision, not done here.
#
# Rerunnable and idempotent. Elevated-registered tasks refuse Set from a normal
# shell; those print DENIED -- rerun this script as administrator to finish them.

$ErrorActionPreference = "Stop"

# Tasks that should wake the machine from sleep (continuous + the signal brain).
$wake = @("DummyDashboard", "DummyCryptoPaperTwin", "DummyShadowPredator",
          "DummyMispricingMonitor", "DummyLivePoller")

foreach ($task in Get-ScheduledTask -TaskName "Dummy*") {
    $name = $task.TaskName
    $old = $task.Settings
    $limit = if ($old.ExecutionTimeLimit) { $old.ExecutionTimeLimit } else { "PT10M" }
    $multi = if ($old.MultipleInstancesPolicy) { $old.MultipleInstancesPolicy } else { "IgnoreNew" }

    $params = @{
        StartWhenAvailable        = $true
        RestartCount              = 3
        RestartInterval           = (New-TimeSpan -Minutes 1)
        AllowStartIfOnBatteries   = $true
        DontStopIfGoingOnBatteries = $true
        ExecutionTimeLimit        = ([System.Xml.XmlConvert]::ToTimeSpan($limit))
        MultipleInstances         = $multi
    }
    if ($wake -contains $name) { $params["WakeToRun"] = $true }

    try {
        $settings = New-ScheduledTaskSettingsSet @params
        Set-ScheduledTask -TaskName $name -Settings $settings -ErrorAction Stop | Out-Null
        $w = if ($wake -contains $name) { " +wake" } else { "" }
        Write-Host "HARDENED $name (catch-up + restart x3$w)"
    } catch {
        Write-Host "DENIED   $name (rerun as administrator): $($_.Exception.Message)"
    }
}
