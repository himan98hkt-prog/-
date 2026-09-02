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

Step "1/7 파이썬 확인"
$py = $null
foreach ($c in @("py -3.13", "py -3.12", "python3", "python")) {
    $exe, $arg = $c.Split(" ", 2)
    if (Get-Command $exe -ErrorAction SilentlyContinue) {
        $check = if ($arg) { & $exe $arg -c "import sys;print(sys.version_info>=(3,12))" 2>$null }
                 else      { & $exe      -c "import sys;print(sys.version_info>=(3,12))" 2>$null }
        if ($check -eq "True") { $py = $c; break }
    }
}
if (-not $py) { Die "Python 3.12 이상이 필요하다. https://www.python.org/downloads/ 에서 설치할 때 'Add python.exe to PATH' 를 반드시 체크하라." }
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
