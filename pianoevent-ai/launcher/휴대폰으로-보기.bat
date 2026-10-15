@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title 피아노이벤트 - 휴대폰으로 보기
cls

echo.
echo   ================================================
echo      휴대폰으로 보기
echo   ================================================
echo.
echo   휴대폰과 이 컴퓨터가 같은 와이파이에 연결돼 있어야 합니다.
echo   잠시 후 QR 코드가 뜨면 휴대폰 카메라로 비추세요.
echo.

set "APP="
if exist "%~dp0pianoevent-ai\package.json" set "APP=%~dp0pianoevent-ai"
if not defined APP if exist "%~dp0package.json" set "APP=%~dp0"
if not defined APP if exist "%~dp0..\pianoevent-ai\package.json" set "APP=%~dp0..\pianoevent-ai"

if not defined APP (
  echo   [!] 프로그램 폴더를 찾지 못했습니다.
  echo       ZIP 파일을 오른쪽 클릭 - "압축 풀기" 를 먼저 해주세요.
  echo.
  pause
  exit /b 1
)
cd /d "%APP%"

where node >nul 2>&1
if errorlevel 1 (
  echo   [!] 먼저 "시작하기" 를 한 번 실행해주세요.
  echo       필요한 프로그램을 자동으로 설치해 드립니다.
  echo.
  pause
  exit /b 1
)

if not exist "node_modules\next\package.json" (
  echo   [준비] 처음 실행이라 준비 작업을 합니다. 2~4분 걸립니다.
  echo.
  call npm install --no-audit --no-fund --loglevel=error
  if errorlevel 1 (
    echo.
    echo   [!] 준비 작업이 끝나지 못했습니다. 인터넷 연결을 확인해주세요.
    pause
    exit /b 1
  )
)

echo   처음 실행하면 윈도우 방화벽 창이 뜹니다. 반드시 "액세스 허용" 을 눌러주세요.
echo.

call npm run mobile

echo.
echo   종료되었습니다.
pause
exit /b 0
