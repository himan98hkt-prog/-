@echo off
chcp 65001 >nul 2>&1
setlocal enabledelayedexpansion
title 피아노이벤트 - 실행 중입니다
cls

echo.
echo   ================================================
echo      피아노이벤트를 시작합니다
echo   ================================================
echo.
echo   이 창은 프로그램이 켜져 있는 동안 그대로 두세요.
echo   끄실 때는 이 창을 닫으시면 됩니다.
echo.

rem ---- 1. 프로그램 폴더 찾기 -------------------------------
set "APP="
if exist "%~dp0pianoevent-ai\package.json" set "APP=%~dp0pianoevent-ai"
if not defined APP if exist "%~dp0package.json" set "APP=%~dp0"
if not defined APP if exist "%~dp0..\pianoevent-ai\package.json" set "APP=%~dp0..\pianoevent-ai"

if not defined APP (
  echo   [!] 프로그램 폴더를 찾지 못했습니다.
  echo.
  echo       압축을 풀지 않고 ZIP 안에서 바로 실행하면 이렇게 됩니다.
  echo       ZIP 파일을 마우스 오른쪽 클릭 - "압축 풀기" 를 먼저 해주세요.
  echo       그런 다음 풀린 폴더 안의 이 파일을 다시 두 번 누르시면 됩니다.
  echo.
  pause
  exit /b 1
)
cd /d "%APP%"

rem ---- 2. Node.js 확인 -------------------------------------
where node >nul 2>&1
if not errorlevel 1 goto NODE_OK

echo   [준비] 프로그램을 켜는 데 필요한 Node.js 가 없습니다.
echo          자동으로 설치를 시도합니다. (한 번만 하면 됩니다)
echo.

where winget >nul 2>&1
if errorlevel 1 goto NODE_MANUAL

winget install --id OpenJS.NodeJS.LTS -e --silent --accept-source-agreements --accept-package-agreements
if exist "%ProgramFiles%\nodejs\node.exe" set "PATH=%ProgramFiles%\nodejs;%PATH%"
if exist "%ProgramFiles(x86)%\nodejs\node.exe" set "PATH=%ProgramFiles(x86)%\nodejs;%PATH%"

where node >nul 2>&1
if not errorlevel 1 (
  echo.
  echo   [완료] Node.js 설치가 끝났습니다.
  echo.
  goto NODE_OK
)

echo.
echo   [알림] 설치는 됐지만 이 창이 아직 인식하지 못합니다.
echo          이 창을 닫고, 시작하기 파일을 한 번만 다시 눌러주세요.
echo.
pause
exit /b 0

:NODE_MANUAL
echo   [안내] 자동 설치를 쓸 수 없는 윈도우입니다.
echo          브라우저를 열어드릴 테니 초록색 LTS 버튼을 눌러 설치해주세요.
echo          설치가 끝나면 이 창을 닫고 시작하기를 다시 누르시면 됩니다.
echo.
start "" "https://nodejs.org/ko/download"
pause
exit /b 0

:NODE_OK
for /f "tokens=*" %%v in ('node -v 2^>nul') do set "NODEV=%%v"
echo   [1/3] 준비 완료 ^(Node.js !NODEV!^)

rem ---- 3. 최초 1회 준비 작업 -------------------------------
if exist "node_modules\next\package.json" goto DEPS_OK

echo   [2/3] 처음 실행이라 준비 작업을 합니다.
echo         2~4분 걸립니다. 인터넷이 연결돼 있어야 합니다.
echo         노란 경고 글씨가 지나가도 정상이니 그대로 두세요.
echo.
call npm install --no-audit --no-fund --loglevel=error
if errorlevel 1 goto INSTALL_FAIL
echo.
echo   [2/3] 준비 작업 완료
goto RUN

:DEPS_OK
echo   [2/3] 준비 작업은 이미 끝나 있습니다

:RUN
echo   [3/3] 프로그램을 켜는 중입니다. 잠시 후 브라우저가 저절로 열립니다.
echo.

start "" /min powershell -NoProfile -ExecutionPolicy Bypass -Command "for($i=0; $i -lt 300; $i++){ $c=New-Object Net.Sockets.TcpClient; try{ $c.Connect('127.0.0.1',3000); $c.Close(); Start-Process 'http://localhost:3000'; break } catch{ Start-Sleep -Milliseconds 700 } }"

call npm run dev

echo.
echo   프로그램이 종료되었습니다.
pause
exit /b 0

:INSTALL_FAIL
echo.
echo   [!] 준비 작업이 끝나지 못했습니다.
echo.
echo       - 인터넷 연결을 확인해주세요.
echo       - 회사/학원 방화벽이 막고 있을 수 있습니다.
echo       - 이 창을 닫고 다시 한 번 눌러보시면 되는 경우가 많습니다.
echo.
pause
exit /b 1
