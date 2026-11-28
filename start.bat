@echo off
rem presenter-sidecar: start
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1" %*
pause
