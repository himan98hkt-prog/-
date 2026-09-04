# 새 판으로 한 번에 올린다.
#
# 지금까지 원장님은 새 판이 나올 때마다 폴더를 지우고, 다시 받고, 압축을 풀고,
# 설치를 처음부터 다시 하셨다. 손이 많이 가는 것보다 나쁜 것은 **위험하다**는 것이다 —
# 폴더를 지우는 습관은 언젠가 지우면 안 되는 것을 지운다. 실제로 그렇게 곡을 잃을 뻔했다.
#
# 그래서 이 스크립트가 대신 한다. 원칙은 셋이다.
#
#   1. **덮어쓴다, 지우지 않는다.** 프로그램 파일만 새것으로 바꾼다.
#   2. **원장님 것은 손대지 않는다.** API 키(.env), 만든 곡, 참고 악보, 받아 둔
#      악보 렌더러는 그대로 둔다.
#   3. **되돌릴 수 있게 한다.** 바꾸기 전 폴더를 통째로 옆에 복사해 둔다.
#
# 만든 곡은 이미 프로그램 폴더 **밖**(AppData)에 저장되므로 여기서 위험하지 않다.
# 그래도 사본은 뜬다 — 되돌릴 길이 없는 작업은 하지 않는다.

$ErrorActionPreference = "Stop"

# **창이 없어도 죽지 않는다.**
#
# 이 줄이 원장님의 "지금 올리기 눌렀는데 움직임이 없다" 의 절반이었다. 화면 단추가
# 이 스크립트를 창 없이 띄우면 `[Console]::OutputEncoding` 이 "핸들이 잘못되었습니다"
# 로 터지고, 바로 위 `$ErrorActionPreference = "Stop"` 때문에 그 자리에서 끝난다 —
# 프로그램을 끄기도 전에, 아무 흔적도 없이. 이제는 창을 주고 띄우지만, 창이 없는
# 자리에서 불려도 갱신은 계속되어야 한다. 글씨가 깨지는 것과 갱신을 못 하는 것은
# 견줄 일이 아니다.
$script:oldEnc = $null
try { $script:oldEnc = [Console]::OutputEncoding } catch { }
try { [Console]::OutputEncoding = [Text.Encoding]::UTF8 } catch { }

# 나갈 때는 반드시 원래대로 돌려 놓는다.
#
# 콘솔 글자표는 **창 전체의 설정**이라 이 스크립트가 끝나도 남는다. 그대로 두면
# 우리를 부른 '업데이트.bat' 이 이어서 찍는 한글이 전부 깨진다. 원장님 화면
# 마지막 줄이 ??????? 로 나온 것이 이것이다 — 다 해 놓고 마지막 한 줄에서
# "뭔가 잘못됐다" 는 인상을 남겼다.
function Restore-Console {
    if ($script:oldEnc) { try { [Console]::OutputEncoding = $script:oldEnc } catch { } }
    try { Stop-Transcript | Out-Null } catch { }
}

# 무슨 일이 있었는지 파일로도 남긴다. 창이 닫혀 버렸거나 창 없이 돌았을 때,
# 원장님이 "왜 안 됐나" 를 물으실 곳이 있어야 한다.
$Log = Join-Path $PSScriptRoot "갱신기록.txt"
try { Start-Transcript -Path $Log -Force | Out-Null } catch { }

$Repo   = "himan98hkt-prog/-"
$Branch = "claude/program-development-yi0956"
$Root   = $PSScriptRoot
$Stamp  = Join-Path $Root "설치버전.txt"

# 프로그램을 다시 켠다 — .bat 을 거치지 않는다.
#
# 윈도우에서 .bat 파일 연결이 메모장으로 바뀌어 있으면 두 번 눌러도 실행되지 않고
# 메모장이 열린다. 원장님 PC 가 정확히 그 상태였다. 그래서 여기서는 파일 연결과
# 무관하게 파이썬을 직접 부른다.
#
# **이 설명은 반드시 # 주석이어야 한다.** PowerShell 에는 파이썬 같은 독스트링이
# 없다. 큰따옴표 세 개는 그냥 문자열 식이고, 함수가 불릴 때마다 화면에
# 그대로 찍힌다. 실제로 원장님 화면에 개발자 메모가 통째로 출력됐다 —
# 원장님은 그것을 자기더러 하라는 지시로 읽으신다.
function Restart-App($root) {
    $pyw = Join-Path $root ".venv\Scripts\pythonw.exe"
    $py  = Join-Path $root ".venv\Scripts\python.exe"
    $launch = Join-Path $root "scripts\launch.py"
    if (Test-Path $pyw)     { Start-Process -FilePath $pyw -ArgumentList "`"$launch`"" -WorkingDirectory $root }
    elseif (Test-Path $py)  { Start-Process -FilePath $py  -ArgumentList "`"$launch`"" -WorkingDirectory $root }
    else { Write-Host "      바탕화면의 '콩쿨 작곡기' 아이콘을 눌러 주십시오." -ForegroundColor DarkGray }
}

function Step($m) { Write-Host $m -ForegroundColor White }
function Ok($m)   { Write-Host "  OK  $m" -ForegroundColor Green }
function Note($m) { Write-Host "      $m" -ForegroundColor DarkGray }
function Warn($m) { Write-Host "  !   $m" -ForegroundColor Yellow }
# **무슨 일이 있어도 프로그램은 다시 켜 놓고 나간다.**
#
# 이 스크립트는 프로그램을 먼저 끄고 시작한다. 그런데 중간 어디서든 멈추면
# (인터넷이 끊기거나, 압축이 깨졌거나, 파일이 잠겼거나) 그대로 종료해서
# **원장님께는 꺼진 프로그램만 남았다.** 원장님이 "프로그램이 꺼졌다가 다시
# 켜져야 하는데 잘 안된다" 고 하신 것이 이것이다.
#
# 갱신에 실패하는 것과 프로그램을 못 쓰게 만드는 것은 전혀 다른 일이다.
# 갱신은 실패해도 되지만, 프로그램은 반드시 돌아와야 한다.
function Die($m)  {
    Write-Host "  X   $m" -ForegroundColor Red
    if ($script:wasRunning) {
        Write-Host "" 
        Write-Host "  갱신은 못 했지만 프로그램은 다시 켜 드립니다." -ForegroundColor Yellow
        Restart-App $Root
    }
    Write-Host ""
    Write-Host "  무엇이 막았는지 이 파일에 적어 두었습니다: $Log" -ForegroundColor DarkGray
    Write-Host "  창은 20초 뒤 닫힙니다." -ForegroundColor DarkGray
    Restore-Console
    Start-Sleep -Seconds 20
    exit 1
}

Write-Host ""
Write-Host "  콩쿨 작곡기 — 새 판으로 올리기" -ForegroundColor White
Write-Host "  이 폴더: $Root" -ForegroundColor DarkGray
Write-Host ""

# ── 1. 프로그램이 켜져 있으면 먼저 끈다 ────────────────────────────────────
# 켜진 채로 파일을 바꾸면 반만 바뀐 프로그램이 된다. 그것이 가장 찾기 어려운 고장이다.
Step "1/6 켜져 있는지 본다"
$script:wasRunning = $false
$alien = @()
foreach ($port in 8000..8011) {
    try {
        $r = Invoke-WebRequest -Uri "http://127.0.0.1:$port/health" -TimeoutSec 1 -UseBasicParsing
        if ($r.StatusCode -eq 200) {
            # **어느 폴더의 프로그램인지 보고 끈다.**
            #
            # 원장님 PC 에는 사본이 둘 있다(바탕화면 · C 드라이브). 앞선 판은 8000 번이
            # 응답만 하면 무조건 껐다 — 그게 **다른 폴더의 프로그램**이어도. 그러면 남의
            # 것을 꺼 놓고 이 폴더에서 다시 켜려 하는데, 이 폴더에 .venv 가 없으면
            # 아무것도 안 켜진다. 원장님께는 그냥 "프로그램이 사라졌다" 로 보인다.
            $rootOf = ""
            try { $rootOf = ($r.Content | ConvertFrom-Json).root } catch { }
            $mine = (-not $rootOf) -or ($rootOf -eq $Root)
            if (-not $mine) {
                $alien += "$port ($rootOf)"
                Warn "$port 번은 **다른 폴더**의 프로그램입니다 — 건드리지 않습니다"
                Note "그 폴더: $rootOf"
                continue
            }
            $script:wasRunning = $true
            Note "$port 번에서 돌고 있습니다 — 잠시 끕니다"
            try { Invoke-WebRequest -Uri "http://127.0.0.1:$port/api/shutdown" -Method Post -TimeoutSec 3 -UseBasicParsing | Out-Null } catch { }
            # **정말 꺼졌는지 확인한다.** 2초만 자고 넘어가면, 아직 켜져 있는 채로
            # 파일을 덮어쓰게 된다. 윈도우는 쓰는 중인 파일을 잠그므로 복사가 실패하고,
            # 그러면 반만 바뀐 프로그램이 남는다 — 가장 찾기 어려운 고장이다.
            $gone = $false
            foreach ($try in 1..30) {
                Start-Sleep -Milliseconds 700
                try { Invoke-WebRequest -Uri "http://127.0.0.1:$port/health" -TimeoutSec 1 -UseBasicParsing | Out-Null }
                catch { $gone = $true; break }
            }
            if ($gone) { Note "$port 번이 꺼졌습니다" }
            else { Warn "$port 번이 아직 살아 있습니다 — 바꾸다 막힐 수 있습니다" }
        }
    } catch { }
}
if ($wasRunning) { Ok "껐습니다 — 다 끝나면 다시 켜 드립니다" } else { Ok "꺼져 있습니다" }
if ($alien.Count -gt 0) {
    Write-Host ""
    Warn "이 폴더가 아닌 곳에서 프로그램이 돌고 있습니다: $($alien -join ', ')"
    Warn "지금 쓰고 계신 것이 그쪽이라면, **그 폴더의 '업데이트.bat'** 을 눌러 주십시오."
    Warn "이 폴더($Root)를 올려 봐야 화면은 그대로입니다."
    Write-Host ""
}

# ── 2. 새 판이 있는지 본다 ────────────────────────────────────────────────
Step "2/6 새 판이 있는지 확인"
$here = ""
if (Test-Path $Stamp) { $here = (Get-Content $Stamp -Raw -ErrorAction SilentlyContinue).Trim() }
$latest = ""
try {
    $api = "https://api.github.com/repos/$Repo/commits/$Branch"
    $head = Invoke-RestMethod -Uri $api -Headers @{ "User-Agent" = "ConcoursComposer" } -TimeoutSec 20
    $latest = "$($head.sha)"
} catch {
    Warn "새 판이 있는지 물어보지 못했습니다 (인터넷·방화벽) — 그냥 최신을 받아 봅니다"
}
if ($latest -and $here -and ($latest -eq $here)) {
    Write-Host ""
    Ok "이미 최신입니다. 바꿀 것이 없습니다."
    Note "판 번호: $($here.Substring(0,7))"
    Write-Host ""
    # "이미 최신입니다" 만 보고 나가면 원장님은 **아무것도 안 바뀐 것**과 구분할 수
    # 없다. 실제로 "전혀 업그레이드가 안되는데" 라고 하셨는데, 그때 파일은 이미
    # 최신이었다. 그러니 화면에서 눈으로 확인하는 법을 여기서 알려 드린다.
    Write-Host "  새 판이 맞는지 눈으로 보시려면:" -ForegroundColor White
    Note "1. 프로그램이 켜지면 브라우저에서 Ctrl 키를 누른 채 F5 를 한 번 누르십시오"
    Note "   (그냥 F5 는 예전 화면이 그대로 나올 수 있습니다)"
    Note "2. 화면 위쪽에 '최신 판입니다 · 판 번호 $($here.Substring(0,7))' 라고 나오면 맞습니다"
    Write-Host ""
    if ($wasRunning) { Restart-App $Root }
    Restore-Console
    Start-Sleep -Seconds 10
    exit 0
}
if ($latest) { Note "새 판: $($latest.Substring(0,7))" }
if ($here)   { Note "지금 판: $($here.Substring(0,7))" }

# ── 3. 받는다 ─────────────────────────────────────────────────────────────
Step "3/6 새 판을 받는다"
$tmp = Join-Path ([IO.Path]::GetTempPath()) ("cc-update-" + [Guid]::NewGuid().ToString("N").Substring(0, 8))
New-Item -ItemType Directory -Path $tmp -Force | Out-Null
$zip = Join-Path $tmp "new.zip"
$url = "https://github.com/$Repo/archive/refs/heads/$Branch.zip"
try {
    $ProgressPreference = "SilentlyContinue"
    Invoke-WebRequest -Uri $url -OutFile $zip -TimeoutSec 300 -UseBasicParsing
} catch {
    Die "내려받지 못했습니다: $_`n      인터넷 연결이나 회사 방화벽을 확인해 주십시오."
}
$mb = [math]::Round((Get-Item $zip).Length / 1MB, 1)
Ok "받았습니다 ($mb MB)"

Step "4/6 압축을 푼다"
try { Expand-Archive -Path $zip -DestinationPath $tmp -Force } catch { Die "압축을 풀지 못했습니다: $_" }
# 압축 안에는 폴더가 하나 있고, 그 안에 concours-composer 가 있다.
$inner = Get-ChildItem -Path $tmp -Directory | Select-Object -First 1
if (-not $inner) { Die "압축 안이 비어 있습니다" }
$src = Join-Path $inner.FullName "concours-composer"
if (-not (Test-Path $src)) { $src = $inner.FullName }
if (-not (Test-Path (Join-Path $src "server"))) { Die "받은 파일이 이 프로그램이 아닙니다" }
Ok "풀었습니다"

# ── 5. 되돌릴 수 있게 사본을 뜨고 덮어쓴다 ────────────────────────────────
# 원장님 것은 건드리지 않는다. 아래 목록은 **프로그램이 만들지 않은 것**들이다.
$keep = @(".env", ".env.bak", "data", "runs", "web\vendor", ".venv",
          "설치기록.txt", "실행기록.txt", "실측결과.txt", "reference_scores")

Step "5/6 되돌릴 수 있게 사본을 뜬 뒤 바꾼다"
$backup = Join-Path (Split-Path $Root -Parent) ("콩쿨작곡기_이전판_" + (Get-Date -Format "yyyyMMdd-HHmm"))
try {
    $skip = @(".venv", "data", "runs", "__pycache__")
    New-Item -ItemType Directory -Path $backup -Force | Out-Null
    Get-ChildItem -Path $Root -Force | Where-Object { $skip -notcontains $_.Name } | ForEach-Object {
        Copy-Item $_.FullName -Destination $backup -Recurse -Force -ErrorAction SilentlyContinue
    }
    Ok "이전 판을 옆에 두었습니다"
    Note $backup
} catch {
    Warn "사본을 뜨지 못했습니다 — 계속합니다: $_"
}

$changed = 0
$stuck = @()
Get-ChildItem -Path $src -Recurse -File | ForEach-Object {
    $rel = $_.FullName.Substring($src.Length).TrimStart('\')
    foreach ($k in $keep) { if ($rel -eq $k -or $rel.StartsWith("$k\")) { return } }
    $dest = Join-Path $Root $rel
    $dir = Split-Path $dest -Parent
    if (-not (Test-Path $dir)) { New-Item -ItemType Directory -Path $dir -Force | Out-Null }
    # 파일 하나가 잠겨 있다고 갱신 전체를 멈추면 안 된다. 그러면 반만 바뀐 채로
    # 끝나고, 프로그램은 다시 켜지지도 않는다. 몇 번 다시 해 보고, 그래도 안 되면
    # 그 파일만 적어 두고 넘어간다.
    $done = $false
    foreach ($try in 1..3) {
        try { Copy-Item $_.FullName -Destination $dest -Force -ErrorAction Stop; $done = $true; break }
        catch { Start-Sleep -Milliseconds 400 }
    }
    if ($done) { $changed++ } else { $stuck += $rel }
}
Ok "$changed 개 파일을 새것으로 바꿨습니다"
if ($stuck.Count -gt 0) {
    Warn "$($stuck.Count) 개는 사용 중이라 바꾸지 못했습니다:"
    $stuck | Select-Object -First 5 | ForEach-Object { Note "  $_" }
    Warn "프로그램을 완전히 끈 뒤 한 번 더 올려 주십시오."
}
Note "API 키(.env)와 만든 곡, 참고 악보는 그대로 두었습니다"

# .ps1 은 인터넷에서 받은 표시가 붙어 실행이 막힌다 — 떼어 준다.
try { Get-ChildItem -Path $Root -Recurse -Filter *.ps1 | Unblock-File } catch { }

# ── 6. 부품을 맞추고 점검한다 ─────────────────────────────────────────────
Step "6/6 부품을 맞추고 점검한다"
$vpy = Join-Path $Root ".venv\Scripts\python.exe"
if (-not (Test-Path $vpy)) {
    Warn "가상환경이 없습니다 — '설치.bat' 을 한 번 돌려 주십시오"
    Write-Host ""
    Restore-Console
    Start-Sleep -Seconds 8
    exit 1
}
& $vpy -m pip install -q -r (Join-Path $Root "server\requirements-desktop.txt")
if ($LASTEXITCODE -ne 0) { Warn "부품 설치가 매끄럽지 않았습니다 — 점검을 계속합니다" } else { Ok "부품 맞춤" }

& $vpy (Join-Path $Root "scripts\self_check.py")
if ($LASTEXITCODE -ne 0) {
    Write-Host ""
    Warn "자기 점검이 통과하지 못했습니다."
    Warn "이전 판이 옆 폴더에 그대로 있습니다: $backup"
    Write-Host ""
    if ($script:wasRunning) {
        Write-Host "  점검은 통과 못 했지만 프로그램은 다시 켜 드립니다." -ForegroundColor Yellow
        Restart-App $Root
    }
    Restore-Console
    Start-Sleep -Seconds 8
    exit 1
}
Ok "점검 통과"

# 도장(설치버전.txt)은 **정말 다 바꿨을 때만**, 그리고 **BOM 없이** 찍는다.
#
# 윈도우 PowerShell 5.1 의 `Set-Content -Encoding UTF8` 은 파일 앞에 BOM 세 바이트를
# 붙인다. 그것을 파이썬이 판 번호로 읽으면 값이 어긋나서, 몇 번을 올려도 화면은
# 영영 "새 판이 나왔습니다" 라고 한다. [IO.File]::WriteAllText 는 BOM 을 붙이지 않는다.
#
# 잠긴 파일이 하나라도 남았는데 도장을 찍으면, 다음에 올릴 때 "이미 최신입니다" 라며
# 그냥 나간다 — 반만 바뀐 프로그램이 최신이라는 이름으로 굳는다. 그러느니 도장을
# 찍지 않고 다음 번에 한 번 더 시도하는 편이 낫다.
if ($latest -and $stuck.Count -eq 0) {
    [IO.File]::WriteAllText($Stamp, $latest)   # BOM 없이. 아래 주석을 보라.
} elseif ($stuck.Count -gt 0) {
    Warn "바꾸지 못한 파일이 있어 '최신' 도장은 찍지 않았습니다 — 한 번 더 올려 주십시오."
}
try { Remove-Item $tmp -Recurse -Force -ErrorAction SilentlyContinue } catch { }

Write-Host ""
Write-Host "  다 됐습니다. 만든 곡과 API 키는 그대로입니다." -ForegroundColor Green
Write-Host "  화면 위쪽에 '최신 판입니다' 라고 나오면 제대로 올라간 것입니다." -ForegroundColor Green
if ($latest) { Note "판 번호: $($latest.Substring(0,7))" }
Note "이전 판이 필요하면: $backup"
Write-Host ""
if ($wasRunning) {
    Write-Host "  프로그램을 다시 켭니다..." -ForegroundColor White
    Restart-App $Root
} else {
    Write-Host "  바탕화면의 '콩쿨 작곡기' 아이콘을 두 번 누르십시오."
}
Write-Host ""
# 창이 곧바로 사라지면 원장님은 다 된 것인지 아무 일도 안 일어난 것인지 모르신다.
Write-Host "  이 창은 10초 뒤 닫힙니다. (기록: $Log)" -ForegroundColor DarkGray
Restore-Console
Start-Sleep -Seconds 10
