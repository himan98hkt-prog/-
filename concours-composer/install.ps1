# ConcoursComposer 설치 - Windows (PowerShell)
#
# 하는 일: 파이썬 확인 -> 가상환경 -> 의존성 -> .env 생성 -> 자기 점검.
# 인터넷과 Python 3.12 이상만 있으면 된다. 관리자 권한은 필요 없다.
#
# 이 파일을 직접 실행하다 막혔다면(PSSecurityException) 두 가지 길이 있다.
#   가장 쉬운 길: 이 폴더의 '설치.bat' 을 두 번 누른다.
#   PowerShell 에서 하려면 한 번만:  Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($m) { Write-Host $m -ForegroundColor White }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Die($m)  { Write-Host "  X   $m" -ForegroundColor Red; exit 1 }

# 파이썬을 찾는다.
#
# 여기서 지켜야 할 것이 하나 있다 — **찾는 중에 나는 오류로 설치가 멈추면 안 된다.**
# py.exe 는 맞는 버전이 없으면 붉은 글씨를 뱉는데, $ErrorActionPreference = "Stop" 아래에서는
# 그것이 스크립트를 통째로 중단시킨다. 원장은 "파이썬을 깔아야 한다"는 안내 대신
# 알 수 없는 붉은 글씨만 보게 된다. 그래서 찾는 동안만 Stop 을 풀고 오류를 삼킨다.
function Find-Python {
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        foreach ($c in @("py -3.13", "py -3.12", "py -3", "python3", "python")) {
            $exe, $arg = $c.Split(" ", 2)
            if (-not (Get-Command $exe -ErrorAction SilentlyContinue)) { continue }
            try {
                $out = if ($arg) { & $exe $arg -c "import sys;print(sys.version_info>=(3,12))" 2>$null }
                       else      { & $exe      -c "import sys;print(sys.version_info>=(3,12))" 2>$null }
            } catch { continue }
            if ($LASTEXITCODE -eq 0 -and "$out".Trim() -eq "True") { return $c }
        }
    } finally { $ErrorActionPreference = $saved }
    return $null
}

Step "1/7 파이썬 확인"
$py = Find-Python

if (-not $py) {
    Write-Host ""
    Write-Host "  이 컴퓨터에 파이썬이 없습니다." -ForegroundColor Yellow
    Write-Host "  콩쿨 작곡기가 돌아가려면 파이썬 3.12 이상이 필요합니다(무료)."
    Write-Host ""

    # winget 이 있으면 여기서 바로 깔아 준다. 원장이 브라우저를 열고 설치 창을
    # 헤매는 단계를 통째로 없애는 것이 목적이다.
    $winget = Get-Command winget -ErrorAction SilentlyContinue
    if ($winget) {
        $ans = Read-Host "  지금 자동으로 설치할까요? (Y = 예 / N = 아니요)"
        if ($ans -match "^[Yy]") {
            Write-Host "  파이썬을 내려받아 설치합니다. 몇 분 걸립니다..." -ForegroundColor White
            $saved = $ErrorActionPreference
            $ErrorActionPreference = "Continue"
            winget install --id Python.Python.3.12 --exact --source winget --accept-package-agreements --accept-source-agreements
            $ErrorActionPreference = $saved
            # 방금 깐 파이썬은 이 창의 PATH 에 아직 없다 — 다시 읽어 온다.
            $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" + [Environment]::GetEnvironmentVariable("Path", "User")
            $py = Find-Python
            if ($py) { Write-Host "  파이썬이 설치되었습니다." -ForegroundColor Green }
        }
    }
}

if (-not $py) {
    Write-Host ""
    Write-Host "  ---------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host "   파이썬을 직접 설치하신 뒤, 이 창을 닫고 다시 해 주십시오." -ForegroundColor Yellow
    Write-Host "  ---------------------------------------------------------------" -ForegroundColor Yellow
    Write-Host "   1. 아래 주소를 브라우저에 붙여넣습니다"
    Write-Host "        https://www.python.org/downloads/" -ForegroundColor Cyan
    Write-Host "   2. 노란 [Download Python] 단추를 누릅니다"
    Write-Host "   3. 받은 파일을 실행하고, 설치창 맨 아래"
    Write-Host "        [v] Add python.exe to PATH" -ForegroundColor Cyan
    Write-Host "      를 반드시 체크한 뒤 [Install Now] 를 누릅니다"
    Write-Host "   4. 설치가 끝나면 이 폴더의 '설치.bat' 을 다시 두 번 누릅니다"
    Write-Host ""
    Write-Host "   3번의 체크를 빠뜨리면 설치해도 여기서 또 막힙니다." -ForegroundColor Yellow
    Write-Host ""
    exit 1
}
Ok $py

Step "2/7 가상환경"
if (-not (Test-Path ".venv")) {
    $exe, $arg = $py.Split(" ", 2)
    if ($arg) { & $exe $arg -m venv .venv } else { & $exe -m venv .venv }
}
$vpy = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $vpy)) { Die "가상환경을 만들지 못했다" }
Ok ".venv"

Step "3/7 의존성 설치 (처음 한 번은 몇 분 걸린다)"
& $vpy -m pip install -q --upgrade pip
& $vpy -m pip install -q -r server\requirements.txt
if ($LASTEXITCODE -ne 0) { Die "의존성 설치 실패" }
Ok "설치 완료"

Step "4/7 설정 파일"
if (Test-Path ".env") {
    Ok ".env 가 이미 있다 - 건드리지 않는다"
} else {
    Copy-Item ".env.example" ".env"
    Ok ".env 를 만들었다"
    Write-Host "      API 키가 없어도 규칙 기반 스텁으로 전 과정이 돌아간다." -ForegroundColor DarkGray
    Write-Host "      실제 작곡 품질을 쓰려면 .env 의 ANTHROPIC_API_KEY 를 채워라." -ForegroundColor DarkGray
}

Step "5/7 악보 렌더러 내려받기 (없어도 프로그램은 돈다)"
& $vpy scripts\fetch_vendor.py
Ok "완료"

Step "6/7 바탕화면 아이콘 만들기"
# 원장이 하는 일은 아이콘 한 번 누르는 것뿐이어야 한다. 검은 창도 주소 입력도 없다.
$pyw = Join-Path $PSScriptRoot ".venv\Scripts\pythonw.exe"
if (-not (Test-Path $pyw)) { $pyw = $vpy }   # pythonw 가 없으면 python 으로라도 만든다
$launch = Join-Path $PSScriptRoot "scripts\launch.py"
$icon   = Join-Path $PSScriptRoot "assets\app\icon.ico"
try {
    $shell = New-Object -ComObject WScript.Shell
    $targets = @(
        (Join-Path ([Environment]::GetFolderPath("Desktop")) "콩쿨 작곡기.lnk"),
        (Join-Path ([Environment]::GetFolderPath("Programs")) "콩쿨 작곡기.lnk")
    )
    foreach ($t in $targets) {
        $dir = Split-Path $t -Parent
        if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
        $lnk = $shell.CreateShortcut($t)
        $lnk.TargetPath       = $pyw
        $lnk.Arguments        = "`"$launch`""
        $lnk.WorkingDirectory = $PSScriptRoot
        $lnk.IconLocation     = "$icon,0"
        $lnk.Description      = "콩쿨 작곡기 — 컨셉을 고르면 심사까지 마친 곡이 나옵니다"
        $lnk.Save()
    }
    Ok "바탕화면과 시작 메뉴에 '콩쿨 작곡기' 아이콘을 만들었다"
} catch {
    Write-Host "      아이콘을 만들지 못했다 — .\start.ps1 로도 실행된다: $_" -ForegroundColor DarkGray
}

Step "7/7 자기 점검"
& $vpy scripts\self_check.py
if ($LASTEXITCODE -ne 0) { Die "자기 점검 실패" }
Ok "정상"

Write-Host ""
Write-Host "설치 끝." -ForegroundColor White
Write-Host "  바탕화면의 '콩쿨 작곡기' 아이콘을 두 번 누르십시오."
Write-Host "  (아이콘이 없으면 이 폴더에서  .\start.ps1  을 실행하십시오)"
Write-Host ""
