<#
Register ONE isolated scheduled task per sports league for the history lake +
walk-forward, so a failure or hang in one league can never stall another (the
operator's "every league on its own scheduler" requirement). Start times are
staggered so they don't all fire at once.

Off-season leagues (currently nba, ncaamb, and the football/hockey slate) still
register: their daily ESPN refresh is a cheap no-op with no new games, and the
task lights up automatically when their season starts -- nothing to re-enable.
Remove a league from $Leagues below, or `Unregister-ScheduledTask Dummy*_<lg>`,
to drop it entirely.

Run from an elevated-or-normal PowerShell:
    powershell -ExecutionPolicy Bypass -File scripts\register_dummy_sports_per_league.ps1
#>
param(
    [string]$Repo   = "C:\src\engine\dummy",
    [string]$Python = "C:\Users\chris\.dummy-desktop\venv\Scripts\pythonw.exe",
    [switch]$WhatIf
)

# Fallback to a plain python if the desktop venv isn't present.
if (-not (Test-Path $Python)) { $Python = (Get-Command python).Source }

$Leagues = @("mlb","wnba","nba","nfl","nhl","ncaaf","ncaamb")
$Basketball = @("wnba","nba","ncaamb")   # get a boxscore task too (for Four Factors)
$Backfill = Join-Path $Repo "scripts\run_dummy_sports_history_backfill.py"
$WalkFwd  = Join-Path $Repo "scripts\run_dummy_sports_walk_forward.py"
$BoxFill  = Join-Path $Repo "scripts\run_dummy_sports_boxscore_backfill.py"

$i = 0
foreach ($lg in $Leagues) {
    # Stagger: lake refresh at 05:00 + 12*i min; boxscores +3; walk-forward +6.
    $lakeAt = (Get-Date "05:00").AddMinutes(12 * $i).ToString("HH:mm")
    $boxAt  = (Get-Date "05:00").AddMinutes(12 * $i + 3).ToString("HH:mm")
    $wfAt   = (Get-Date "05:00").AddMinutes(12 * $i + 6).ToString("HH:mm")
    $i++

    $jobs = @(
        @{ Name = "DummyLake_$lg"; At = $lakeAt;
           Args = "`"$Backfill`" --source espn --league $lg" },
        @{ Name = "DummyWF_$lg";   At = $wfAt;
           Args = "`"$WalkFwd`" --league $lg" }
    )
    if ($Basketball -contains $lg) {
        $jobs += @{ Name = "DummyBox_$lg"; At = $boxAt;
                    Args = "`"$BoxFill`" --league $lg --min-interval 0.4" }
    }
    foreach ($j in $jobs) {
        $action  = New-ScheduledTaskAction -Execute $Python -Argument $j.Args -WorkingDirectory $Repo
        $trigger = New-ScheduledTaskTrigger -Daily -At $j.At
        $set     = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
                     -ExecutionTimeLimit (New-TimeSpan -Minutes 20)
        if ($WhatIf) {
            Write-Host "[dry-run] $($j.Name) @ $($j.At): $Python $($j.Args)"
        } else {
            Register-ScheduledTask -TaskName $j.Name -Action $action -Trigger $trigger `
                -Settings $set -Force -User $env:USERNAME | Out-Null
            Write-Host "registered $($j.Name) @ $($j.At)"
        }
    }
}
$total = $Leagues.Count * 2 + $Basketball.Count
Write-Host "Done. $($Leagues.Count) leagues (+$($Basketball.Count) boxscore tasks) = $total isolated schedulers."
