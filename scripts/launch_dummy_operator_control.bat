@echo off
title Dummy Operator Control
cd /d C:\src\engine\dummy
powershell -NoProfile -ExecutionPolicy Bypass -File "scripts\launch_dummy_operator_control.ps1" %*
