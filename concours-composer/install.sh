#!/usr/bin/env bash
# ConcoursComposer 설치 — macOS · Linux
#
# 하는 일: 파이썬 확인 → 가상환경 → 의존성 → .env 생성 → 자기 점검.
# 인터넷과 Python 3.12 이상만 있으면 된다. 관리자 권한은 필요 없다.
set -euo pipefail
cd "$(dirname "$0")"

BOLD=$'\033[1m'; DIM=$'\033[2m'; RED=$'\033[31m'; GREEN=$'\033[32m'; OFF=$'\033[0m'
say()  { printf '%s\n' "$1"; }
step() { printf '%s\n' "${BOLD}$1${OFF}"; }
fail() { printf '%s\n' "${RED}✗ $1${OFF}" >&2; exit 1; }
ok()   { printf '%s\n' "${GREEN}✓${OFF} $1"; }

step "1/5 파이썬 확인"
PY=""
for c in python3.13 python3.12 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || fail "Python 3.12 이상이 필요하다. https://www.python.org/downloads/ 에서 설치한 뒤 다시 실행하라."
ok "$($PY --version)"

step "2/5 가상환경"
[ -d .venv ] || "$PY" -m venv .venv
VPY=".venv/bin/python"
ok ".venv"

step "3/5 의존성 설치 ${DIM}(처음 한 번은 몇 분 걸린다)${OFF}"
"$VPY" -m pip install -q --upgrade pip
"$VPY" -m pip install -q -r server/requirements.txt
ok "설치 완료"

step "4/5 설정 파일"
if [ -f .env ]; then
  ok ".env 가 이미 있다 — 건드리지 않는다"
else
  cp .env.example .env
  ok ".env 를 만들었다"
  say "  ${DIM}API 키가 없어도 규칙 기반 스텁으로 전 과정이 돌아간다.${OFF}"
  say "  ${DIM}실제 작곡 품질을 쓰려면 .env 의 ANTHROPIC_API_KEY 를 채워라.${OFF}"
fi

step "5/5 자기 점검"
"$VPY" scripts/self_check.py
ok "정상"

printf '\n%s\n' "${BOLD}설치 끝. 다음 명령으로 실행한다:${OFF}"
printf '  %s\n\n' "./start.sh"
