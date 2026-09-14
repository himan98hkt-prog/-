#!/usr/bin/env bash
# 원스텝 실행 — 처음이든 두 번째든 이 파일 하나만 실행하면 됩니다.
#
#   ./start.sh
#
# 하는 일: 가상환경 준비 → 의존성 설치 → 대시보드 실행 → 브라우저 열기
# 대시보드에서 키를 입력하고 "자동매매 시작" 버튼을 누르면 끝입니다.

set -euo pipefail
cd "$(dirname "$0")"

PORT="${PORT:-8765}"
VENV=".venv"

echo "════════════════════════════════════════════════════════"
echo "  Multi-Agent 자동매매 — 준비"
echo "════════════════════════════════════════════════════════"

# --- Python 확인 ---------------------------------------------------------
PY=""
for candidate in python3.13 python3.12 python3.11 python3 python; do
  if command -v "$candidate" >/dev/null 2>&1; then
    version=$("$candidate" -c 'import sys; print(f"{sys.version_info[0]}{sys.version_info[1]:02d}")' 2>/dev/null || echo 0)
    if [ "$version" -ge 311 ] 2>/dev/null; then PY="$candidate"; break; fi
  fi
done
if [ -z "$PY" ]; then
  echo "❌ Python 3.11 이상이 필요합니다. https://www.python.org/downloads/ 에서 설치하세요."
  exit 1
fi
echo "✅ Python: $($PY --version)"

# --- 가상환경 ------------------------------------------------------------
if [ ! -d "$VENV" ]; then
  echo "· 가상환경을 만드는 중..."
  "$PY" -m venv "$VENV"
fi
# shellcheck disable=SC1091
source "$VENV/bin/activate"

# --- 의존성 (변경됐을 때만 재설치) ----------------------------------------
STAMP="$VENV/.deps-installed"
if [ ! -f "$STAMP" ] || [ requirements.txt -nt "$STAMP" ]; then
  echo "· 의존성을 설치하는 중... (처음 한 번은 몇 분 걸립니다)"
  python -m pip install --quiet --upgrade pip
  # ta 는 레거시 setup.py 라 환경에 따라 wheel 빌드가 실패한다
  python -m pip install --quiet --use-pep517 -r requirements.txt
  touch "$STAMP"
  echo "✅ 의존성 설치 완료"
else
  echo "✅ 의존성 준비됨"
fi

# --- 첫 실행 안내 --------------------------------------------------------
if [ ! -f .env ]; then
  echo ""
  echo "🔑 아직 키가 없습니다. 곧 열리는 브라우저 화면에서 입력하세요."
fi

echo ""
echo "════════════════════════════════════════════════════════"
echo "  대시보드:  http://127.0.0.1:$PORT"
echo ""
echo "  1) 설정 화면에 API 키를 붙여넣고 [저장]"
echo "  2) [키 점검 실행] 으로 전부 ✅ 확인"
echo "  3) 현황 화면에서 [▶ 자동매매 시작]"
echo ""
echo "  이 창을 닫으면 대시보드가 꺼집니다 (매매는 계속 돕니다)"
echo "  중지: Ctrl+C"
echo "════════════════════════════════════════════════════════"
echo ""

# 브라우저는 서버가 실제로 뜬 뒤에 열린다 (--open-browser).
# 먼저 열면 "연결할 수 없음" 페이지가 뜬다.
#
# 종료 코드 42 = "방금 나를 업데이트했으니 다시 띄워라". 새 코드를 실제로
# 읽어들이려면 프로세스를 갈아야 한다(파이썬은 모듈을 한 번만 import 한다).
while true; do
  set +e
  python scripts/dashboard.py --port "$PORT" --open-browser
  code=$?
  set -e
  if [ "$code" -ne 42 ]; then
    exit "$code"
  fi
  echo ""
  echo "· 업데이트 적용됨 — 대시보드를 다시 띄웁니다..."
  echo ""
done
