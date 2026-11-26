@echo off
rem presenter-sidecar: stop
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0stop.ps1"
pause
