# AI DEOKHU 작업실 열기
#
#   start.bat 을 더블클릭하면 이 스크립트가 돈다.
#   파이썬 확인 -> 필요한 꾸러미 설치 -> .env 준비 -> 작업실 실행.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$Root = $PSScriptRoot
Set-Location $Root

function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Info($m) { Write-Host "  ..  $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "  !   $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "`n  X   $m" -ForegroundColor Red; Read-Host "`n엔터를 누르면 닫힙니다"; exit 1 }

Write-Host "`nAI DEOKHU 작업실" -ForegroundColor White
Write-Host "폴더: $Root`n"

# 1. 파이썬
$py = $null
foreach ($cand in @("python", "py")) {
    try {
        $v = & $cand --version 2>&1
        if ($LASTEXITCODE -eq 0 -and "$v" -match "Python 3") { $py = $cand; Ok "파이썬 확인: $v"; break }
    } catch { }
}
if (-not $py) {
    Die "파이썬이 없습니다.`n  https://www.python.org/downloads/ 에서 설치하고,`n  설치 화면 맨 아래 [Add python.exe to PATH] 를 꼭 체크하세요."
}

# 2. 꾸러미
Info "필요한 꾸러미를 확인하는 중..."
& $py -c "import click, PIL, requests, boto3" 2>$null
if ($LASTEXITCODE -ne 0) {
    Info "처음이라 설치가 필요합니다. 1~2분 걸립니다..."
    & $py -m pip install --quiet --disable-pip-version-check -r (Join-Path $Root "requirements.txt")
    if ($LASTEXITCODE -ne 0) { Die "꾸러미 설치에 실패했습니다." }
    Ok "설치 완료"
} else {
    Ok "꾸러미 준비됨"
}

# 3. .env
$envFile = Join-Path $Root ".env"
if (-not (Test-Path $envFile)) {
    $sample = Join-Path $Root ".env.example"
    if (Test-Path $sample) {
        Copy-Item $sample $envFile
        Warn ".env 를 새로 만들었습니다. 작업실의 [설정] 탭에서 fal 키를 넣으세요."
    }
}

# 4. ffmpeg (없어도 켜지지만 영상 합치기에서 막힌다)
$ff = Get-Command ffmpeg -ErrorAction SilentlyContinue
if ($ff) { Ok "ffmpeg 확인" } else { Warn "ffmpeg 이 없습니다. 작업실 [설정] 탭에서 안내를 확인하세요." }

Write-Host "`n작업실을 엽니다. 브라우저가 자동으로 열립니다." -ForegroundColor Green
Write-Host "  이 검은 창을 닫으면 작업실도 꺼집니다.`n" -ForegroundColor DarkGray

& $py (Join-Path $Root "main.py") ui

Write-Host ""
Read-Host "작업실이 종료되었습니다. 엔터를 누르면 닫힙니다"
