@echo off
rem Shows the KIS account balance right now. Never places an order.
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

if not exist ".venv\Scripts\python.exe" goto no_venv

".venv\Scripts\python.exe" scripts\check_account.py
echo.
pause
exit /b 0

:no_venv
echo [X] Not set up yet. Run start.bat once by hand first.
echo.
pause
exit /b 1
