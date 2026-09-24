@echo off
rem ===========================================================================
rem  폰·태블릿에서 열기 — 같은 와이파이에 있는 기기로 반주를 보냅니다.
rem
rem  두 번 눌러 실행하세요. 주소가 뜨면 폰 브라우저에 그대로 치시면 됩니다.
rem  (install-windows.bat 을 먼저 한 번 돌리셨어야 합니다)
rem ===========================================================================
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

set PY=
py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  python --version >nul 2>&1 && set PY=python
)
if not defined PY (
  echo.
  echo   먼저 install-windows.bat 을 두 번 눌러 설치하세요.
  echo.
  pause
  exit /b 1
)

%PY% "tools\setup.py" --phone
if errorlevel 1 pause
