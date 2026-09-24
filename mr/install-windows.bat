@echo off
rem ===========================================================================
rem  피아노 학원 반주 프로그램 — 윈도우 설치·실행
rem
rem  두 번 눌러 실행하세요. 처음엔 설치까지 하고, 그 다음부터는 바로 뜹니다.
rem
rem  이 파일은 일부러 얇게 두었습니다. 배치 파일에서 한글을 많이 다루면
rem  PC 마다 깨지는 일이 잦아서, 파이썬을 찾는 것까지만 하고 나머지는
rem  tools\setup.py 가 합니다.
rem ===========================================================================
chcp 65001 >nul 2>&1
set PYTHONIOENCODING=utf-8
set PYTHONUTF8=1
cd /d "%~dp0"

rem py 런처를 먼저 봅니다. 윈도우에서 python 은 파이썬이 없을 때
rem Microsoft Store 를 열어 버려서, 없는 것을 "있다"고 착각하게 됩니다.
set PY=
py -3 --version >nul 2>&1 && set PY=py -3
if not defined PY (
  python --version >nul 2>&1 && set PY=python
)

if not defined PY (
  echo.
  echo   ============================================================
  echo    파이썬이 필요합니다. 아직 안 깔려 있습니다.
  echo   ============================================================
  echo.
  echo    1^) https://www.python.org/downloads/  에서 내려받으세요.
  echo.
  echo    2^) 설치 첫 화면 아래쪽의
  echo         [v] Add python.exe to PATH
  echo       를 **반드시 체크**하고 설치하세요.
  echo       이걸 빠뜨리면 이 창이 파이썬을 못 찾습니다.
  echo.
  echo    3^) 설치가 끝나면 이 파일을 다시 두 번 누르세요.
  echo.
  echo    ^(winget 을 쓰신다면:  winget install Python.Python.3.12^)
  echo.
  pause
  exit /b 1
)

%PY% "tools\setup.py"
if errorlevel 1 pause
