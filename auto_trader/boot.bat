@echo off
rem Runs at Windows logon when autostart is enabled.
rem Starts the dashboard, and the trading bot too when the flag file exists.
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

rem Wait for the network to settle after a reboot before touching the broker API.
timeout /t 30 /nobreak >nul 2>&1

if not exist ".venv\Scripts\python.exe" goto no_venv

if exist "data\autostart_trading" (
    ".venv\Scripts\python.exe" scripts\boot_trading.py
)

rem The dashboard runs in the foreground and owns this window.
call start.bat
exit /b 0

:no_venv
echo Not set up yet. Run start.bat once by hand first.
timeout /t 20 >nul 2>&1
exit /b 1
