@echo off
rem Starts the trading bot on its own, without the dashboard.
rem Use this when the dashboard's start button does not work.
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
set PYTHONUTF8=1
set PYTHONIOENCODING=utf-8

echo ========================================================
echo   Auto Trader - bot only
echo ========================================================
echo.

if not exist ".venv\Scripts\python.exe" goto no_venv
if not exist ".env" goto no_env

echo Starting. Keep this window open while trading.
echo Stop with Ctrl+C - the current cycle finishes first.
echo.

".venv\Scripts\python.exe" main.py
set CODE=%errorlevel%

echo.
if not "%CODE%"=="0" (
    echo [X] The bot stopped with code %CODE%. The lines above say why.
) else (
    echo The bot has stopped.
)
echo.
pause
exit /b %CODE%

:no_venv
echo [X] Not set up yet. Run start.bat once by hand first.
echo.
pause
exit /b 1

:no_env
echo [X] No .env found. Open the dashboard (start.bat) and save your keys first.
echo.
pause
exit /b 1
