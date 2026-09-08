@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"
if "%PORT%"=="" set PORT=8765

echo ========================================================
echo   Multi-Agent Auto Trader
echo ========================================================
echo.

rem ---- find Python 3.11+ ------------------------------------------------
rem 1) py launcher (python.org installer puts this on every Windows box)
where py >nul 2>&1
if errorlevel 1 goto try_python
rem PY holds the executable, PYA the extra argument - keeps quoting sane
rem when the interpreter lives in a path that contains spaces.
set "PY=py"
set "PYA=-3"
"%PY%" %PYA% -c "import sys;raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
if not errorlevel 1 goto found_python

:try_python
rem 2) python on PATH, skipping the Microsoft Store stub
rem    (the stub opens the Store instead of running anything)
for /f "delims=" %%P in ('where python 2^>nul') do (
    echo %%P | find /i "WindowsApps" >nul
    if errorlevel 1 (
        set "PY=%%P"
        set "PYA="
        goto check_python
    )
)
goto no_python

:check_python
"%PY%" %PYA% -c "import sys;raise SystemExit(0 if sys.version_info>=(3,11) else 1)" >nul 2>&1
if errorlevel 1 goto no_python

:found_python
echo [OK] Python found
"%PY%" %PYA% --version
echo.

rem ---- virtual environment ----------------------------------------------
if exist ".venv\Scripts\python.exe" goto have_venv
echo [..] Creating virtual environment...
"%PY%" %PYA% -m venv .venv
if errorlevel 1 goto venv_failed

:have_venv
set "VPY=.venv\Scripts\python.exe"
if not exist "%VPY%" goto venv_failed

rem ---- dependencies ------------------------------------------------------
if exist ".venv\.deps-installed" goto have_deps
echo [..] Installing dependencies. The first run takes a few minutes...
"%VPY%" -m pip install --quiet --upgrade pip
rem "ta" ships a legacy setup.py, so PEP 517 is required on some machines
"%VPY%" -m pip install --quiet --use-pep517 -r requirements.txt
if errorlevel 1 goto deps_failed
echo ok> ".venv\.deps-installed"

:have_deps
echo [OK] Dependencies ready
echo.
echo ========================================================
echo   Dashboard:  http://127.0.0.1:%PORT%/setup
echo.
echo   1) Paste your API keys on the setup page, press Save
echo   2) Press "key check" and confirm every row is OK
echo   3) Press "start" on the status page
echo.
echo   The browser opens by itself once the server is up.
echo   Keep this window open. Stop with Ctrl+C.
echo ========================================================
echo.

"%VPY%" scripts\dashboard.py --port %PORT% --open-browser
echo.
echo The dashboard has stopped.
pause
exit /b 0

rem ---- failures ----------------------------------------------------------
:no_python
echo.
echo [X] Python 3.11 or newer was not found.
echo.
echo     1. Download it from https://www.python.org/downloads/
echo     2. In the installer, TICK "Add python.exe to PATH" (bottom of the
echo        first screen) before pressing Install.
echo     3. Close this window, then double-click start.bat again.
echo.
echo     Note: the "python" that ships with the Microsoft Store does not
echo     work here. Install from python.org instead.
echo.
pause
exit /b 1

:venv_failed
echo.
echo [X] Could not create the virtual environment (.venv).
echo     Most often the folder is read-only or synced by OneDrive.
echo     Move this folder somewhere plain, e.g. C:\autotrader, and retry.
echo.
pause
exit /b 1

:deps_failed
echo.
echo [X] Dependency installation failed.
echo     Scroll up for the first line starting with ERROR and send it over.
echo     A blocked network or proxy is the usual cause.
echo.
pause
exit /b 1
