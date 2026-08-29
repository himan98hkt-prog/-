# AI DEOKHU 최신 코드 받기
#
#   update.bat 을 더블클릭하거나, 터미널에서
#     powershell -ExecutionPolicy Bypass -File update.ps1
#
# .env(fal 키)와 seeds(고른 이미지), runs(만든 영상)는 건드리지 않는다.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

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

# config.yaml 은 사용자가 고치는 파일이다. 그냥 덮어쓰면 바꿔 놓은 설정이
# 조용히 되돌아간다 (업스케일 끄기, 클립 수, 음악 설정 등).
# 그래서 따로 빼놨다가 되돌려 놓고, 새 버전은 config.yaml.new 로 남긴다.
$cfg = Join-Path $Target "config.yaml"
$mine = $null
if (Test-Path $cfg) { $mine = Get-Content $cfg -Raw -Encoding UTF8 }

try {
    Info "파일을 덮어쓰는 중..."
    Copy-Item (Join-Path $src.FullName "*") -Destination $Target -Recurse -Force
    Ok "덮어쓰기 완료"
} catch {
    Die "복사 실패: $($_.Exception.Message)`n  작업실이 켜져 있으면 끄고 다시 시도하세요."
}

if ($null -ne $mine) {
    $fresh = Get-Content $cfg -Raw -Encoding UTF8
    Set-Content -Path $cfg -Value $mine -Encoding UTF8 -NoNewline
    if ($fresh -ne $mine) {
        Set-Content -Path (Join-Path $Target "config.yaml.new") -Value $fresh -Encoding UTF8 -NoNewline
        Ok "config.yaml 을 지켰습니다 (새 버전은 config.yaml.new)"
        Write-Host "      새로 생긴 설정이 있는지 두 파일을 비교해 보세요." -ForegroundColor DarkGray
    } else {
        Ok "config.yaml 유지됨"
    }
}

Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue

# 보존돼야 할 것들 확인
Write-Host ""
foreach ($keep in @(".env", "seeds", "runs", "music", "config.yaml")) {
    $p = Join-Path $Target $keep
    if (Test-Path $p) { Ok "$keep 유지됨" }
}

Write-Host "`n업데이트가 끝났습니다." -ForegroundColor Green
Write-Host "  바탕화면의 [AI DEOKHU 작업실] 을 더블클릭하세요.`n" -ForegroundColor White
Read-Host "엔터를 누르면 닫힙니다"
