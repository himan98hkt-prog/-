# AI DEOKHU 최신 코드 받기
#
#   update.bat 을 더블클릭하거나, 터미널에서
#     powershell -ExecutionPolicy Bypass -File update.ps1
#
# .env(fal 키)와 seeds(고른 이미지), runs(만든 영상)는 건드리지 않는다.

$ErrorActionPreference = "Stop"
$ZipUrl = "https://github.com/himan98hkt-prog/-/archive/refs/heads/claude/auto-video-generation-upload-3kilh6.zip"
$Target = $PSScriptRoot

function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Info($m) { Write-Host "  ..  $m" -ForegroundColor Cyan }
function Die($m)  { Write-Host "`n  X   $m" -ForegroundColor Red; Read-Host "`n엔터를 누르면 닫힙니다"; exit 1 }

Write-Host "`nAI DEOKHU 업데이트" -ForegroundColor White
Write-Host "대상 폴더: $Target`n"

$zip = Join-Path $env:TEMP "aideokhu_update.zip"
$tmp = Join-Path $env:TEMP "aideokhu_update_x"

try {
    Info "최신 코드를 내려받는 중..."
    $old = $ProgressPreference; $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $ZipUrl -OutFile $zip -UseBasicParsing
    $ProgressPreference = $old
    Ok ("{0:N1} MB 받음" -f ((Get-Item $zip).Length / 1MB))
} catch {
    Die "내려받기 실패: $($_.Exception.Message)`n  인터넷 연결을 확인하세요."
}

try {
    Info "압축을 푸는 중..."
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive -Path $zip -DestinationPath $tmp -Force
} catch {
    Die "압축 해제 실패: $($_.Exception.Message)"
}

$src = Get-ChildItem $tmp -Recurse -Directory -Filter "shorts-pipeline" |
       Where-Object { Test-Path (Join-Path $_.FullName "main.py") } |
       Select-Object -First 1
if (-not $src) { Die "받은 파일 안에서 프로그램 폴더를 찾지 못했습니다." }

try {
    Info "파일을 덮어쓰는 중..."
    Copy-Item (Join-Path $src.FullName "*") -Destination $Target -Recurse -Force
    Ok "덮어쓰기 완료"
} catch {
    Die "복사 실패: $($_.Exception.Message)`n  작업실(python main.py ui)이 켜져 있으면 끄고 다시 시도하세요."
}

Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue

# 보존돼야 할 것들 확인
Write-Host ""
foreach ($keep in @(".env", "seeds", "runs")) {
    $p = Join-Path $Target $keep
    if (Test-Path $p) { Ok "$keep 유지됨" }
}

Write-Host "`n업데이트가 끝났습니다." -ForegroundColor Green
Write-Host "  작업실 열기:  python main.py ui`n" -ForegroundColor White
Read-Host "엔터를 누르면 닫힙니다"
