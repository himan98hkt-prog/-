#!/bin/bash
# ===========================================================================
#  폰·태블릿에서 열기 — 같은 와이파이에 있는 기기로 반주를 보냅니다.
#
#  두 번 눌러 실행하세요. 주소가 뜨면 폰 브라우저에 그대로 치시면 됩니다.
#  (install-mac.command 를 먼저 한 번 돌리셨어야 합니다)
# ===========================================================================
cd "$(dirname "$0")" || exit 1
export PYTHONIOENCODING=utf-8

PY=""
for c in python3.13 python3.12 python3.11 python3; do
  if command -v "$c" >/dev/null 2>&1; then PY="$c"; break; fi
done
if [ -z "$PY" ]; then
  echo
  echo "  먼저 install-mac.command 를 두 번 눌러 설치하세요."
  echo
  read -r -p "  엔터를 누르면 창이 닫힙니다. " _
  exit 1
fi

"$PY" tools/setup.py --phone
code=$?
[ $code -ne 0 ] && read -r -p "  엔터를 누르면 창이 닫힙니다. " _
exit $code
