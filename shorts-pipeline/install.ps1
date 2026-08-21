# AI DEOKHU 자동 설치 (Windows)
#
#   1) 시작 버튼 우클릭 -> "터미널(관리자)"
#   2) 이 파일이 있는 폴더로 이동한 뒤 아래를 실행
#        powershell -ExecutionPolicy Bypass -File install.ps1
#
# Python 과 ffmpeg 을 winget 으로 설치하고, 파이썬 패키지까지 넣는다.

$ErrorActionPreference = "Stop"

function Step($n, $msg) { Write-Host "`n[$n] $msg" -ForegroundColor Cyan }
function Ok($msg)       { Write-Host "  OK  $msg" -ForegroundColor Green }
function Warn($msg)     { Write-Host "  !   $msg" -ForegroundColor Yellow }
function Die($msg)      { Write-Host "`n  X   $msg" -ForegroundColor Red; exit 1 }

Write-Host "AI DEOKHU 설치를 시작합니다" -ForegroundColor White

# ── winget 확인 ──────────────────────────────────────────────────────
Step 1 "winget 확인"
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Die @"
winget 이 없습니다. Windows 10 구버전일 수 있습니다.
  Microsoft Store 에서 '앱 설치 관리자'(App Installer) 를 설치한 뒤 다시 실행하거나,
  세팅 페이지의 '수동 설치' 안내를 따라 주세요.
"@
}
Ok "winget 사용 가능"

# ── Python ──────────────────────────────────────────────────────────
Step 2 "Python 설치"
if (Get-Command python -ErrorAction SilentlyContinue) {
    Ok "이미 설치됨 — $(python --version 2>&1)"
} else {
    winget install --id Python.Python.3.12 -e --accept-source-agreements --accept-package-agreements
    Ok "설치 완료"
}

# ── ffmpeg ──────────────────────────────────────────────────────────
Step 3 "ffmpeg 설치"
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Ok "이미 설치됨"
} else {
    winget install --id Gyan.FFmpeg -e --accept-source-agreements --accept-package-agreements
    Ok "설치 완료"
}

# winget 이 방금 넣은 PATH 를 현재 창에도 반영한다
$env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
            [Environment]::GetEnvironmentVariable("Path", "User")

# ── 파이썬 패키지 ────────────────────────────────────────────────────
Step 4 "파이썬 패키지 설치"
$req = Join-Path $PSScriptRoot "requirements.txt"
if (-not (Test-Path $req)) {
    Die "requirements.txt 를 찾을 수 없습니다. 이 스크립트를 shorts-pipeline 폴더 안에서 실행하세요."
}
python -m pip install --upgrade pip --quiet
python -m pip install -r $req
Ok "패키지 설치 완료"

# ── .env ────────────────────────────────────────────────────────────
Step 5 ".env 파일 준비"
$envFile = Join-Path $PSScriptRoot ".env"
$example  = Join-Path $PSScriptRoot ".env.example"
if (Test-Path $envFile) {
    Ok "이미 있습니다 (덮어쓰지 않음)"
} else {
    Copy-Item $example $envFile
    Ok ".env 생성 — 메모장으로 열어 FAL_API_KEY 를 채우세요"
}

# ── 확인 ────────────────────────────────────────────────────────────
Step 6 "설치 확인"
$fail = $false
foreach ($c in @("python", "ffmpeg")) {
    if (Get-Command $c -ErrorAction SilentlyContinue) { Ok "$c 확인됨" }
    else { Warn "$c 을(를) 아직 찾지 못합니다"; $fail = $true }
}

Write-Host ""
if ($fail) {
    Warn @"
설치는 됐지만 이 창에서 아직 인식되지 않습니다. 정상입니다.
  이 창을 완전히 닫고 새 터미널을 연 뒤 아래를 실행하세요.
"@
} else {
    Write-Host "설치가 끝났습니다." -ForegroundColor Green
}
Write-Host "  python main.py doctor" -ForegroundColor White
Write-Host ""
