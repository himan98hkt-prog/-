@echo off
rem 원스텝 실행 — 이 파일을 더블클릭하면 됩니다.
rem 하는 일: 가상환경 준비 -> 의존성 설치 -> 대시보드 실행 -> 브라우저 열기

setlocal
cd /d "%~dp0"
if "%PORT%"=="" set PORT=8765

echo ========================================================
echo   Multi-Agent 자동매매 - 준비
echo ========================================================

where py >nul 2>&1
if %errorlevel%==0 (set PY=py -3) else (set PY=python)

%PY% -c "import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)" 2>nul
if errorlevel 1 (
  echo [X] Python 3.11 이상이 필요합니다. https://www.python.org/downloads/
  pause
  exit /b 1
)

if not exist ".venv" (
  echo . 가상환경을 만드는 중...
  %PY% -m venv .venv
)
call .venv\Scripts\activate.bat

if not exist ".venv\.deps-installed" (
  echo . 의존성을 설치하는 중... 처음 한 번은 몇 분 걸립니다
  python -m pip install --quiet --upgrade pip
  python -m pip install --quiet --use-pep517 -r requirements.txt
  echo ok > .venv\.deps-installed
)

if not exist ".env" (
  echo.
  echo [!] 아직 키가 없습니다. 곧 열리는 브라우저 화면에서 입력하세요.
)

echo.
echo ========================================================
echo   대시보드:  http://127.0.0.1:%PORT%
echo.
echo   1^) 설정 화면에 API 키를 붙여넣고 [저장]
echo   2^) [키 점검 실행] 으로 전부 OK 확인
echo   3^) 현황 화면에서 [자동매매 시작]
echo.
echo   중지: Ctrl+C
echo ========================================================
echo.

start "" http://127.0.0.1:%PORT%
python scripts\dashboard.py --port %PORT%
