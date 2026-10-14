@echo off
rem Shares the dashboard with YOUR OWN devices through Tailscale.
rem
rem The dashboard itself stays bound to 127.0.0.1 - nothing about that changes.
rem Tailscale relays localhost over an encrypted link that only devices signed
rem into your own Tailscale account can reach. It is NOT on the public internet.
rem
rem Usage:  mobile.bat          (uses port 8765)
rem         mobile.bat 9000     (other port)
rem         mobile.bat off      (stop sharing)
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

rem Serve needs an elevated console on Windows. Re-launch ourselves if needed.
net session >nul 2>&1
if errorlevel 1 (
    echo Administrator rights are required. Asking Windows...
    powershell -NoProfile -Command "Start-Process -FilePath '%~f0' -ArgumentList '%*' -Verb RunAs"
    exit /b 0
)

set "TS=tailscale"
where tailscale >nul 2>&1
if errorlevel 1 set "TS=%ProgramFiles%\Tailscale\tailscale.exe"
if not exist "%TS%" if "%TS%" NEQ "tailscale" goto no_tailscale

if /i "%~1"=="off" goto stop

set "PORT=%~1"
if "%PORT%"=="" set "PORT=8765"

echo.
echo Sharing the dashboard on port %PORT% with your Tailscale devices...
echo.
"%TS%" serve --bg %PORT%
if errorlevel 1 goto failed

echo.
echo ---------------------------------------------------------------
"%TS%" serve status
echo ---------------------------------------------------------------
echo.
echo Open that https://... address on your phone.
echo The phone must be signed into the SAME Tailscale account.
echo.
echo This keeps working after a reboot. To stop:  mobile.bat off
echo.
pause
exit /b 0

:stop
echo Stopping the share...
"%TS%" serve off
"%TS%" serve reset
echo Done. The dashboard is reachable from this PC only again.
echo.
pause
exit /b 0

:failed
echo.
echo [X] Could not start sharing.
echo     - Is Tailscale signed in?  Try:  tailscale status
echo     - The first run asks you to turn on HTTPS for your tailnet.
echo       Open the link it printed, click the button, then run this again.
echo.
pause
exit /b 1

:no_tailscale
echo.
echo [X] Tailscale is not installed.
echo     Download it from https://tailscale.com/download/windows
echo     Install, sign in, then run this file again.
echo.
pause
exit /b 1
