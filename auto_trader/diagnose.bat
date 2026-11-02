@echo off
rem Explains WHY the results are bad. Reads the local DB only - no orders, no AI calls.
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto no_venv

".venv\Scripts\python.exe" scripts\diagnose.py
echo.
pause
exit /b 0

:no_venv
echo [X] Not set up yet. Run start.bat once by hand first.
echo.
pause
exit /b 1
