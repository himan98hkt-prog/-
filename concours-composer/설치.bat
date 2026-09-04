@echo off
REM ConcoursComposer 설치 - 두 번 눌러 실행하십시오.
REM
REM 윈도우는 인터넷에서 받은 PowerShell 스크립트(.ps1)를 기본으로 막는다.
REM 원장이 명령을 외워 치게 하는 대신 이 배치 파일이 대신 풀어 준다 -
REM 배치 파일은 실행 정책의 대상이 아니라서 두 번 누르면 그냥 돈다.
cd /d "%~dp0"
title 콩쿨 작곡기 설치 중 - 창 안을 클릭하지 마십시오
REM 윈도우 명령창은 "빠른 편집" 이 기본으로 켜져 있다. 창 안을 클릭하면 제목이
REM "선택 ..." 으로 바뀌면서 **돌던 작업이 그 자리에서 멈춘다.** 화면은 그대로라
REM 고장 난 것처럼 보이는데, 사실은 사람이 멈춰 세운 것이다. 실제로 여기서 막혔다.
REM 끄는 것은 사용자 전체 설정이라 함부로 건드리지 않고, 대신 미리 말해 준다.
echo.
echo   [알림] 이 창 안을 마우스로 클릭하지 마십시오 - 클릭하면 작업이 멈춥니다.
echo          이미 멈췄다면 이 창을 한 번 누르고 Esc 를 누르면 이어서 돌아갑니다.
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
