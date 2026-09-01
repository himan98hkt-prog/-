# ConcoursComposer 설치 - Windows (PowerShell)
#
# 하는 일: 파이썬 확인 -> 가상환경 -> 의존성 -> .env 생성 -> 자기 점검.
# 인터넷과 Python 3.12 이상만 있으면 된다. 관리자 권한은 필요 없다.
#
# 실행이 막히면 PowerShell 에서 한 번만:
#   Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
$ErrorActionPreference = "Stop"
Set-Location $PSScriptRoot

function Step($m) { Write-Host $m -ForegroundColor White }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Die($m)  { Write-Host "  X   $m" -ForegroundColor Red; exit 1 }

Step "1/5 파이썬 확인"
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

Step "2/5 가상환경"
if (-not (Test-Path ".venv")) {
    $exe, $arg = $py.Split(" ", 2)
    if ($arg) { & $exe $arg -m venv .venv } else { & $exe -m venv .venv }
}
$vpy = ".\.venv\Scripts\python.exe"
if (-not (Test-Path $vpy)) { Die "가상환경을 만들지 못했다" }
Ok ".venv"

Step "3/5 의존성 설치 (처음 한 번은 몇 분 걸린다)"
& $vpy -m pip install -q --upgrade pip
& $vpy -m pip install -q -r server\requirements.txt
if ($LASTEXITCODE -ne 0) { Die "의존성 설치 실패" }
Ok "설치 완료"

Step "4/5 설정 파일"
if (Test-Path ".env") {
    Ok ".env 가 이미 있다 - 건드리지 않는다"
} else {
    Copy-Item ".env.example" ".env"
    Ok ".env 를 만들었다"
    Write-Host "      API 키가 없어도 규칙 기반 스텁으로 전 과정이 돌아간다." -ForegroundColor DarkGray
    Write-Host "      실제 작곡 품질을 쓰려면 .env 의 ANTHROPIC_API_KEY 를 채워라." -ForegroundColor DarkGray
}

Step "5/5 자기 점검"
& $vpy scripts\self_check.py
if ($LASTEXITCODE -ne 0) { Die "자기 점검 실패" }
Ok "정상"

Write-Host ""
Write-Host "설치 끝. 다음으로 실행한다:" -ForegroundColor White
Write-Host "  .\start.ps1"
Write-Host ""
