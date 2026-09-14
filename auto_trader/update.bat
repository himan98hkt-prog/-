@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================================
echo   Updating to the latest version
echo ========================================================
echo.

if not exist ".venv\Scripts\python.exe" goto no_venv
".venv\Scripts\python.exe" scripts\update.py
if errorlevel 1 goto failed
echo.
pause
exit /b 0

:no_venv
echo [X] Not set up yet. Run start.bat first.
echo.
pause
exit /b 1

:failed
echo.
echo [X] The update did not complete. Your keys and records were not touched.
echo.
pause
exit /b 1
