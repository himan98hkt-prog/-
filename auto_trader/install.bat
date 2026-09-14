@echo off
setlocal
chcp 65001 >nul 2>&1
cd /d "%~dp0"

echo ========================================================
echo   Desktop shortcut
echo ========================================================
echo.

rem The shortcut name is Korean, so Python creates it - a .bat file
rem cannot carry non-ASCII text reliably across cmd code pages.
if exist ".venv\Scripts\python.exe" (
    ".venv\Scripts\python.exe" scripts\make_shortcut.py
    goto done
)

where py >nul 2>&1
if errorlevel 1 goto use_python
py -3 scripts\make_shortcut.py
goto done

:use_python
python scripts\make_shortcut.py

:done
echo.
pause
exit /b 0
