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
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Root = $PSScriptRoot
$Desk = [Environment]::GetFolderPath("Desktop")
if (-not $Desk -or -not (Test-Path $Desk)) {
    Write-Host "  X   바탕화면 폴더를 찾지 못했습니다." -ForegroundColor Red
    Read-Host "`n엔터를 누르면 닫힙니다"; exit 1
}
$W = New-Object -ComObject WScript.Shell

# $args 는 파워셸 예약 변수라 매개변수 이름으로 쓸 수 없다.
function Make($name, $target, $cmdArgs, $icon) {
    $lnk = Join-Path $Desk "$name.lnk"
    $s = $W.CreateShortcut($lnk)
    $s.TargetPath = $target
    if ($cmdArgs) { $s.Arguments = $cmdArgs }
    $s.WorkingDirectory = $Root
    $s.IconLocation = $icon
    $s.Save()
    Write-Host "  OK  $name" -ForegroundColor Green
}

Write-Host "`n바탕화면 바로가기를 만듭니다" -ForegroundColor White
Write-Host "폴더: $Root`n"

Make "AI DEOKHU 작업실"   (Join-Path $Root "start.bat")     "" "shell32.dll,220"
Make "AI DEOKHU 업데이트" (Join-Path $Root "update.bat")    "" "shell32.dll,238"
Make "AI DEOKHU 폴더"     "explorer.exe"                 $Root "shell32.dll,4"

Write-Host "`n바탕화면을 확인하세요." -ForegroundColor Green
Write-Host "  [AI DEOKHU 작업실] 을 더블클릭하면 브라우저에서 관리 화면이 열립니다.`n"
Read-Host "엔터를 누르면 닫힙니다"
