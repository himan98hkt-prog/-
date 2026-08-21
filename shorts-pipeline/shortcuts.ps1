# 바탕화면 바로가기 만들기
#
#   shortcuts.bat 을 더블클릭하거나
#     powershell -ExecutionPolicy Bypass -File shortcuts.ps1
#
# 만드는 것:
#   AI DEOKHU 작업실   - 브라우저 관리 화면을 연다
#   AI DEOKHU 업데이트 - 최신 코드를 받는다
#   AI DEOKHU 폴더     - 프로그램 폴더를 연다

$ErrorActionPreference = "Stop"
$Root = $PSScriptRoot
$Desk = [Environment]::GetFolderPath("Desktop")
$W = New-Object -ComObject WScript.Shell

function Make($name, $target, $args, $icon) {
    $lnk = Join-Path $Desk "$name.lnk"
    $s = $W.CreateShortcut($lnk)
    $s.TargetPath = $target
    if ($args) { $s.Arguments = $args }
    $s.WorkingDirectory = $Root
    $s.IconLocation = $icon
    $s.Save()
    Write-Host "  OK  $name" -ForegroundColor Green
}

Write-Host "`n바탕화면 바로가기를 만듭니다" -ForegroundColor White
Write-Host "폴더: $Root`n"

# 작업실 — 서버를 띄우고 브라우저를 연다. 창은 최소화해 둔다.
$studio = Join-Path $Root "studio.bat"
@"
@echo off
title AI DEOKHU 작업실
cd /d "%~dp0"
echo.
echo   AI DEOKHU 작업실을 여는 중...
echo   이 창을 닫으면 작업실이 종료됩니다.
echo.
python main.py ui
pause
"@ | Set-Content -Path $studio -Encoding OEM

Make "AI DEOKHU 작업실"   $studio                       ""  "shell32.dll,220"
Make "AI DEOKHU 업데이트" (Join-Path $Root "update.bat") ""  "shell32.dll,238"
Make "AI DEOKHU 폴더"     "explorer.exe"                 $Root "shell32.dll,4"

Write-Host "`n바탕화면을 확인하세요." -ForegroundColor Green
Write-Host "  작업실을 더블클릭하면 브라우저에서 관리 화면이 열립니다.`n"
Read-Host "엔터를 누르면 닫힙니다"
