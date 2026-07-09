@echo off
REM Registers the Dummy shadow predator as a Windows Scheduled Task that runs
REM one shadow cycle every 10 minutes (durable across logoff/reboot).
REM Run this once, from an elevated (Administrator) command prompt.
REM
REM Shadow-only: never trades real money. Honors runtime\autonomy\KILL.
REM Remove with:  schtasks /delete /tn "DummyShadowPredator" /f

set ACTION=cmd /c cd /d C:\src\engine\dummy ^&^& C:\Python314\python.exe scripts\run_dummy_shadow_daemon.py ^>^> runtime\autonomy\daemon_stdout.log 2^>^&1

schtasks /create /tn "DummyShadowPredator" /tr "%ACTION%" /sc minute /mo 10 /f

echo.
echo Registered. Verify with:  schtasks /query /tn "DummyShadowPredator"
echo Stop trading anytime:      type nul ^> C:\src\engine\dummy\runtime\autonomy\KILL
