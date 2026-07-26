# Compatibility wrapper for the verified cooperative Python VACUUM.
#
# The historical implementation disabled every Dummy task and force-killed
# Python processes. That required elevation, could terminate unrelated work,
# and still let Task Scheduler report success. The Python runner instead uses
# the shared maintenance lease, bounded SQLite waits, a mandatory verified
# backup, integrity checks, and truthful exit codes.

$ErrorActionPreference = "Stop"
$manifest = $env:DUMMY_MAINTENANCE_BACKUP_MANIFEST
if ([string]::IsNullOrWhiteSpace($manifest)) {
    Write-Error "DUMMY_MAINTENANCE_BACKUP_MANIFEST is required"
    exit 2
}

$python = (Get-Command python -ErrorAction Stop).Source
& $python "scripts\run_dummy_ledger_vacuum.py" --backup-manifest $manifest
exit $LASTEXITCODE
