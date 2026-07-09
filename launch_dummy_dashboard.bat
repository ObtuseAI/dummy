@echo off
title Dummy Dashboard Launcher
cd /d C:\src\engine\dummy

echo ============================================
echo   Dummy Operator Dashboard
echo   Backend  : http://localhost:8000
echo   Dashboard: http://localhost:4173/operator-control
echo ============================================
echo.

REM --- backend API (FastAPI on :8000) ---
start "Dummy API" cmd /k "cd /d C:\src\engine\dummy && python -m uvicorn dashboard.backend.main:app --host 127.0.0.1 --port 8000"

REM --- frontend (serves built dist on :4173) ---
start "Dummy UI" cmd /k "cd /d C:\src\engine\dummy\dashboard\frontend && npm run preview -- --host 127.0.0.1 --port 4173"

REM --- give servers a moment, then open the operator control page ---
timeout /t 6 /nobreak >nul
start "" "http://localhost:4173/operator-control"

echo Launched. Close the two server windows to stop.
timeout /t 3 /nobreak >nul
