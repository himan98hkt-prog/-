# AutoShorts-Engine 설치 (Windows PowerShell)
#   PowerShell 에서:  powershell -ExecutionPolicy Bypass -File install.ps1
$ErrorActionPreference = "Stop"
Set-Location -Path $PSScriptRoot

Write-Host ""
Write-Host "=== AutoShorts-Engine 설치 ===" -ForegroundColor Cyan
Write-Host ""

# ── 1. 파이썬 확인 ────────────────────────────────────────
$python = $null
foreach ($candidate in @("python", "python3", "py")) {
    if (Get-Command $candidate -ErrorAction SilentlyContinue) { $python = $candidate; break }
}
if (-not $python) {
    Write-Host "X 파이썬을 찾을 수 없습니다." -ForegroundColor Red
    Write-Host "  https://www.python.org/downloads/ 에서 3.10 이상을 설치하세요."
    Write-Host "  설치할 때 'Add Python to PATH' 를 반드시 체크하세요."
    exit 1
}
$version = & $python -c "import sys; print('%d.%d' % sys.version_info[:2])"
Write-Host "  파이썬 $version"
& $python -c "import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE -ne 0) {
    Write-Host "X 파이썬 3.10 이상이 필요합니다 (현재 $version)." -ForegroundColor Red
    exit 1
}

# ── 2. FFmpeg 확인 ────────────────────────────────────────
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "  FFmpeg 확인됨"
} else {
    Write-Host ""
    Write-Host "! FFmpeg 가 없습니다. 영상 편집에 반드시 필요합니다." -ForegroundColor Yellow
    Write-Host "    winget install Gyan.FFmpeg"
    Write-Host "  설치 후 새 PowerShell 창을 열어야 인식됩니다."
    Write-Host ""
    $reply = Read-Host "  FFmpeg 없이 계속할까요? (y/N)"
    if ($reply -ne "y" -and $reply -ne "Y") { exit 1 }
}

# ── 3. 가상환경 ───────────────────────────────────────────
if (-not (Test-Path ".venv")) {
    Write-Host ""
    Write-Host "  가상환경을 만듭니다 (.venv)..."
    & $python -m venv .venv
}
$venvPython = Join-Path $PSScriptRoot ".venv\Scripts\python.exe"
& $venvPython -m pip install --quiet --upgrade pip

# ── 4. 의존성 ─────────────────────────────────────────────
Write-Host "  의존성을 설치합니다. 처음에는 몇 분 걸립니다..."
& $venvPython -m pip install --quiet -r requirements.txt
& $venvPython -m pip install --quiet -e .

Write-Host ""
Write-Host "설치 완료" -ForegroundColor Green
Write-Host ""
Write-Host "다음 단계"
Write-Host "  1) .\.venv\Scripts\Activate.ps1     # 가상환경 활성화 (새 창마다)"
Write-Host "  2) autoshorts setup                 # API 키 입력"
Write-Host "  3) autoshorts doctor                # 설치 상태 점검"
Write-Host "  4) autoshorts ui                    # 웹 화면 -> http://127.0.0.1:7860"
Write-Host ""
Write-Host "업로드까지 쓰시려면"
Write-Host "  autoshorts login                    # 최초 1회 브라우저 로그인"
Write-Host '  autoshorts schedule add "재테크" --at 09:00 -- --upload'
Write-Host ""
