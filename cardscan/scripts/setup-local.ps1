# 명함스캔 — 집 PC(윈도우) 개발 환경 한 번에 준비
# 사용법: cardscan 폴더에서 PowerShell 로
#   powershell -ExecutionPolicy Bypass -File scripts\setup-local.ps1
# 하는 일: 준비물 확인(Git·Node·Java·안드로이드 SDK) → 패키지 설치 → 타입검사·테스트 → 다음 할 일 안내

$ErrorActionPreference = 'Stop'
Set-Location (Split-Path -Parent $PSScriptRoot)

function Ok($m)   { Write-Host "  [OK]  $m" -ForegroundColor Green }
function Warn($m) { Write-Host "  [!!]  $m" -ForegroundColor Yellow }
function Fail($m) { Write-Host "  [XX]  $m" -ForegroundColor Red }

Write-Host "`n== 1. 준비물 확인 ==" -ForegroundColor Cyan
$must = $true
if (Get-Command git -ErrorAction SilentlyContinue) { Ok "Git $(git --version)" } else { Fail 'Git 이 없습니다 → https://git-scm.com/download/win'; $must = $false }
if (Get-Command node -ErrorAction SilentlyContinue) {
  $v = (node -v).TrimStart('v'); $major = [int]($v.Split('.')[0])
  if ($major -ge 20) { Ok "Node $v" } else { Fail "Node $v — 20 이상 필요 (22 LTS 권장) → https://nodejs.org"; $must = $false }
} else { Fail 'Node.js 가 없습니다 → https://nodejs.org (22 LTS)'; $must = $false }
if (-not $must) { Write-Host "`n위 준비물을 설치하고 PowerShell 을 새로 열어 다시 실행하세요." -ForegroundColor Red; exit 1 }

# 휴대폰에 직접 설치해 개발할 때만 필요 (웹 미리보기·테스트는 없어도 됨)
if (Get-Command java -ErrorAction SilentlyContinue) { Ok "Java $((java -version 2>&1)[0])" } else { Warn 'Java(JDK 17) 없음 — 휴대폰 개발 빌드(npm run android:dev)에만 필요. Android Studio 를 설치하면 함께 들어옵니다' }
$sdk = $env:ANDROID_HOME; if (-not $sdk) { $sdk = "$env:LOCALAPPDATA\Android\Sdk" }
if (Test-Path "$sdk\platform-tools\adb.exe") { Ok "안드로이드 SDK $sdk" } else { Warn '안드로이드 SDK 없음 — 휴대폰 개발 빌드에만 필요. Android Studio 설치 후 SDK Manager 에서 받으세요 (HANDOVER.md 2-2)' }

Write-Host "`n== 2. 패키지 설치 (처음 3~5분) ==" -ForegroundColor Cyan
npm ci
if ($LASTEXITCODE -ne 0) { Fail 'npm ci 실패 — 인터넷 연결을 확인하고 다시 실행하세요'; exit 1 }
Ok '패키지 설치 완료'

Write-Host "`n== 3. 타입검사 + 자동 테스트 ==" -ForegroundColor Cyan
npm run check
if ($LASTEXITCODE -ne 0) { Fail '검사 실패 — 위 오류를 확인하세요'; exit 1 }
Ok '모두 통과'

Write-Host "`n== 준비 끝! 다음 할 일 ==" -ForegroundColor Cyan
Write-Host '  화면 빠르게 보기(웹 미리보기) :  npm run web'
Write-Host '  내 안드로이드폰에서 실행      :  npm run android:dev   (USB 디버깅 켜고 연결 — HANDOVER.md 3-2)'
Write-Host '  테스트만 다시                 :  npm run check'
Write-Host '  자세한 안내                   :  HANDOVER.md'
