# AI DEOKHU — 내 PC 영상 엔진(LTX-2.5) 설치
#
#   tools\ltx_setup.bat 을 더블클릭하면 이 스크립트가 돈다.
#   그래픽카드 확인 -> LTX-2 코드 -> 파이썬 환경(uv) -> 모델(약 66GB) -> Real-ESRGAN(선택)
#
#   중간에 끊겨도 다시 실행하면 이어서 받는다. 이미 있는 것은 건너뛴다.

$ErrorActionPreference = "Stop"
[Console]::OutputEncoding = [Text.Encoding]::UTF8

$App = Split-Path $PSScriptRoot -Parent

function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Info($m) { Write-Host "  ..  $m" -ForegroundColor Cyan }
function Warn($m) { Write-Host "  !   $m" -ForegroundColor Yellow }
function Die($m)  { Write-Host "`n  X   $m" -ForegroundColor Red; Read-Host "`n엔터를 누르면 닫힙니다"; exit 1 }

Write-Host "`nAI DEOKHU — 내 PC 영상 엔진(LTX-2.5) 설치" -ForegroundColor White
Write-Host "한 번만 하면 됩니다. 인터넷 속도에 따라 30분~몇 시간 걸립니다.`n"

# ── 1. 그래픽카드 ─────────────────────────────────────────────────────
$smi = Get-Command nvidia-smi -ErrorAction SilentlyContinue
if (-not $smi) {
    Die ("NVIDIA 그래픽카드(또는 드라이버)를 찾지 못했습니다.`n" +
         "  LTX-2.5 는 NVIDIA 그래픽카드가 있어야 돕니다.`n" +
         "  그래픽카드가 있다면 https://www.nvidia.com/drivers 에서 드라이버를 설치하세요.")
}
$gpuName = (& nvidia-smi --query-gpu=name --format=csv,noheader | Select-Object -First 1).Trim()
$gpuMem = [int]((& nvidia-smi --query-gpu=memory.total --format=csv,noheader,nounits | Select-Object -First 1).Trim())
$gb = [math]::Round($gpuMem / 1024)
Info "그래픽카드: $gpuName (${gb}GB)"
$ramGb = [math]::Round((Get-CimInstance Win32_ComputerSystem).TotalPhysicalMemory / 1GB)
Info "시스템 메모리: ${ramGb}GB"
if ($gb -lt 15) {
    # Lightricks 의 LTX Desktop 도 15GB 미만에서는 내 PC 생성을 막고 클라우드로 돌린다.
    # 여기서 70GB 를 받아 봐야 매일 아침 예약이 매일 실패한다.
    Die ("${gb}GB 그래픽카드로는 LTX-2.5 를 내 PC 에서 돌릴 수 없습니다 (15GB 이상 필요).`n" +
         "  Lightricks 의 LTX Desktop 도 이 크기에서는 클라우드(LTX API, 유료)로 만듭니다.`n" +
         "  70GB 를 받지 않도록 여기서 멈춥니다. 클라우드(fal) 엔진은 그대로 쓸 수 있습니다.")
} elseif ($gb -lt 30) {
    Warn "${gb}GB 는 모델을 시스템 메모리에 두고 나눠 돌립니다. 느리지만 돕니다."
    if ($ramGb -lt 40) { Warn "시스템 메모리가 ${ramGb}GB 라 디스크까지 써서 더 느립니다. 64GB 를 권장합니다." }
} else {
    Ok "권장 사양을 만족합니다"
}
Warn "LTX-2 는 최신 CUDA 를 씁니다. NVIDIA 드라이버를 최신으로 올려 두세요."

# ── 2. 설치 위치 · 디스크 ─────────────────────────────────────────────
$Target = if ($env:LTX_DIR) { $env:LTX_DIR } else { "C:\LTX-2" }
while ($true) {
    $qual = Split-Path $Target -Qualifier
    $drive = Get-PSDrive ($qual.TrimEnd(":")) -ErrorAction SilentlyContinue
    $free = if ($drive) { [math]::Round($drive.Free / 1GB) } else { 0 }
    $have = Test-Path (Join-Path $Target "models\ltx-2.5")
    if ($free -ge 100 -or $have) { break }
    Warn "$qual 드라이브 남은 공간 ${free}GB — 100GB 이상 필요합니다."
    $Target = Read-Host "  다른 드라이브에 설치할 경로를 넣으세요 (예: D:\LTX-2)"
    if (-not $Target) { Die "설치 위치가 없습니다." }
}
Ok "설치 위치: $Target"

# ── 3. LTX-2 코드 (git 없이 zip 으로) ─────────────────────────────────
if (Test-Path (Join-Path $Target "pyproject.toml")) {
    Ok "LTX-2 코드가 이미 있습니다"
} else {
    Info "LTX-2 코드를 받는 중..."
    $zip = Join-Path $env:TEMP "ltx2_main.zip"
    $tmp = Join-Path $env:TEMP "ltx2_unzip"
    Invoke-WebRequest "https://github.com/Lightricks/LTX-2/archive/refs/heads/main.zip" -OutFile $zip -UseBasicParsing
    Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Expand-Archive $zip $tmp -Force
    $src = Get-ChildItem $tmp -Directory | Select-Object -First 1
    New-Item -ItemType Directory -Force $Target | Out-Null
    Copy-Item (Join-Path $src.FullName "*") $Target -Recurse -Force
    Remove-Item $zip, $tmp -Recurse -Force -ErrorAction SilentlyContinue
    Ok "LTX-2 코드를 받았습니다"
}

# ── 4. uv (파이썬 환경 관리 도구) ─────────────────────────────────────
$uv = Get-Command uv -ErrorAction SilentlyContinue
if (-not $uv) {
    Info "uv 를 설치하는 중..."
    powershell -NoProfile -ExecutionPolicy Bypass -Command "irm https://astral.sh/uv/install.ps1 | iex"
    $env:Path = "$env:USERPROFILE\.local\bin;$env:Path"
    $uv = Get-Command uv -ErrorAction SilentlyContinue
    if (-not $uv) { Die "uv 설치에 실패했습니다. https://docs.astral.sh/uv/ 를 참고하세요." }
}
Ok "uv 준비됨"

# ── 5. 파이썬 환경 (torch 등 수 GB) ───────────────────────────────────
Info "LTX 파이썬 환경을 만드는 중... (처음에는 10분 이상 걸립니다)"
Push-Location $Target
try {
    & uv sync
    if ($LASTEXITCODE -ne 0) { Die "파이썬 환경을 만들지 못했습니다 (uv sync)." }
} finally { Pop-Location }
Ok "파이썬 환경 준비됨"

# ── 6. 모델 (약 66GB, 허깅페이스 약관 동의 필요) ──────────────────────
$Models = Join-Path $Target "models\ltx-2.5"
$files = @(
    "diffusion_models/ltx-2.5-22b-distilled-transformer-bf16.safetensors",
    "text_encoders/gemma4-12b-with-proj-ltx-2.5-bf16.safetensors",
    "vae/ltx-2.5-video-vae-conv-bf16.safetensors",
    "vae/ltx-2.5-audio-vae-bf16.safetensors",
    "latent_upscale_models/ltx-2.5-latent-spatial-upscaler-x2-bf16-1.0.safetensors"
)
$missing = @($files | Where-Object { -not (Test-Path (Join-Path $Models $_)) })
if ($missing.Count -eq 0) {
    Ok "모델 파일이 모두 있습니다"
} else {
    Write-Host ""
    Write-Host "  모델을 받으려면 허깅페이스 약관 동의와 토큰이 필요합니다 (무료)." -ForegroundColor White
    Write-Host "   1) 방금 열린 페이지에서 로그인 -> 약관에 동의(Agree)"
    Write-Host "   2) https://huggingface.co/settings/tokens -> Create new token -> Read"
    Write-Host "   3) 만든 토큰(hf_...)을 아래에 붙여넣기"
    Start-Process "https://huggingface.co/Lightricks/LTX-2.5"
    $sec = Read-Host "`n  토큰 (화면에 안 보입니다)" -AsSecureString
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($sec)
    $env:HF_TOKEN = [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr)
    [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr)
    Info "모델을 받는 중... (끊겨도 다시 실행하면 이어서 받습니다)"
    Push-Location $Target
    try {
        & uv run --with "huggingface_hub[cli]" hf download Lightricks/LTX-2.5 @missing --local-dir "models/ltx-2.5"
        $code = $LASTEXITCODE
    } finally {
        Pop-Location
        # 토큰은 이 창에서만 쓰고 어디에도 저장하지 않는다
        Remove-Item Env:HF_TOKEN -ErrorAction SilentlyContinue
    }
    if ($code -ne 0) {
        Die ("모델을 받지 못했습니다.`n" +
             "  401/403 이면 약관 동의를 안 했거나 토큰 권한이 Read 가 아닙니다.")
    }
    Ok "모델을 받았습니다"
}

# ── 7. AI DEOKHU 에 위치 알려주기 ─────────────────────────────────────
if ($Target -ne "C:\LTX-2") {
    $envFile = Join-Path $App ".env"
    $lines = @()
    if (Test-Path $envFile) { $lines = @(Get-Content $envFile -Encoding UTF8) }
    $lines = @($lines | Where-Object { $_ -notmatch "^LTX_DIR=" }) + "LTX_DIR=$Target"
    [IO.File]::WriteAllLines($envFile, $lines, (New-Object Text.UTF8Encoding $false))
    Ok ".env 에 LTX_DIR=$Target 을 적었습니다"
}

# ── 8. Real-ESRGAN (선택) ─────────────────────────────────────────────
$esrDir = Join-Path $PSScriptRoot "realesrgan"
if (Get-ChildItem $esrDir -Recurse -Filter "realesrgan-ncnn-vulkan.exe" -ErrorAction SilentlyContinue) {
    Ok "Real-ESRGAN 이 이미 있습니다"
} else {
    $ans = Read-Host "`n  Real-ESRGAN(한 번 더 업스케일, 45MB)도 받을까요? (Y/n)"
    if ($ans -ne "n") {
        $zip = Join-Path $env:TEMP "realesrgan.zip"
        Invoke-WebRequest "https://github.com/xinntao/Real-ESRGAN/releases/download/v0.2.5.0/realesrgan-ncnn-vulkan-20220424-windows.zip" -OutFile $zip -UseBasicParsing
        New-Item -ItemType Directory -Force $esrDir | Out-Null
        Expand-Archive $zip $esrDir -Force
        Remove-Item $zip -Force -ErrorAction SilentlyContinue
        Ok "Real-ESRGAN 을 받았습니다"
    }
}

Write-Host "`n설치가 끝났습니다." -ForegroundColor Green
Write-Host "  작업실 -> [자동 업로드] 탭 -> 영상 엔진 -> [내 PC] 를 고르세요." -ForegroundColor White
Write-Host "  처음 한 편은 [싸게 먼저 시험하기] 로 짧게 뽑아 보는 것을 권합니다.`n" -ForegroundColor DarkGray
Read-Host "엔터를 누르면 닫힙니다"
