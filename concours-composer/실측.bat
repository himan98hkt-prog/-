@echo off
REM 실측 - 실제 API 로 한 곡 만들어 비용·시간·품질을 잰다. 두 번 눌러 실행하십시오.
REM
REM 이 파일은 돈을 씁니다. 곡 하나에 평균 $1.6, 최고 $3.2 입니다.
REM 준비 점검(무료)을 먼저 하고, 통과했을 때만 만들 것인지 묻습니다.
cd /d "%~dp0"
title 실측 - 창 안을 클릭하지 마십시오
REM 창 안을 클릭하면 "빠른 편집" 선택 모드로 작업이 멈춘다. 미리 말해 준다.
echo.
echo   [알림] 이 창 안을 마우스로 클릭하지 마십시오 - 클릭하면 작업이 멈춥니다.
echo          이미 멈췄다면 이 창을 한 번 누르고 Esc 를 누르면 이어서 돌아갑니다.
echo.
if not exist ".venv\Scripts\python.exe" (
  echo   아직 설치가 되어 있지 않습니다. "설치.bat" 을 먼저 두 번 누르십시오.
  echo.
  pause
  exit /b 1
)

echo   1단계 - 준비 점검 ^(무료^)
echo.
".venv\Scripts\python.exe" scripts\auto_compose.py --preflight > "실측결과.txt" 2>&1
type "실측결과.txt"
echo.
findstr /C:"[X]" "실측결과.txt" >nul
if not errorlevel 1 (
  echo   위 [X] 를 먼저 해결해야 합니다. 아무것도 만들지 않았고 돈도 쓰지 않았습니다.
  echo   결과는 "실측결과.txt" 에 저장했습니다.
  echo.
  pause
  exit /b 1
)

echo   준비가 끝났습니다.
echo.
echo   이제 실제로 한 곡 만듭니다. 곡 하나에 평균 $1.6, 최고 $3.2 가 듭니다.
echo   1~3분 걸립니다.
echo.
set /p GO="   만들까요? (Y = 예 / 그 밖의 키 = 아니요) : "
if /i not "%GO%"=="Y" (
  echo.
  echo   그만두었습니다. 돈은 쓰지 않았습니다.
  echo.
  pause
  exit /b 0
)

echo.
echo   2단계 - 한 곡 만들기 ^(행진곡 - 레벨 4^)
echo.
echo. >> "실측결과.txt"
echo ================ 실제 작곡 ================ >> "실측결과.txt"
".venv\Scripts\python.exe" scripts\auto_compose.py --preset march --level 4 >> "실측결과.txt" 2>&1
type "실측결과.txt"
echo.
echo   ------------------------------------------------------------
echo   끝났습니다. 결과가 "실측결과.txt" 에 저장되어 있습니다.
echo   그 파일을 그대로 보내 주시면 비용과 품질을 함께 보겠습니다.
echo   만든 악보와 음원은 runs\auto 폴더에 있습니다.
echo   ------------------------------------------------------------
echo.
pause
