#!/usr/bin/env bash
# AutoShorts-Engine 설치 (macOS / Linux)
#   curl 로 받은 뒤:  bash install.sh
set -euo pipefail

cd "$(dirname "$0")"
echo
echo "=== AutoShorts-Engine 설치 ==="
echo

# ── 1. 파이썬 확인 ────────────────────────────────────────
if command -v python3 >/dev/null 2>&1; then
  PY=python3
elif command -v python >/dev/null 2>&1; then
  PY=python
else
  echo "❌ 파이썬을 찾을 수 없습니다. https://www.python.org/downloads/ 에서 3.10 이상을 설치하세요."
  exit 1
fi

PY_VERSION="$($PY -c 'import sys; print("%d.%d" % sys.version_info[:2])')"
echo "  파이썬 $PY_VERSION ($(command -v $PY))"
$PY -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "❌ 파이썬 3.10 이상이 필요합니다 (현재 $PY_VERSION)."
  exit 1
}

# ── 2. FFmpeg 확인 ────────────────────────────────────────
if command -v ffmpeg >/dev/null 2>&1; then
  echo "  FFmpeg $(ffmpeg -version 2>/dev/null | head -1 | cut -d' ' -f3)"
else
  echo
  echo "⚠️  FFmpeg 가 없습니다. 영상 편집에 반드시 필요합니다."
  if [[ "$(uname)" == "Darwin" ]]; then
    echo "     brew install ffmpeg"
  else
    echo "     sudo apt install ffmpeg fonts-nanum      # Ubuntu/Debian"
    echo "     sudo dnf install ffmpeg google-noto-sans-cjk-fonts   # Fedora"
  fi
  echo
  read -r -p "  FFmpeg 없이 계속할까요? (y/N) " reply
  [[ "$reply" =~ ^[Yy]$ ]] || exit 1
fi

# ── 3. 가상환경 ───────────────────────────────────────────
if [[ ! -d .venv ]]; then
  echo
  echo "  가상환경을 만듭니다 (.venv)..."
  $PY -m venv .venv
fi
# shellcheck disable=SC1091
source .venv/bin/activate
python -m pip install --quiet --upgrade pip

# ── 4. 의존성 ─────────────────────────────────────────────
echo "  의존성을 설치합니다. 처음에는 몇 분 걸립니다..."
python -m pip install --quiet -r requirements.txt
python -m pip install --quiet -e .

echo
echo "✅ 설치 완료"
echo
echo "다음 단계"
echo "  1) source .venv/bin/activate      # 가상환경 활성화 (새 터미널마다)"
echo "  2) autoshorts setup               # API 키 입력"
echo "  3) autoshorts doctor              # 설치 상태 점검"
echo "  4) autoshorts ui                  # 웹 화면 → http://127.0.0.1:7860"
echo
echo "업로드까지 쓰시려면"
echo "  autoshorts login                  # 최초 1회 브라우저 로그인"
echo "  autoshorts schedule add \"재테크\" --at 09:00 -- --upload"
echo
