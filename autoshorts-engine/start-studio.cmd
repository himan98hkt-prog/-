@echo off
setlocal
title Shorts Studio Launcher
cd /d "%~dp0"
powershell.exe -NoLogo -NoProfile -ExecutionPolicy Bypass -File "%~dp0start-studio.ps1"
if errorlevel 1 (
  echo.
  echo Startup did not finish. Open studio-startup.log in this folder.
  pause
  exit /b 1
)
