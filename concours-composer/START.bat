@echo off
REM start.ps1 와 같습니다. 한글 이름이 깨져 보일 때 이것을 누르십시오.
cd /d "%~dp0"
title ConcoursComposer
echo.
echo   [알림] 이 창 안을 마우스로 클릭하지 마십시오 - 클릭하면 작업이 멈춥니다.
echo          이미 멈췄다면 이 창을 한 번 누르고 Esc 를 누르면 이어서 돌아갑니다.
echo.
echo   콩쿨 작곡기를 켭니다.
echo.
powershell -NoProfile -ExecutionPolicy Bypass -Command "Get-ChildItem -Recurse -Filter *.ps1 | Unblock-File" 2>nul
powershell -NoProfile -ExecutionPolicy Bypass -File "%~dp0start.ps1"
