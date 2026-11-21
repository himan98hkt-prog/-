#!/usr/bin/env bash
# 명함스캔 — 집 PC(맥·리눅스) 개발 환경 한 번에 준비
# 사용법: cardscan 폴더에서   bash scripts/setup-local.sh
set -euo pipefail
cd "$(dirname "$0")/.."

ok()   { printf '  \033[32m[OK]\033[0m  %s\n' "$1"; }
warn() { printf '  \033[33m[!!]\033[0m  %s\n' "$1"; }
fail() { printf '  \033[31m[XX]\033[0m  %s\n' "$1"; }

echo; echo "== 1. 준비물 확인 =="
must=1
if command -v git >/dev/null; then ok "$(git --version)"; else fail 'Git 이 없습니다 → https://git-scm.com'; must=0; fi
if command -v node >/dev/null; then
  v=$(node -v | tr -d v); major=${v%%.*}
  if [ "$major" -ge 20 ]; then ok "Node $v"; else fail "Node $v — 20 이상 필요 (22 LTS 권장)"; must=0; fi
else fail 'Node.js 가 없습니다 → https://nodejs.org (22 LTS)'; must=0; fi
[ "$must" = 1 ] || { echo; fail '위 준비물을 설치하고 다시 실행하세요'; exit 1; }
if command -v java >/dev/null; then ok "Java $(java -version 2>&1 | head -1)"; else warn 'Java(JDK 17) 없음 — 휴대폰 개발 빌드(npm run android:dev)에만 필요'; fi
sdk="${ANDROID_HOME:-$HOME/Library/Android/sdk}"; [ -d "$sdk" ] || sdk="$HOME/Android/Sdk"
if [ -x "$sdk/platform-tools/adb" ]; then ok "안드로이드 SDK $sdk"; else warn '안드로이드 SDK 없음 — 휴대폰 개발 빌드에만 필요 (HANDOVER.md 2-2)'; fi

echo; echo "== 2. 패키지 설치 (처음 3~5분) =="
npm ci
ok '패키지 설치 완료'

echo; echo "== 3. 타입검사 + 자동 테스트 =="
npm run check
ok '모두 통과'

echo; echo "== 준비 끝! 다음 할 일 =="
echo '  화면 빠르게 보기(웹 미리보기) :  npm run web'
echo '  내 안드로이드폰에서 실행      :  npm run android:dev   (USB 디버깅 켜고 연결 — HANDOVER.md 3-2)'
echo '  테스트만 다시                 :  npm run check'
echo '  자세한 안내                   :  HANDOVER.md'
