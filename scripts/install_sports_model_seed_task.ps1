param(
    [string]$TaskName = "DummySportsModelSeed",
    [int]$IntervalMinutes = 5,
    [int]$StartDelayMinutes = 1,
    [int]$TimeoutMinutes = 3
)

$ErrorActionPreference = "Stop"
$repo = "C:\src\engine\dummy"
$python = "C:\Python314\pythonw.exe"
$script = Join-Path $repo "scripts\run_sports_model_seed.py"

if (-not (Test-Path -LiteralPath $script)) {
    throw "Sports model seed producer not found: $script"
}

$start = (Get-Date).AddMinutes([Math]::Max(1, $StartDelayMinutes)).ToString("HH:mm")
if ($IntervalMinutes -ne 5) {
    throw "DummySportsModelSeed has a fixed five-minute cadence"
}
if ($TimeoutMinutes -lt 2 -or $TimeoutMinutes -gt 3) {
    throw "DummySportsModelSeed timeout must remain between two and three minutes"
}
$cadence = 5
$timeout = $TimeoutMinutes
$arguments = "`"$script`""
$bootstrapAction = "cmd /c cd /d $repo && $python $arguments"

& schtasks.exe /Create /TN $TaskName /TR $bootstrapAction /SC MINUTE `
    /MO $cadence /ST $start /F | Out-Host
if ($LASTEXITCODE -ne 0) {
    throw "schtasks.exe failed with exit code $LASTEXITCODE"
}

$action = New-ScheduledTaskAction `
    -Execute $python `
    -Argument $arguments `
    -WorkingDirectory $repo
$settings = New-ScheduledTaskSettingsSet `
    -MultipleInstances IgnoreNew `
    -ExecutionTimeLimit (New-TimeSpan -Minutes $timeout) `
    -RestartCount 1 `
    -RestartInterval (New-TimeSpan -Minutes 1) `
    -StartWhenAvailable `
    -AllowStartIfOnBatteries `
    -DontStopIfGoingOnBatteries
Set-ScheduledTask -TaskName $TaskName -Action $action -Settings $settings | Out-Null

# Installation is intentionally non-arming. The parent operator workflow must
# explicitly enable the task after tests and the first manual artifact readback.
Disable-ScheduledTask -TaskName $TaskName | Out-Null

$task = Get-ScheduledTask -TaskName $TaskName
$info = Get-ScheduledTaskInfo -TaskName $TaskName
[pscustomobject]@{
    TaskName = $task.TaskName
    State = $task.State.ToString()
    Enabled = $task.Settings.Enabled
    NextRunTime = $info.NextRunTime
    Action = "$python $arguments"
    WorkingDirectory = $repo
    CadenceMinutes = $cadence
    ExecutionTimeLimitMinutes = $timeout
    RestartCount = 1
    MultipleInstances = "IgnoreNew"
    InstalledDisabledForValidation = $true
    PublicGetOnly = $true
    LedgerAccess = "read_only_mode_ro_query_only_snapshot"
    NoLedgerWrites = $true
    ExecutionAuthority = $false
    CapitalAuthority = $false
}
