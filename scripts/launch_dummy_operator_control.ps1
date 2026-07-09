# Dummy Operator Control - one-click launcher.
# Starts the FastAPI backend (if not already up) and the frontend preview/dev
# server (if not already up), then opens the browser at /operator-control.
#
# This launcher never runs live proof, never contacts the broker, never
# modifies live-submit/caps, and never creates approvals.

[CmdletBinding()]
param(
    [string]$BackendPort = "8000",
    [string]$FrontendPort = "4173",
    [switch]$Dev
)

$ErrorActionPreference = "Stop"
$Root = "C:\src\engine\dummy"
Set-Location -LiteralPath $Root

function Test-Port([string]$Port) {
    try {
        $c = New-Object System.Net.Sockets.TcpClient
        $iar = $c.BeginConnect("127.0.0.1", [int]$Port, $null, $null)
        $ok = $iar.AsyncWaitHandle.WaitOne(600)
        if ($ok) { $c.EndConnect($iar); $c.Close(); return $true }
        $c.Close()
    } catch {}
    return $false
}

function Start-Bg([string]$Title, [string]$Cmd) {
    Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "title $Title && $Cmd" -WindowStyle Normal
}

Write-Host "=== Dummy Operator Control launcher ===" -ForegroundColor Cyan
Write-Host "repo root: $Root"

# --- backend ---
if (Test-Port $BackendPort) {
    Write-Host "backend already up on :$BackendPort" -ForegroundColor Green
} else {
    Write-Host "starting backend on :$BackendPort ..." -ForegroundColor Yellow
    Start-Bg "Dummy API" "cd /d $Root && python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port $BackendPort"
    Start-Sleep -Seconds 4
    if (Test-Port $BackendPort) {
        Write-Host "backend up" -ForegroundColor Green
    } else {
        Write-Host "backend did not bind :$BackendPort in time - continuing anyway" -ForegroundColor Red
    }
}

# --- frontend ---
$FPort = if ($Dev) { "5173" } else { $FrontendPort }
if (Test-Port $FPort) {
    Write-Host "frontend already up on :$FPort" -ForegroundColor Green
} else {
    $uiDir = Join-Path $Root "dashboard\frontend"
    if ($Dev) {
        Write-Host "starting frontend dev server on :$FPort ..." -ForegroundColor Yellow
        Start-Bg "Dummy UI (dev)" "cd /d $uiDir && npm run dev -- --host 127.0.0.1 --port $FPort"
    } else {
        $dist = Join-Path $uiDir "dist"
        if (-not (Test-Path -LiteralPath $dist)) {
            Write-Host "dist not found - building frontend ..." -ForegroundColor Yellow
            Start-Process -FilePath "cmd.exe" -ArgumentList "/k", "cd /d $uiDir && npm run build" -WindowStyle Normal -Wait
        }
        Write-Host "starting frontend preview on :$FPort ..." -ForegroundColor Yellow
        Start-Bg "Dummy UI (preview)" "cd /d $uiDir && npm run preview -- --host 127.0.0.1 --port $FPort"
    }
    Start-Sleep -Seconds 5
    if (Test-Port $FPort) {
        Write-Host "frontend up" -ForegroundColor Green
    } else {
        Write-Host "frontend did not bind :$FPort in time - continuing anyway" -ForegroundColor Red
    }
}

# --- open browser ---
$url = "http://localhost:$FPort/operator-control"
Write-Host "opening browser: $url" -ForegroundColor Cyan
Start-Process $url

Write-Host ""
Write-Host "Launcher complete. No live proof, no broker contact, no caps/approval mutation." -ForegroundColor DarkGray
Write-Host "Close the server windows to stop." -ForegroundColor DarkGray
