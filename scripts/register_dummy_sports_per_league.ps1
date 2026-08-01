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
    [string]$Python = (Join-Path $env:USERPROFILE ".dummy-desktop\venv\Scripts\pythonw.exe"),
    [switch]$WhatIf
)

# Presence is NOT capability, and assuming it was cost eight days of data.
#
# The previous check was `Test-Path $Python`. The default above points at the
# native desktop app's isolated GUI venv, which exists but holds only PySide6
# and numpy -- no httpx. So the fallback never fired, all 19 sports tasks were
# registered against an interpreter that cannot fetch, every ESPN call raised
# ModuleNotFoundError inside default_fetch_scoreboard, EspnClient.games()
# swallowed it to an empty list, ingest_espn_league logged "ok" with rows 0,
# and pythonw.exe exited 0. The lake took zero rows from 2026-07-24 to
# 2026-08-01 while every layer reported success.
#
# Probe what the interpreter can actually DO. pythonw.exe is windowless, so
# probe its console sibling and keep the original for registration.
function Test-PythonCanFetch([string]$exe) {
    if (-not $exe -or -not (Test-Path $exe)) { return $false }
    $probe = $exe -replace 'pythonw\.exe$', 'python.exe'
    if (-not (Test-Path $probe)) { $probe = $exe }
    & $probe -c "import httpx" 2>$null | Out-Null
    return ($LASTEXITCODE -eq 0)
}

if (-not (Test-PythonCanFetch $Python)) {
    $fallback = (Get-Command python -ErrorAction SilentlyContinue).Source
    # These run unattended on a schedule, so prefer the windowless sibling
    # when it exists -- otherwise every task flashes a console window.
    if ($fallback) {
        $windowless = $fallback -replace 'python\.exe$', 'pythonw.exe'
        if (Test-Path $windowless) { $fallback = $windowless }
    }
    if (-not (Test-PythonCanFetch $fallback)) {
        throw ("No usable interpreter: '$Python' cannot import httpx and neither " +
               "can '$fallback'. Registering against either would recreate the " +
               "silent eight-day outage of 2026-07-24. Pass -Python explicitly.")
    }
    Write-Warning "'$Python' cannot import httpx; falling back to '$fallback'."
    $Python = $fallback
}
Write-Host "registering against interpreter: $Python"

$Leagues = @("mlb","wnba","nba","nfl","nhl","ncaaf","ncaamb")
$Basketball = @("wnba","nba","ncaamb")   # get a boxscore task too (for Four Factors)
$EpaLeagues = @("nfl")                     # nflfastR EPA (open, no key)
$Backfill = Join-Path $Repo "scripts\run_dummy_sports_history_backfill.py"
$WalkFwd  = Join-Path $Repo "scripts\run_dummy_sports_walk_forward.py"
$BoxFill  = Join-Path $Repo "scripts\run_dummy_sports_boxscore_backfill.py"
$EpaFill  = Join-Path $Repo "scripts\run_dummy_sports_epa_backfill.py"
$Tune     = Join-Path $Repo "scripts\run_dummy_sports_tune.py"

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
    if ($EpaLeagues -contains $lg) {
        $jobs += @{ Name = "DummyEpa_$lg"; At = $boxAt;
                    Args = "`"$EpaFill`" --seasons 2016-2025" }
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
# One self-tuning task re-optimizes every analytic's priors from the fresh lake
# (runs after the day's backfills). This is the recursive-improvement heartbeat.
$tuneAction  = New-ScheduledTaskAction -Execute $Python -Argument "`"$Tune`"" -WorkingDirectory $Repo
$tuneTrigger = New-ScheduledTaskTrigger -Daily -At "06:30"
$tuneSet     = New-ScheduledTaskSettingsSet -StartWhenAvailable -MultipleInstances IgnoreNew `
                 -ExecutionTimeLimit (New-TimeSpan -Minutes 30)
if ($WhatIf) {
    Write-Host "[dry-run] DummyTune @ 06:30: $Python `"$Tune`""
} else {
    Register-ScheduledTask -TaskName "DummyTune" -Action $tuneAction -Trigger $tuneTrigger `
        -Settings $tuneSet -Force -User $env:USERNAME | Out-Null
    Write-Host "registered DummyTune @ 06:30"
}

$total = $Leagues.Count * 2 + $Basketball.Count + $EpaLeagues.Count + 1
Write-Host "Done. $($Leagues.Count) leagues (+$($Basketball.Count) boxscore, +$($EpaLeagues.Count) EPA, +1 tune) = $total isolated schedulers."
