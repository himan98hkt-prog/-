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

step "1/7 파이썬 확인"
PY=""
for c in python3.13 python3.12 python3 python; do
  if command -v "$c" >/dev/null 2>&1 && "$c" -c 'import sys; sys.exit(0 if sys.version_info >= (3,12) else 1)' 2>/dev/null; then
    PY="$c"; break
  fi
done
[ -n "$PY" ] || fail "Python 3.12 이상이 필요하다. https://www.python.org/downloads/ 에서 설치한 뒤 다시 실행하라."
ok "$($PY --version)"

step "2/7 가상환경"
[ -d .venv ] || "$PY" -m venv .venv
VPY=".venv/bin/python"
ok ".venv"

step "3/7 의존성 설치 ${DIM}(처음 한 번은 몇 분 걸린다)${OFF}"
"$VPY" -m pip install -q --upgrade pip
"$VPY" -m pip install -q -r server/requirements.txt
ok "설치 완료"

step "4/7 설정 파일"
if [ -f .env ]; then
  ok ".env 가 이미 있다 — 건드리지 않는다"
else
  cp .env.example .env
  ok ".env 를 만들었다"
  say "  ${DIM}API 키가 없어도 규칙 기반 스텁으로 전 과정이 돌아간다.${OFF}"
  say "  ${DIM}실제 작곡 품질을 쓰려면 .env 의 ANTHROPIC_API_KEY 를 채워라.${OFF}"
fi

step "5/7 악보 렌더러 내려받기 ${DIM}(없어도 프로그램은 돈다)${OFF}"
"$VPY" scripts/fetch_vendor.py || true
ok "완료"

step "6/7 바탕화면 아이콘 만들기"
HERE="$(pwd)"
if [ "$(uname)" = "Darwin" ]; then
  # 맥은 더블클릭으로 도는 .command 파일을 바탕화면에 둔다.
  DESK="$HOME/Desktop/콩쿨 작곡기.command"
  cat > "$DESK" <<LAUNCH
#!/usr/bin/env bash
cd "$HERE" && exec "$HERE/.venv/bin/python" scripts/launch.py
LAUNCH
  chmod +x "$DESK"
  ok "바탕화면에 '콩쿨 작곡기' 를 만들었다"
else
  DESK_DIR="${XDG_DESKTOP_DIR:-$HOME/Desktop}"
  mkdir -p "$DESK_DIR" "$HOME/.local/share/applications"
  for D in "$DESK_DIR/concours-composer.desktop" "$HOME/.local/share/applications/concours-composer.desktop"; do
    cat > "$D" <<LAUNCH
[Desktop Entry]
Type=Application
Name=콩쿨 작곡기
Comment=컨셉을 고르면 심사까지 마친 콩쿨곡이 나옵니다
Exec=$HERE/.venv/bin/python $HERE/scripts/launch.py
Icon=$HERE/assets/app/icon.png
Path=$HERE
Terminal=false
Categories=Audio;Music;
LAUNCH
    chmod +x "$D"
  done
  ok "바탕화면과 앱 목록에 '콩쿨 작곡기' 를 만들었다"
fi

step "7/7 자기 점검"
"$VPY" scripts/self_check.py
ok "정상"

printf '\n%s\n' "${BOLD}설치 끝.${OFF}"
printf '  %s\n' "바탕화면의 '콩쿨 작곡기' 를 두 번 누르십시오."
printf '  %s\n\n' "(없으면 이 폴더에서  ./start.sh  를 실행하십시오)"
