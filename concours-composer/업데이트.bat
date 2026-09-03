@echo off
REM ConcoursComposer 새 판으로 올리기 - 두 번 눌러 실행하십시오.
REM
REM 지금까지는 새 판이 나올 때마다 폴더를 지우고 다시 받고 다시 설치하셨다.
REM 손이 많이 가는 것보다 나쁜 것은 위험하다는 것이다 - 지우는 습관은 언젠가
REM 지우면 안 되는 것을 지운다. 이 파일이 대신 한다: 덮어쓰고, 원장님 것은
REM 손대지 않고(API 키/만든 곡/참고 악보), 이전 판은 옆에 남겨 둔다.
cd /d "%~dp0"
title 콩쿨 작곡기 새 판으로 올리기 - 창 안을 클릭하지 마십시오
REM 명령창은 "빠른 편집" 이 기본으로 켜져 있다. 창 안을 클릭하면 제목이
REM "선택 ..." 으로 바뀌면서 **동작이 그 자리에서 멈춘다.** Esc 를 누르면 이어서 돈다.
echo.
echo   [알림] 이 창 안을 마우스로 클릭하지 마십시오 - 클릭하면 작업이 멈춥니다.
echo          이미 멈췄다면 이 창을 한 번 누르고 Esc 를 누르면 이어서 돌아갑니다.
echo.
echo   새 판이 있으면 받아서 올립니다. 없으면 그대로 둡니다.
echo   만든 곡과 API 키는 건드리지 않습니다.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0update.ps1"
echo.
if errorlevel 1 (
  echo   올리지 못했습니다. 위의 붉은 글씨를 그대로 알려 주십시오.
  echo   이전 판은 옆 폴더에 그대로 있으니 잃은 것은 없습니다.
) else (
  echo   끝났습니다.
)
echo.
pause
