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

# 설치 과정을 파일로 남긴다.
#
# 검은 창은 닫히면 사라진다. 원장이 "설치가 안 된다"고 할 때 화면을 사진으로
# 찍어 보내지 않으면 무슨 일이 있었는지 알 방법이 없다. 이 파일 하나만 보내면 된다.
try { Start-Transcript -Path (Join-Path $PSScriptRoot "설치기록.txt") -Force | Out-Null } catch { }

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

# 파이썬을 대신 깔아 준다.
#
# winget 이 있으면 그것이 가장 깔끔하다. 다만 회사 PC·구형 윈도우10 에는 winget 이
# 없는 경우가 흔하다. 그때 브라우저로 보내면 원장은 설치창의 체크박스 하나 때문에
# 또 막힌다("Add python.exe to PATH"). 그래서 python.org 의 공식 설치 파일을
# 직접 받아 조용히 실행한다 — PATH 등록까지 우리가 켜 준다.

# 방금 깐 파이썬은 이 창의 PATH 에 아직 없다 — 다시 읽어 온 뒤 찾는다.
function Find-PythonAfterRefresh {
    $env:Path = [Environment]::GetEnvironmentVariable("Path", "Machine") + ";" +
                [Environment]::GetEnvironmentVariable("Path", "User")
    $script:py = Find-Python
    return $script:py
}

function Install-Python {
    $saved = $ErrorActionPreference
    $ErrorActionPreference = "Continue"
    try {
        if (Get-Command winget -ErrorAction SilentlyContinue) {
            Write-Host "  파이썬을 내려받아 설치합니다. 몇 분 걸립니다..." -ForegroundColor White
            winget install --id Python.Python.3.12 --exact --source winget --accept-package-agreements --accept-source-agreements
            if (Find-PythonAfterRefresh) { return $true }
            Write-Host "  다른 방법으로 다시 시도합니다..." -ForegroundColor DarkGray
        }

        # winget 이 없거나 실패했다 — 설치 파일을 직접 받는다.
        $arch = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" }
                elseif ([Environment]::Is64BitOperatingSystem) { "amd64" }
                else { "" }
        # 판올림이 잦아 한 주소를 박아 두면 언젠가 죽는다. 있는 것을 찾아 쓴다.
        $vers = @("3.12.12", "3.12.11", "3.12.10", "3.12.9", "3.12.8", "3.12.7", "3.12.3")
        $url = $null
        foreach ($v in $vers) {
            $u = if ($arch) { "https://www.python.org/ftp/python/$v/python-$v-$arch.exe" }
                 else       { "https://www.python.org/ftp/python/$v/python-$v.exe" }
            try {
                Invoke-WebRequest -Uri $u -Method Head -UseBasicParsing -TimeoutSec 20 | Out-Null
                $url = $u
                break
            } catch { continue }
        }
        if (-not $url) {
            Write-Host "  python.org 에 연결하지 못했습니다(회사 방화벽일 수 있습니다)." -ForegroundColor Yellow
            return $false
        }

        $exe = Join-Path $env:TEMP "python-setup.exe"
        Write-Host "  파이썬을 내려받습니다 (약 25MB)..." -ForegroundColor White
        try {
            $keep = $ProgressPreference
            $ProgressPreference = "SilentlyContinue"
            Invoke-WebRequest -Uri $url -OutFile $exe -UseBasicParsing -TimeoutSec 900
            $ProgressPreference = $keep
        } catch {
            Write-Host "  내려받지 못했습니다: $_" -ForegroundColor Yellow
            return $false
        }

        Write-Host "  설치 중입니다. 2~3분 걸립니다. 창을 닫지 마십시오..." -ForegroundColor White
        # PrependPath=1 이 바로 그 체크박스다. 원장이 놓쳐서 막히던 자리를 여기서 없앤다.
        $flags = "/quiet InstallAllUsers=0 PrependPath=1 Include_launcher=1 Include_test=0 Include_doc=0"
        $proc = Start-Process -FilePath $exe -ArgumentList $flags -Wait -PassThru
        Remove-Item $exe -ErrorAction SilentlyContinue
        if ($proc.ExitCode -ne 0 -and $proc.ExitCode -ne 3010) {
            Write-Host "  설치 프로그램이 오류로 끝났습니다(코드 $($proc.ExitCode))." -ForegroundColor Yellow
            return $false
        }
        if (Find-PythonAfterRefresh) { return $true }
        return $false
    } finally { $ErrorActionPreference = $saved }
}

Step "1/7 파이썬 확인"
$py = Find-Python

if (-not $py) {
    Write-Host ""
    Write-Host "  이 컴퓨터에 파이썬이 없습니다." -ForegroundColor Yellow
    Write-Host "  콩쿨 작곡기가 돌아가려면 파이썬 3.12 이상이 필요합니다(무료)."
    Write-Host "  지금 대신 설치해 드리겠습니다 - 그대로 두고 기다리십시오." -ForegroundColor White
    Write-Host ""
    if (Install-Python) {
        $py = $script:py
        Write-Host "  파이썬이 설치되었습니다." -ForegroundColor Green
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

Step "3/7 필요한 부품 내려받기"
# 여기가 가장 오래 걸린다. -q 로 조용히 돌리면 화면이 몇 분 동안 아무것도 안 바뀌어서
# 멈춘 줄 알고 창을 닫게 된다(실제로 그랬다). 그래서 pip 의 진행 표시를 그대로 보여 준다.
Write-Host "      2~5분쯤 걸립니다. 줄이 계속 올라가면 잘 되고 있는 것입니다." -ForegroundColor DarkGray
Write-Host "      창을 닫지 마십시오." -ForegroundColor DarkGray
# 원장 PC 용 목록을 쓴다. 전체 목록에는 도커 배포용(PostgreSQL·Celery·Redis)과
# 코드가 쓰지도 않는 3D 도구(vtk, 내려받기 133MB)가 들어 있어 다섯 배 느리다.
& $vpy -m pip install --disable-pip-version-check --upgrade pip
& $vpy -m pip install --disable-pip-version-check -r server\requirements-desktop.txt
if ($LASTEXITCODE -ne 0) { Die "부품을 내려받지 못했다 - 인터넷 연결을 확인하고 다시 실행하라" }
Ok "완료"

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
# pythonw 가 없으면 python 으로라도 만든다. 다만 **절대 경로**여야 한다 —
# 바로가기에 상대 경로를 넣으면 윈도우가 아무 말 없이 아무것도 하지 않는다.
if (-not (Test-Path $pyw)) { $pyw = Join-Path $PSScriptRoot ".venv\Scripts\python.exe" }
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

# 어느 판을 깔았는지 남긴다. '업데이트.bat' 이 이것을 보고 "이미 최신입니다" 를 판단한다.
try {
    $head = Invoke-RestMethod -TimeoutSec 15 -Headers @{ "User-Agent" = "ConcoursComposer" } `
        -Uri "https://api.github.com/repos/himan98hkt-prog/-/commits/claude/program-development-yi0956"
    Set-Content -Path (Join-Path $PSScriptRoot "설치버전.txt") -Value "$($head.sha)" -Encoding UTF8
} catch { }

Step "7/7 자기 점검"
& $vpy scripts\self_check.py
if ($LASTEXITCODE -ne 0) { Die "자기 점검 실패" }
Ok "정상"

Write-Host ""
Write-Host "설치 끝." -ForegroundColor White
Write-Host "  바탕화면의 '콩쿨 작곡기' 아이콘을 두 번 누르십시오."
Write-Host "  아이콘을 눌러도 아무 변화가 없으면 이 폴더의 '실행.bat' 을 두 번 누르십시오 -"
Write-Host "  창이 열린 채로 돌아서 무엇이 잘못됐는지 글씨로 보입니다."
Write-Host "  이 폴더: $PSScriptRoot" -ForegroundColor DarkGray
Write-Host ""
try { Stop-Transcript | Out-Null } catch { }
