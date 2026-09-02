@echo off
REM 아이콘이 없거나 지워졌을 때 쓰는 예비 실행기. 두 번 눌러 실행하십시오.
cd /d "%~dp0"
if not exist ".venv\Scripts\python.exe" (
  echo.
  echo   먼저 "설치.bat" 을 두 번 눌러 설치하십시오.
  echo.
  pause
  exit /b 1
)
start "" ".venv\Scripts\pythonw.exe" "scripts\launch.py"
