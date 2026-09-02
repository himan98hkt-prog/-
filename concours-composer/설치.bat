@echo off
REM ConcoursComposer 설치 - 두 번 눌러 실행하십시오.
REM
REM 윈도우는 인터넷에서 받은 PowerShell 스크립트(.ps1)를 기본으로 막는다.
REM 원장이 명령을 외워 치게 하는 대신 이 배치 파일이 대신 풀어 준다 -
REM 배치 파일은 실행 정책의 대상이 아니라서 두 번 누르면 그냥 돈다.
cd /d "%~dp0"
echo.
echo   콩쿨 작곡기를 설치합니다. 처음 한 번은 몇 분 걸립니다.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0install.ps1"
echo.
if errorlevel 1 (
  echo   설치가 끝나지 못했습니다. 위의 붉은 글씨를 그대로 알려 주십시오.
) else (
  echo   설치가 끝났습니다. 바탕화면의 "콩쿨 작곡기" 아이콘을 두 번 누르십시오.
)
echo.
pause
